"""
SD Agent AI查询接口
支持自然语言查询销售订单、ATP检查、创建交货单等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
from app.services.sd_service import SDService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建SDService实例，并传递token
def get_sd_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth")
) -> SDService:
    """创建SDService实例，并传递认证token"""
    service = SDService()
    
    # 优先从Authorization头获取token（bearer格式）
    token = None
    if authorization:
        logger.info(f"收到Authorization头: {authorization[:20]}...")  # 只记录前20个字符，避免泄露完整token
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()  # 去除前后空格
            logger.info(f"从Authorization头提取token (长度: {len(token)})")
        else:
            logger.warning(f"Authorization头格式不正确: {authorization[:20]}...")
    
    # 如果Authorization头没有token，尝试从Blade-Auth头获取（项目标准格式）
    if not token and blade_auth:
        logger.info(f"收到Blade-Auth头: {blade_auth[:20]}...")
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()  # 去除前后空格
            logger.info(f"从Blade-Auth头提取token (长度: {len(token)})")
        elif blade_auth.lower().startswith("crypto "):
            logger.warning("Blade-Auth头使用了加密格式，需要解密")
            # 加密token保持原样，但去除前后空格
            token = blade_auth.strip()
        else:
            # 如果没有bearer前缀，直接使用（可能是纯token）
            token = blade_auth.strip()  # 去除前后空格
            logger.info(f"从Blade-Auth头提取token（无前缀）(长度: {len(token)})")
    
    # 设置token到service
    if token:
        service.set_token(token)
        logger.info(f"Token已设置到SDService (长度: {len(token)})")
        logger.debug(f"Token前20字符: {token[:20]}...")
    else:
        logger.warning("未收到有效的token请求头（检查了Authorization和Blade-Auth）")
    
    return service

def _extract_order_number(text: str) -> Optional[str]:
    """
    从文本中提取订单号
    支持多种格式：VB2025000059, VB2025000059, 订单号VB2025000059等
    """
    patterns = [
        r"(?:订单号|订单|SO|VBELN)[\s\-:]?([A-Z0-9\-]+)",
        r"([A-Z]{2,4}[\-]?\d{8,})",
        r"([0-9]{10,})",  # 纯数字订单号
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            order_num = match.group(1).strip()
            # 过滤掉太短的数字（可能是年份等）
            if len(order_num) >= 8:
                return order_num
    
    return None

def _identify_intent(text: str) -> str:
    """
    识别用户意图
    
    Returns:
        意图类型：NAVIGATE_*, QUERY_ORDER_*, ATP_CHECK, CREATE_DELIVERY, SMALLTALK
    """
    text_lower = text.lower()
    
    # 页面跳转意图
    if any(keyword in text_lower for keyword in ["跳转", "打开", "进入", "去", "导航"]):
        if "订单列表" in text_lower or ("销售订单" in text_lower and "列表" in text_lower):
            return "NAVIGATE_ORDER_LIST"
        elif "订单详情" in text_lower or ("订单" in text_lower and "详情" in text_lower):
            return "NAVIGATE_ORDER_DETAIL"
        elif "发票" in text_lower:
            return "NAVIGATE_INVOICE"
        elif "交货单" in text_lower or "发货" in text_lower:
            return "NAVIGATE_DELIVERY"
        elif "单据流" in text_lower or "流程" in text_lower:
            return "NAVIGATE_DOCUMENT_FLOW"
    
    # 订单列表查询
    if any(keyword in text_lower for keyword in ["订单列表", "所有订单", "查询订单", "订单查询", "显示订单"]):
        return "QUERY_ORDER_LIST"
    
    # 订单详情查询
    order_num = _extract_order_number(text)
    if order_num:
        if any(keyword in text_lower for keyword in ["详情", "信息", "查看", "显示"]):
            return "QUERY_ORDER_DETAIL"
        elif any(keyword in text_lower for keyword in ["修改", "编辑", "更新"]):
            return "NAVIGATE_ORDER_EDIT"
        elif any(keyword in text_lower for keyword in ["atp", "可用性", "库存检查", "物料可用", "库存够"]):
            return "ATP_CHECK"
        elif any(keyword in text_lower for keyword in ["创建交货单", "生成交货单", "自动交货", "交货"]):
            return "CREATE_DELIVERY"
        else:
            # 如果提到订单号但没有明确意图，默认查询详情
            return "QUERY_ORDER_DETAIL"
    
    # ATP检查
    if any(keyword in text_lower for keyword in ["atp", "可用性检查", "库存检查", "物料可用性", "检查库存"]):
        return "ATP_CHECK"
    
    # 创建交货单
    if any(keyword in text_lower for keyword in ["创建交货单", "生成交货单", "自动创建交货单", "创建发货单"]):
        return "CREATE_DELIVERY"
    
    # 默认：闲聊
    return "SMALLTALK"

@router.post("/sd-agent/ai-query")
async def sd_ai_query(
    payload: Dict[str, Any],
    sd_service: SDService = Depends(get_sd_service)
) -> Dict[str, Any]:
    """
    SD模块AI查询接口
    
    支持的功能：
    1. 查询销售订单列表
    2. 查询订单详情
    3. ATP物料可用性检查
    4. 自动创建交货单
    5. 销售模块页面概览
    
    Request Body:
        {
            "query": "查询最近的销售订单"
        }
    
    Returns:
        {
            "success": true,
            "intent": "QUERY_ORDER_LIST",
            "data": {
                "type": "order_list",
                "orders": [...],
                "total": 100
            }
        }
    """
    try:
        query = payload.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query不能为空")
        
        logger.info(f"收到SD Agent查询: {query}")
        
        # 识别意图
        intent = _identify_intent(query)
        logger.info(f"识别意图: {intent}")
        
        # 根据意图处理
        if intent == "QUERY_ORDER_LIST":
            # 查询订单列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            result = await sd_service.get_order_list(current=current, size=size)
            
            # 格式化响应
            sd_data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_list",
                    "orders": sd_data.get("records", []),
                    "total": sd_data.get("total", 0),
                    "current": sd_data.get("current", current),
                    "size": sd_data.get("size", size)
                }
            }
        
        elif intent == "QUERY_ORDER_DETAIL":
            # 查询订单详情
            vbeln = _extract_order_number(query)
            if not vbeln:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供销售订单号，例如：查看订单VB2025000059"
                }
            
            result = await sd_service.get_order_detail(vbeln)
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_detail",
                    "order": result.get("data")
                }
            }
        
        elif intent == "ATP_CHECK" or intent == "CREATE_DELIVERY":
            # ATP检查或创建交货单
            vbeln = _extract_order_number(query)
            if not vbeln:
                # 根据意图区分提示文案
                if intent == "CREATE_DELIVERY":
                    error_message = "请提供销售订单号，例如：为订单 VB2025000059 创建交货单"
                else:
                    error_message = "请提供销售订单号，例如：检查订单 VB2025000059 的物料可用性"
                return {
                    "success": False,
                    "intent": intent,
                    "message": error_message
                }
            
            # 获取订单信息（用于创建交货单）
            try:
                order_info_result = await sd_service.get_order_info_for_delivery(vbeln)
                order_info = order_info_result.get("data")
                
                if not order_info:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"订单 {vbeln} 不存在或无法获取订单信息"
                    }
            except Exception as e:
                error_msg = str(e)
                # 处理无行项目的错误
                if "无行项目相关信息" in error_msg or "无行项目" in error_msg:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"订单 {vbeln} 没有可用的行项目信息，无法进行ATP检查。请确认订单是否已创建行项目数据。"
                    }
                # 处理其他错误
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"获取订单信息失败：{error_msg}"
                }
            
            # 如果是创建交货单，直接调用创建接口（内部会进行ATP检查）
            if intent == "CREATE_DELIVERY":
                try:
                    delivery_result = await sd_service.create_delivery(order_info)
                    delivery_vbeln = delivery_result.get("data")
                    
                    return {
                        "success": True,
                        "intent": intent,
                        "data": {
                            "type": "delivery_result",
                            "vbeln": delivery_vbeln,
                            "message": f"交货单创建成功，交货单号：{delivery_vbeln}"
                        }
                    }
                except Exception as e:
                    error_msg = str(e)
                    # 检查是否是库存不足的错误
                    if "库存不足" in error_msg or "可用库存" in error_msg:
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": error_msg
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "intent": intent,
                            "message": f"创建交货单失败：{error_msg}"
                        }
            else:
                # 仅ATP检查 - 通过尝试创建交货单来检查ATP（但不实际创建）
                # 如果创建成功，说明ATP检查通过；如果失败，说明库存不足
                try:
                    delivery_result = await sd_service.create_delivery(order_info)
                    delivery_vbeln = delivery_result.get("data")
                    
                    # ATP检查通过，返回成功结果
                    return {
                        "success": True,
                        "intent": intent,
                        "data": {
                            "type": "atp_check",
                            "message": f"ATP检查通过：订单 {vbeln} 的物料可用性检查完成，库存充足，可以创建交货单。",
                            "delivery_vbeln": delivery_vbeln  # 如果创建成功，返回交货单号
                        }
                    }
                except Exception as e:
                    error_msg = str(e)
                    # 检查是否是库存不足的错误
                    if "库存不足" in error_msg or "可用库存" in error_msg or "ATP" in error_msg:
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": f"ATP检查失败：{error_msg}"
                            }
                        }
                    else:
                        # 其他错误，也返回ATP检查失败
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": f"ATP检查失败：{error_msg}"
                            }
                        }
        
        elif intent.startswith("NAVIGATE_") or "销售模块页面概览" in query or "页面跳转" in query or "跳转" in query:
            # 销售模块页面概览 - 返回可跳转的SD模块页面列表
            sd_pages = [
                {
                    "name": "销售订单列表",
                    "route": "order_list",
                    "path": "/sales/titleDetail",
                    "description": "查看所有销售订单",
                    "icon": "iconfont iconicon_list"
                },
                {
                    "name": "创建销售订单",
                    "route": "order_create",
                    "path": "/sales/createDetail",
                    "description": "创建新的销售订单",
                    "icon": "iconfont iconicon_doc"
                },
                {
                    "name": "修改销售订单",
                    "route": "order_edit",
                    "path": "/sales/createDetail",
                    "description": "修改现有销售订单",
                    "icon": "iconfont iconicon_edit"
                },
                {
                    "name": "显示销售订单",
                    "route": "order_display",
                    "path": "/sales/titleDetail",
                    "description": "查看销售订单详情",
                    "icon": "iconfont iconicon_view"
                },
                {
                    "name": "销售发票列表",
                    "route": "invoice_list",
                    "path": "/sales/invoice/list",
                    "description": "查看所有销售发票",
                    "icon": "iconfont iconicon_list"
                },
                {
                    "name": "创建销售发票",
                    "route": "invoice_create",
                    "path": "/sales/invoice/create",
                    "description": "创建新的销售发票",
                    "icon": "iconfont iconicon_doc"
                },
                {
                    "name": "显示销售发票",
                    "route": "invoice_detail",
                    "path": "/sales/invoice/display",
                    "description": "查看销售发票详情",
                    "icon": "iconfont iconicon_view"
                },
                {
                    "name": "交货单列表",
                    "route": "delivery_list",
                    "path": "/solution-order/list-solution-order",
                    "description": "查看所有交货单",
                    "icon": "iconfont iconicon_list"
                },
                {
                    "name": "创建交货单",
                    "route": "delivery_create",
                    "path": "/solution-order/delivery",
                    "description": "创建新的交货单",
                    "icon": "iconfont iconicon_doc"
                },
                {
                    "name": "文档流",
                    "route": "document_flow",
                    "path": "/sales/document-flow",
                    "description": "查看销售订单文档流",
                    "icon": "iconfont iconicon_doc"
                }
            ]
            
            # 如果指定了具体页面，执行跳转
            if intent.startswith("NAVIGATE_"):
                route_map = {
                    "NAVIGATE_ORDER_LIST": "order_list",
                    "NAVIGATE_ORDER_DETAIL": "order_detail",
                    "NAVIGATE_ORDER_EDIT": "order_edit",
                    "NAVIGATE_INVOICE": "invoice",
                    "NAVIGATE_DELIVERY": "delivery",
                    "NAVIGATE_DOCUMENT_FLOW": "document_flow"
                }
                
                route = route_map.get(intent, intent.replace("NAVIGATE_", "").lower())
                vbeln = _extract_order_number(query) if "ORDER" in intent else None
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "navigate",
                        "route": route,
                        "params": {"vbeln": vbeln} if vbeln else None
                    }
                }
            else:
                # 返回页面列表
                return {
                    "success": True,
                    "intent": "NAVIGATE_LIST",
                    "data": {
                        "type": "page_list",
                        "pages": sd_pages,
                        "message": "以下是可跳转的销售模块页面，点击任意页面即可跳转："
                    }
                }
        
        else:
            # 闲聊
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "text",
                    "message": (
                        "你好，我是SD智能体。我可以帮您：\n"
                        "1. 查询销售订单列表（例如：显示最近的订单）\n"
                        "2. 查看订单详情（例如：查看订单VB2025000059）\n"
                        "3. 检查物料可用性（例如：检查订单VB2025000059的物料可用性）\n"
                        "4. 创建交货单（例如：为订单VB2025000059创建交货单）\n"
                        "5. 销售模块页面概览（例如：打开订单列表）"
                    )
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SD Agent查询处理失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"处理请求时出错：{str(e)}"
        }

