"""
MM Agent消息处理API
用于处理来自其他agent的消息，以及发送消息到其他agent
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from app.services.mm_service import MMService
from app.services.agent_message_service import AgentMessageService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入
def get_mm_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> MMService:
    """创建MMService实例"""
    service = MMService()
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
    
    mandt = x_mandt or x_tenant_id
    if mandt and mandt != "null" and mandt.strip() != "":
        service.set_mandt(mandt.strip())
    if x_tenant_id and x_tenant_id != "null" and x_tenant_id.strip() != "":
        service.set_tenant_id(x_tenant_id.strip())
    
    return service

def get_message_service() -> AgentMessageService:
    """创建AgentMessageService实例"""
    return AgentMessageService()

@router.post("/mm-agent/message/purchase-receipt-completed")
async def purchase_receipt_completed(
    payload: Dict[str, Any],
    message_service: AgentMessageService = Depends(get_message_service),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> Dict[str, Any]:
    """
    采购收货完成后，发送消息到sd-agent
    
    请求体:
    {
        "ebeln": "4500000123",  // 采购订单号
        "mblnr": "4900000123",  // 物料凭证号
        "vbeln": "0000000123",  // 关联的销售订单号（可选）
        "contextId": "ATP_CHECK_0000000123_20250129120000",  // 上下文ID（可选）
        "purchaseType": "standard"  // standard 或 outsource（标准采购或委外采购）
    }
    """
    try:
        ebeln = payload.get("ebeln")
        mblnr = payload.get("mblnr")
        vbeln = payload.get("vbeln")
        context_id = payload.get("contextId")
        purchase_type = payload.get("purchaseType", "standard")
        
        if not ebeln:
            raise HTTPException(status_code=400, detail="缺少采购订单号（ebeln）")
        
        mandt = x_mandt or x_tenant_id or "600"
        
        # 使用context_id作为conversation_id，关联到原始对话
        msg_result = message_service.send_message(
            sender_agent="mm-agent",
            receiver_agent="sd-agent",
            message_type="PURCHASE_RECEIPT_COMPLETED",
            content={
                "action": "CREATE_DELIVERY",
                "data": {
                    "vbeln": vbeln,
                    "ebeln": ebeln,
                    "mblnr": mblnr,
                    "purchaseType": purchase_type,
                    "message": f"{'委外' if purchase_type == 'outsource' else '标准'}采购订单 {ebeln} 收货完成，需要进行外向交货"
                }
            },
            context_id=context_id,
            conversation_id=context_id,  # 使用context_id作为conversation_id，关联到原始对话
            priority="HIGH",
            mandt=mandt,
            tenant_id=x_tenant_id
        )
        
        logger.info(f"采购收货完成，已发送消息到sd-agent，采购订单号: {ebeln}")
        
        return {
            "code": 200,
            "msg": "消息已发送到sd-agent",
            "data": {
                "messageType": "PURCHASE_RECEIPT_COMPLETED",
                "ebeln": ebeln
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送采购收货完成消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")

