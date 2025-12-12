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

# 依赖注入：创建SDService实例，并传递token和租户信息
def get_sd_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> SDService:
    """创建SDService实例，并传递认证token和租户信息"""
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
    
    # 设置租户信息（mandt和tenantId）到service
    # 优先使用X-Mandt，如果没有则使用X-Tenant-Id
    mandt = x_mandt
    if not mandt or mandt == "null" or mandt.strip() == "":
        mandt = x_tenant_id
    
    if mandt and mandt != "null" and mandt.strip() != "":
        service.set_mandt(mandt.strip())
        logger.info(f"设置mandt: {mandt.strip()}")
    
    # 同时设置tenantId（如果提供了）
    if x_tenant_id and x_tenant_id != "null" and x_tenant_id.strip() != "":
        service.set_tenant_id(x_tenant_id.strip())
        logger.info(f"设置tenantId: {x_tenant_id.strip()}")
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
    
    # 根据指定订单复制创建新订单（优先级高，需要在订单详情查询之前）
    if "复制" in text_lower and "订单" in text_lower:
        # 检查是否提到了具体的订单号
        order_num = _extract_order_number(text)
        if order_num:
            return "COPY_ORDER"
    
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
    
    # 创建销售订单（基于昨天的最后一个订单复制）
    if any(keyword in text_lower for keyword in ["创建销售订单", "复制订单", "基于", "昨天的", "最后一个订单"]):
        if "复制" in text_lower or "基于" in text_lower:
            return "CREATE_SALES_ORDER"
    
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
    5. 销售模块概览
    
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
                # 处理"销售订单不存在"的错误 - 先验证订单是否真的不存在
                if "销售订单不存在" in error_msg or "订单不存在" in error_msg:
                    # 尝试用其他接口验证订单是否存在
                    try:
                        detail_result = await sd_service.get_order_detail(vbeln)
                        detail_data = detail_result.get("data")
                        if detail_data:
                            # 订单存在，但getVbInfoBy查询失败，可能是其他原因
                            # 检查是否是"已有交货单"的错误
                            if "已有交货单" in error_msg:
                                return {
                                    "success": False,
                                    "intent": intent,
                                    "message": f"订单 {vbeln} 已有交货单，无法再次创建交货单或进行ATP检查"
                                }
                            # 其他原因，返回更详细的错误
                            return {
                                "success": False,
                                "intent": intent,
                                "message": f"订单 {vbeln} 存在，但无法获取用于创建交货单的订单信息。可能原因：订单状态异常、缺少必要数据等。错误详情：{error_msg}"
                            }
                    except Exception as detail_e:
                        # 订单详情也查询不到，说明订单确实不存在
                        detail_error = str(detail_e)
                        return {
                            "success": False,
                            "intent": intent,
                            "message": f"订单 {vbeln} 不存在。请确认订单号是否正确，或订单是否已被删除。"
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
                    # 确保 order_info 中包含 vgbel 字段（销售订单号）
                    # 如果 vgbel 为空或不存在，使用 vbeln 设置它
                    if not order_info.get("vgbel"):
                        order_info["vgbel"] = vbeln
                    
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
                    # 解析错误信息，提取物料号、工厂、库存地点等信息
                    solution_info = _parse_error_and_get_solution(error_msg, vbeln)
                    
                    # 检查是否是库存不足的错误
                    if "库存不足" in error_msg or "可用库存" in error_msg:
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": error_msg,
                                "vbeln": vbeln,  # 销售订单号
                                "solution": solution_info.get("solution", ""),
                                "action": solution_info.get("action", {}),
                                "matnr": solution_info.get("matnr"),
                                "werks": solution_info.get("werks"),
                                "lgort": solution_info.get("lgort")
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": f"创建交货单失败：{error_msg}",
                                "vbeln": vbeln,  # 销售订单号
                                "solution": solution_info.get("solution", ""),
                                "action": solution_info.get("action", {})
                            }
                        }
            else:
                # 仅ATP检查 - 执行详细的ATP检查
                try:
                    # 先执行详细的ATP检查
                    atp_result = await sd_service.check_atp_detailed(order_info)
                    
                    if atp_result.get("success"):
                        # ATP检查通过，返回成功结果（包含详细检查信息）
                        # 不再自动创建交货单，由用户点击按钮手动创建
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "atp_check",
                                "message": f"ATP检查通过：订单 {vbeln} 的物料可用性检查完成，库存充足，可以创建交货单。",
                                "vbeln": vbeln,  # 销售订单号
                                "items": atp_result.get("items", [])  # 详细的物料检查结果
                            }
                        }
                    else:
                        # ATP检查失败，返回详细结果
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": atp_result.get("message", "ATP检查失败"),
                                "vbeln": vbeln,  # 销售订单号
                                "items": atp_result.get("items", [])
                            }
                        }
                except Exception as e:
                    error_msg = str(e)
                    
                    # 检查是否是服务连接错误
                    if "无法连接到" in error_msg or "ConnectError" in error_msg or "连接" in error_msg:
                        # 判断是哪个服务连接失败
                        if "sinocst-module-wm" in error_msg or "WM" in error_msg or "仓库" in error_msg:
                            return {
                                "success": False,
                                "intent": intent,
                                "message": f"无法连接到仓库管理服务（WM服务），无法执行ATP检查。请检查：\n1. WM服务是否已启动（端口9112）\n2. 服务地址配置是否正确\n3. 网络连接是否正常\n\n错误详情：{error_msg}"
                            }
                        else:
                            return {
                                "success": False,
                                "intent": intent,
                                "message": f"无法连接到后端服务，无法执行ATP检查。请检查服务是否正常运行。\n\n错误详情：{error_msg}"
                            }
                    
                    # 解析错误信息，提取物料号、工厂、库存地点等信息
                    solution_info = _parse_error_and_get_solution(error_msg, vbeln)
                    
                    # 检查是否是库存相关的错误（包括库存不足、未维护库存等）
                    if ("库存不足" in error_msg or "可用库存" in error_msg or "ATP" in error_msg 
                        or "未维护库存" in error_msg or "未维护" in error_msg):
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": error_msg,
                                "vbeln": vbeln,  # 销售订单号
                                "solution": solution_info.get("solution", ""),
                                "action": solution_info.get("action", {}),
                                "matnr": solution_info.get("matnr"),
                                "werks": solution_info.get("werks"),
                                "lgort": solution_info.get("lgort")
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "atp_check_failed",
                                "message": f"ATP检查失败：{error_msg}",
                                "vbeln": vbeln,  # 销售订单号
                                "solution": solution_info.get("solution", ""),
                                "action": solution_info.get("action", {})
                            }
                        }
        
        elif intent == "COPY_ORDER":
            # 根据指定订单复制创建新订单
            vbeln = _extract_order_number(query)
            if not vbeln:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供要复制的订单号，例如：根据订单VB2025000091复制并创建新订单"
                }
            
            try:
                # 获取源订单详情
                source_order_result = await sd_service.get_order_detail(vbeln)
                
                if source_order_result.get("code") != 200:
                    error_msg = source_order_result.get("msg", "获取订单详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"获取订单{vbeln}详情失败：{error_msg}"
                    }
                
                source_order = source_order_result.get("data")
                if not source_order:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"订单{vbeln}不存在或无法获取订单信息"
                    }
                
                # 检查源订单是否有行项目
                if not source_order.get("apList") or len(source_order.get("apList", [])) == 0:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"源订单{vbeln}没有行项目数据，无法复制创建新订单。请选择有行项目的订单进行复制。"
                    }
                
                # 复制订单数据
                new_order_data = _copy_order_data(source_order, query)
                
                # 如果指定了销售办事处关键词，查找并设置销售办事处
                if "_sales_office_keyword" in new_order_data:
                    keyword = new_order_data.pop("_sales_office_keyword")
                    sales_office = await sd_service.get_sales_office_by_name(keyword)
                    
                    if sales_office:
                        new_order_data["vkbur"] = sales_office.get("vkbur")
                        new_order_data["txnamSdb"] = sales_office.get("txnamSdb") or sales_office.get("vtext", "")
                        logger.info(f"已设置销售办事处为：{new_order_data['vkbur']} - {new_order_data.get('txnamSdb', '')}")
                    else:
                        logger.warning(f"未找到包含'{keyword}'的销售办事处，保持原订单的销售办事处")
                
                # 创建新订单
                create_result = await sd_service.create_sales_order(new_order_data)
                
                if create_result.get("code") == 200:
                    new_vbeln = create_result.get("data")
                    
                    if not new_vbeln:
                        logger.error(f"创建订单成功但未返回订单号，返回结果：{create_result}")
                        return {
                            "success": False,
                            "intent": intent,
                            "message": "创建订单成功，但未获取到订单号，请稍后查询订单列表确认。"
                        }
                    
                    # 获取新创建的订单详情
                    try:
                        new_order_detail = await sd_service.get_order_detail(new_vbeln)
                        order_data = new_order_detail.get("data") if new_order_detail.get("code") == 200 else None
                        
                        if not order_data:
                            logger.warning(f"订单 {new_vbeln} 创建成功，但获取订单详情失败：{new_order_detail}")
                            # 即使获取详情失败，也返回订单号
                            return {
                                "success": True,
                                "intent": intent,
                                "data": {
                                    "type": "order_created",
                                    "order": None,
                                    "message": f"基于订单{vbeln}复制创建新订单成功！新订单号：{new_vbeln}（订单详情获取失败，请稍后查看）",
                                    "vbeln": new_vbeln,
                                    "source_vbeln": vbeln
                                }
                            }
                        
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "order_created",
                                "order": order_data,
                                "message": f"基于订单{vbeln}复制创建新订单成功！新订单号：{new_vbeln}",
                                "vbeln": new_vbeln,
                                "source_vbeln": vbeln
                            }
                        }
                    except Exception as e:
                        logger.error(f"获取订单 {new_vbeln} 详情失败: {str(e)}", exc_info=True)
                        # 即使获取详情失败，也返回订单号
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "order_created",
                                "order": None,
                                "message": f"基于订单{vbeln}复制创建新订单成功！新订单号：{new_vbeln}（订单详情获取失败，请稍后查看）",
                                "vbeln": new_vbeln,
                                "source_vbeln": vbeln
                            }
                        }
                else:
                    error_msg = create_result.get("msg", "创建销售订单失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"创建销售订单失败：{error_msg}"
                    }
                    
            except Exception as e:
                logger.error(f"复制创建销售订单失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"复制创建销售订单时出错：{str(e)}"
                }
        
        elif intent == "CREATE_SALES_ORDER":
            # 创建销售订单（基于昨天的最后一个订单复制）
            try:
                # 获取昨天的最后一个订单
                yesterday_order = await sd_service.get_yesterday_last_order()
                
                if not yesterday_order:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": "未找到昨天的销售订单，无法复制创建新订单。"
                    }
                
                # 检查源订单是否有行项目
                if not yesterday_order.get("apList") or len(yesterday_order.get("apList", [])) == 0:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"源订单 {yesterday_order.get('vbeln', '')} 没有行项目数据，无法复制创建新订单。请选择有行项目的订单进行复制。"
                    }
                
                # 确保源订单有客户信息（如果没有，从 vbpa 表查询）
                if not yesterday_order.get("kunnrAgv") and not yesterday_order.get("kunnr"):
                    # 尝试从订单详情中获取客户信息
                    # get_order_detail 应该已经包含了客户信息，但如果还没有，我们需要确保它被设置
                    pass  # get_order_detail 应该已经包含了客户信息
                
                # 复制订单数据
                new_order_data = _copy_order_data(yesterday_order, query)
                
                # 如果指定了销售办事处关键词，查找并设置销售办事处
                if "_sales_office_keyword" in new_order_data:
                    keyword = new_order_data.pop("_sales_office_keyword")
                    sales_office = await sd_service.get_sales_office_by_name(keyword)
                    
                    if sales_office:
                        new_order_data["vkbur"] = sales_office.get("vkbur")
                        new_order_data["txnamSdb"] = sales_office.get("txnamSdb") or sales_office.get("vtext", "")
                        logger.info(f"已设置销售办事处为：{new_order_data['vkbur']} - {new_order_data.get('txnamSdb', '')}")
                    else:
                        logger.warning(f"未找到包含'{keyword}'的销售办事处，保持原订单的销售办事处")
                
                # 创建新订单
                create_result = await sd_service.create_sales_order(new_order_data)
                
                if create_result.get("code") == 200:
                    new_vbeln = create_result.get("data")
                    
                    if not new_vbeln:
                        logger.error(f"创建订单成功但未返回订单号，返回结果：{create_result}")
                        return {
                            "success": False,
                            "intent": intent,
                            "message": "创建订单成功，但未获取到订单号，请稍后查询订单列表确认。"
                        }
                    
                    # 获取新创建的订单详情
                    try:
                        new_order_detail = await sd_service.get_order_detail(new_vbeln)
                        order_data = new_order_detail.get("data") if new_order_detail.get("code") == 200 else None
                        
                        if not order_data:
                            logger.warning(f"订单 {new_vbeln} 创建成功，但获取订单详情失败：{new_order_detail}")
                            # 即使获取详情失败，也返回订单号
                            return {
                                "success": True,
                                "intent": intent,
                                "data": {
                                    "type": "order_created",
                                    "order": None,
                                    "message": f"销售订单创建成功！订单号：{new_vbeln}（订单详情获取失败，请稍后查看）",
                                    "vbeln": new_vbeln
                                }
                            }
                        
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "order_created",
                                "order": order_data,
                                "message": f"销售订单创建成功！订单号：{new_vbeln}",
                                "vbeln": new_vbeln
                            }
                        }
                    except Exception as e:
                        logger.error(f"获取订单 {new_vbeln} 详情失败: {str(e)}", exc_info=True)
                        # 即使获取详情失败，也返回订单号
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "order_created",
                                "order": None,
                                "message": f"销售订单创建成功！订单号：{new_vbeln}（订单详情获取失败，请稍后查看）",
                                "vbeln": new_vbeln
                            }
                        }
                else:
                    error_msg = create_result.get("msg", "创建销售订单失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"创建销售订单失败：{error_msg}"
                    }
                    
            except Exception as e:
                logger.error(f"创建销售订单失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"创建销售订单时出错：{str(e)}"
                }
        
        elif intent.startswith("NAVIGATE_") or "销售模块概览" in query or "页面跳转" in query or "跳转" in query:
            # 销售模块概览 - 返回可跳转的SD模块页面列表
            sd_pages = [
                {
                    "name": "销售订单列表",
                    "route": "order_list",
                    "path": "/sales/titleDetail",
                    "description": "查看所有销售订单",
                    "icon": "iconfont iconicon_list",
                    "sapCode": "VA05"
                },
                {
                    "name": "创建销售订单",
                    "route": "order_create",
                    "path": "/sales/createDetail",
                    "description": "创建新的销售订单",
                    "icon": "iconfont iconicon_doc",
                    "sapCode": "VA01"
                },
                {
                    "name": "修改销售订单",
                    "route": "order_edit",
                    "path": "/sales/createDetail",
                    "description": "修改现有销售订单",
                    "icon": "iconfont iconicon_edit",
                    "sapCode": "VA02"
                },
                {
                    "name": "显示销售订单",
                    "route": "order_display",
                    "path": "/sales/titleDetail",
                    "description": "查看销售订单详情",
                    "icon": "iconfont iconicon_view",
                    "sapCode": "VA03"
                },
                {
                    "name": "销售发票列表",
                    "route": "invoice_list",
                    "path": "/sales/invoice/list",
                    "description": "查看所有销售发票",
                    "icon": "iconfont iconicon_list",
                    "sapCode": "VF04"
                },
                {
                    "name": "创建销售发票",
                    "route": "invoice_create",
                    "path": "/sales/invoice/create",
                    "description": "创建新的销售发票",
                    "icon": "iconfont iconicon_doc",
                    "sapCode": "VF01"
                },
                {
                    "name": "显示销售发票",
                    "route": "invoice_detail",
                    "path": "/sales/invoice/display",
                    "description": "查看销售发票详情",
                    "icon": "iconfont iconicon_view",
                    "sapCode": "VF03"
                },
                {
                    "name": "交货单列表",
                    "route": "delivery_list",
                    "path": "/solution-order/list-solution-order",
                    "description": "查看所有交货单",
                    "icon": "iconfont iconicon_list",
                    "sapCode": "VL06G"
                },
                {
                    "name": "创建交货单",
                    "route": "delivery_create",
                    "path": "/solution-order/delivery",
                    "description": "创建新的交货单",
                    "icon": "iconfont iconicon_doc",
                    "sapCode": "VL01N"
                },
                {
                    "name": "凭证流",
                    "route": "document_flow",
                    "path": "/sales/document-flow",
                    "description": "查看销售订单凭证流",
                    "icon": "iconfont iconicon_doc",
                    "sapCode": "VA05"
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
                        "message": "以下是可跳转的销售模块页面，点击任意页面即可跳转：",
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
                        "5. 销售模块概览（例如：打开订单列表）"
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


def _parse_error_and_get_solution(error_msg: str, vbeln: str = None) -> Dict[str, Any]:
    """
    解析错误信息，提取关键信息并生成解决方案
    
    Args:
        error_msg: 错误信息
        vbeln: 订单号（可选）
    
    Returns:
        包含解决方案、跳转链接等信息的字典
    """
    solution_info = {
        "solution": "",
        "action": {},
        "matnr": None,
        "werks": None,
        "lgort": None
    }
    
    # 解析"未维护库存"错误
    # 格式：物料 M0001 在工厂 1001 库存地点 未维护库存！
    # 或：物料 M0001 在工厂 1001 库存地点 XXX 未维护库存！
    if "未维护库存" in error_msg:
        # 提取物料号（支持M0001、M-0001等格式）
        matnr_match = re.search(r'物料\s+([A-Z0-9\-]+)', error_msg)
        if matnr_match:
            matnr = matnr_match.group(1).strip()
            solution_info["matnr"] = matnr
        
        # 提取工厂（支持1001、1001等格式）
        werks_match = re.search(r'工厂\s+([A-Z0-9]+)', error_msg)
        if werks_match:
            werks = werks_match.group(1).strip()
            solution_info["werks"] = werks
        
        # 提取库存地点（可能为空，格式：库存地点 XXX 或 库存地点 未维护）
        # 先尝试提取有值的库存地点
        lgort_match = re.search(r'库存地点\s+([A-Z0-9]+)\s+未维护', error_msg)
        if lgort_match:
            lgort = lgort_match.group(1).strip()
            solution_info["lgort"] = lgort
        # 如果没有找到，说明库存地点可能为空或未指定
        
        # 生成解决方案
        solution_parts = [
            "该物料需要在物料主数据中维护工厂和库存地点的关系。"
        ]
        
        if solution_info["matnr"]:
            solution_parts.append(f"物料号：{solution_info['matnr']}")
        if solution_info["werks"]:
            solution_parts.append(f"工厂：{solution_info['werks']}")
        if solution_info["lgort"]:
            solution_parts.append(f"库存地点：{solution_info['lgort']}")
        
        solution_info["solution"] = "\n".join(solution_parts)
        
        # 生成跳转链接
        if solution_info["matnr"]:
            solution_info["action"] = {
                "label": "前往物料主数据维护",
                "path": "/masterdata/material/addMaterial/add",
                "query": {
                    "matnr": solution_info["matnr"],
                    "type": "edit"
                }
            }
        else:
            solution_info["action"] = {
                "label": "前往物料列表",
                "path": "/masterdata/material/list_material"
            }
    
    # 解析"库存不足"错误
    elif "库存不足" in error_msg or "可用库存" in error_msg:
        # 提取物料号
        matnr_match = re.search(r'物料\s+([A-Z0-9]+)', error_msg)
        if matnr_match:
            matnr = matnr_match.group(1)
            solution_info["matnr"] = matnr
        
        solution_info["solution"] = (
            "该物料的可用库存不足，无法满足订单需求。\n"
            "解决方案：\n"
            "1. 检查库存是否充足\n"
            "2. 如有需要，可以通过货物移动增加库存\n"
            "3. 或调整订单数量"
        )
        
        if solution_info["matnr"]:
            solution_info["action"] = {
                "label": "查看物料详情",
                "path": "/masterdata/material/addMaterial/add",
                "query": {
                    "matnr": solution_info["matnr"],
                    "type": "display"
                }
            }
        else:
            solution_info["action"] = {
                "label": "前往物料列表",
                "path": "/masterdata/material/list_material"
            }
    
    # 其他错误
    else:
        solution_info["solution"] = "请检查错误信息，或联系系统管理员。"
        solution_info["action"] = {
            "label": "返回首页",
            "path": "/wel/index"
        }
    
    return solution_info


def _copy_order_data(order_data: Dict[str, Any], query: str) -> Dict[str, Any]:
    """
    复制订单数据并修改销售办事处
    
    Args:
        order_data: 原始订单数据
        query: 用户查询（用于提取要修改的销售办事处）
    
    Returns:
        新的订单数据
    """
    import copy
    
    # 深拷贝订单数据
    new_order = copy.deepcopy(order_data)
    
    # 清空订单号，让系统自动生成
    new_order["vbeln"] = None
    
    # 清空日期相关字段，让系统使用当前日期
    from datetime import datetime
    today_str = datetime.now().strftime("%Y%m%d")
    new_order["erdat"] = None  # 创建日期，系统会自动设置为今天
    new_order["audat"] = today_str  # 凭证日期，设置为今天
    if "bstdk" in new_order:
        new_order["bstdk"] = None  # 客户参考日期，清空
    if "ketdat" in new_order:
        new_order["ketdat"] = None  # 请求交货日期，清空
    
    # 确保客户信息被正确复制
    # 如果源订单有 kunnr，但没有 kunnrAgv，则使用 kunnr 作为 kunnrAgv
    if not new_order.get("kunnrAgv") and new_order.get("kunnr"):
        new_order["kunnrAgv"] = new_order["kunnr"]
    
    # 如果源订单有 kunnrAgvName，但没有 kunnrAgv，尝试从名称中提取（这种情况较少）
    # 主要逻辑：如果源订单有 kunnrAgvName，说明有客户信息，应该也有 kunnrAgv
    
    # 如果源订单有 kunnrWev，保持它；否则使用 kunnrAgv 作为 kunnrWev（默认售达方和送达方相同）
    if not new_order.get("kunnrWev") and new_order.get("kunnrAgv"):
        new_order["kunnrWev"] = new_order["kunnrAgv"]
    
    # 如果源订单有 kunnrWevName，但没有 kunnrWev，使用 kunnrAgv 作为 kunnrWev
    if not new_order.get("kunnrWev") and new_order.get("kunnrAgv"):
        new_order["kunnrWev"] = new_order["kunnrAgv"]
    
    # 从查询中提取销售办事处信息
    query_lower = query.lower()
    sales_office_keyword = None
    
    if "华东" in query or "华东办事处" in query:
        sales_office_keyword = "华东"
    elif "华北" in query or "华北办事处" in query:
        sales_office_keyword = "华北"
    elif "华南" in query or "华南办事处" in query:
        sales_office_keyword = "华南"
    elif "西南" in query or "西南办事处" in query:
        sales_office_keyword = "西南"
    elif "西北" in query or "西北办事处" in query:
        sales_office_keyword = "西北"
    elif "华中" in query or "华中办事处" in query:
        sales_office_keyword = "华中"
    
    # 如果指定了销售办事处关键词，需要异步获取（这里先设置一个标记，由调用方处理）
    if sales_office_keyword:
        new_order["_sales_office_keyword"] = sales_office_keyword
    
    # 复制行项目数据（如果存在）
    if "apList" in new_order and new_order["apList"]:
        for item in new_order["apList"]:
            # 清空行项目号，让系统自动生成
            if "posnr" in item:
                item["posnr"] = None
    
    return new_order

