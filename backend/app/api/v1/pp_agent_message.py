"""
PP Agent消息处理API
用于处理来自其他agent的消息，以及发送消息到其他agent
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from app.services.pp_service import PPService
from app.services.agent_message_service import AgentMessageService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入
def get_pp_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth")
) -> PPService:
    """创建PPService实例"""
    service = PPService()
    token = None
    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
    elif blade_auth:
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()
        else:
            token = blade_auth.strip()
    if token:
        service.set_token(token)
    return service

def get_message_service() -> AgentMessageService:
    """创建AgentMessageService实例"""
    return AgentMessageService()

@router.post("/pp-agent/message/check-materials")
async def check_materials_after_receipt(
    payload: Dict[str, Any],
    pp_service: PPService = Depends(get_pp_service),
    message_service: AgentMessageService = Depends(get_message_service),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> Dict[str, Any]:
    """
    齐套性检查完成后，根据结果发送消息
    
    请求体:
    {
        "aufnr": "001010014285",  // 生产订单号（可选）
        "internal_aufnr": "808000000008",  // 内部订单号（可选）
        "orderType": "production",  // production 或 internal
        "checkResult": "passed",  // passed 或 failed
        "items": [...],  // 物料检查结果
        "contextId": "ATP_CHECK_0000000123_20250129120000",  // 上下文ID
        "vbeln": "0000000123"  // 关联的销售订单号
    }
    """
    try:
        aufnr = payload.get("aufnr")
        internal_aufnr = payload.get("internal_aufnr")
        order_type = payload.get("orderType", "production")
        check_result = payload.get("checkResult")
        items = payload.get("items", [])
        context_id = payload.get("contextId")
        vbeln = payload.get("vbeln")
        
        if not aufnr and not internal_aufnr:
            raise HTTPException(status_code=400, detail="缺少订单号（aufnr或internal_aufnr）")
        
        if not check_result:
            raise HTTPException(status_code=400, detail="缺少检查结果（checkResult）")
        
        mandt = x_mandt or x_tenant_id or "600"
        
        if check_result == "passed":
            # 齐套性检查通过，发送消息到sd-agent
            # 注意：这里假设已经完成了生产流程（MES同步、收货等）
            # 实际应该在收货完成后调用此接口
            
            order_number = aufnr or internal_aufnr
            message_type = "PRODUCTION_RECEIPT_COMPLETED" if order_type == "production" else "INTERNAL_RECEIPT_COMPLETED"
            
            # 使用context_id作为conversation_id，关联到原始对话
            msg_result = message_service.send_message(
                sender_agent="pp-agent",
                receiver_agent="sd-agent",
                message_type=message_type,
                content={
                    "action": "CREATE_DELIVERY",
                    "data": {
                        "vbeln": vbeln,
                        "aufnr": aufnr,
                        "internal_aufnr": internal_aufnr,
                        "orderType": order_type,
                        "message": f"{'生产订单' if order_type == 'production' else '内部订单'} {order_number} 收货完成，需要进行外向交货"
                    }
                },
                context_id=context_id,
                conversation_id=context_id,  # 使用context_id作为conversation_id，关联到原始对话
                priority="HIGH",
                mandt=mandt,
                tenant_id=x_tenant_id
            )
            
            logger.info(f"齐套性检查通过，已发送消息到sd-agent，订单号: {order_number}")
            
            return {
                "code": 200,
                "msg": "消息已发送到sd-agent",
                "data": {
                    "messageType": message_type,
                    "orderNumber": order_number
                }
            }
        else:
            # 齐套性检查不通过，发送消息到mm-agent
            insufficient_items = [item for item in items if not item.get("is_available", False)]
            
            # 自动生成新的对话ID，在mm-agent中会创建新对话
            msg_result = message_service.send_message(
                sender_agent="pp-agent",
                receiver_agent="mm-agent",
                message_type="MATERIAL_CHECK_FAILED",
                content={
                    "action": "CREATE_PURCHASE_ORDER",
                    "data": {
                        "aufnr": aufnr,
                        "internal_aufnr": internal_aufnr,
                        "orderType": order_type,
                        "items": insufficient_items,
                        "message": f"{'生产订单' if order_type == 'production' else '内部订单'} 齐套性检查失败，物料不足"
                    }
                },
                context_id=context_id,
                conversation_id=None,  # 自动生成新对话
                priority="HIGH",
                mandt=mandt,
                tenant_id=x_tenant_id
            )
            
            logger.info(f"齐套性检查不通过，已发送消息到mm-agent，订单号: {aufnr or internal_aufnr}")
            
            return {
                "code": 200,
                "msg": "消息已发送到mm-agent",
                "data": {
                    "messageType": "MATERIAL_CHECK_FAILED",
                    "insufficientItems": insufficient_items
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理齐套性检查消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

@router.post("/pp-agent/message/production-receipt-completed")
async def production_receipt_completed(
    payload: Dict[str, Any],
    message_service: AgentMessageService = Depends(get_message_service),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> Dict[str, Any]:
    """
    生产收货完成后，发送消息到sd-agent
    
    请求体:
    {
        "aufnr": "001010014285",
        "internal_aufnr": "808000000008",  // 可选
        "orderType": "production",  // production 或 internal
        "mblnr": "4900000123",  // 物料凭证号
        "vbeln": "0000000123",  // 关联的销售订单号
        "contextId": "ATP_CHECK_0000000123_20250129120000"
    }
    """
    try:
        aufnr = payload.get("aufnr")
        internal_aufnr = payload.get("internal_aufnr")
        order_type = payload.get("orderType", "production")
        mblnr = payload.get("mblnr")
        vbeln = payload.get("vbeln")
        context_id = payload.get("contextId")
        
        if not aufnr and not internal_aufnr:
            raise HTTPException(status_code=400, detail="缺少订单号（aufnr或internal_aufnr）")
        
        mandt = x_mandt or x_tenant_id or "600"
        order_number = aufnr or internal_aufnr
        message_type = "PRODUCTION_RECEIPT_COMPLETED" if order_type == "production" else "INTERNAL_RECEIPT_COMPLETED"
        
        # 使用context_id作为conversation_id，关联到原始对话
        msg_result = message_service.send_message(
            sender_agent="pp-agent",
            receiver_agent="sd-agent",
            message_type=message_type,
            content={
                "action": "CREATE_DELIVERY",
                "data": {
                    "vbeln": vbeln,
                    "aufnr": aufnr,
                    "internal_aufnr": internal_aufnr,
                    "orderType": order_type,
                    "mblnr": mblnr,
                    "message": f"{'生产订单' if order_type == 'production' else '内部订单'} {order_number} 收货完成，需要进行外向交货"
                }
            },
            context_id=context_id,
            conversation_id=context_id,  # 使用context_id作为conversation_id，关联到原始对话
            priority="HIGH",
            mandt=mandt,
            tenant_id=x_tenant_id
        )
        
        logger.info(f"生产收货完成，已发送消息到sd-agent，订单号: {order_number}")
        
        return {
            "code": 200,
            "msg": "消息已发送到sd-agent",
            "data": {
                "messageType": message_type,
                "orderNumber": order_number
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送生产收货完成消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")

