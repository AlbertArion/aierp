#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MM Agent AI查询接口
支持自然语言查询采购订单、采购申请、采购信息记录、物料凭证等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
import os
import json
import requests
from app.services.mm_service import MMService
from app.services.agent_message_service import AgentMessageService
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建MMService实例，并传递token和租户信息
def get_mm_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> MMService:
    """创建MMService实例，并传递认证token和租户信息"""
    service = MMService()
    
    # 优先从Authorization头获取token
    token = None
    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        else:
            token = authorization.strip()
    
    # 如果Authorization头没有token，尝试从Blade-Auth头获取
    if not token and blade_auth:
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()
        elif blade_auth.lower().startswith("crypto "):
            token = blade_auth.strip()
        else:
            token = blade_auth.strip()
    
    # 设置token到service
    if token:
        service.set_token(token)
    
    # 设置租户信息
    mandt = x_mandt
    if not mandt or mandt == "null" or mandt.strip() == "":
        mandt = x_tenant_id
    
    if mandt and mandt != "null" and mandt.strip() != "":
        service.set_mandt(mandt.strip())
    
    if x_tenant_id and x_tenant_id != "null" and x_tenant_id.strip() != "":
        service.set_tenant_id(x_tenant_id.strip())
    
    return service

# 依赖注入：创建AgentMessageService实例
def get_message_service() -> AgentMessageService:
    """创建AgentMessageService实例"""
    return AgentMessageService()

def _extract_purchase_order_number(text: str) -> Optional[str]:
    """从文本中提取采购订单号"""
    patterns = [
        r"(?:采购订单号|采购订单|订单号|EBELN|ebeln)[\s\-:：]?([A-Z0-9\-]+)",
        r"([A-Z]{2,4}[\-]?\d{8,})",
        r"([0-9]{10,})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            order_num = match.group(1).strip()
            if len(order_num) >= 8:
                return order_num
    
    return None

def _extract_purchase_requisition_number(text: str) -> Optional[str]:
    """从文本中提取采购申请号"""
    patterns = [
        r"(?:采购申请号|采购申请|申请号|BANFN|banfn)[\s\-:：]?([A-Z0-9\-]+)",
        r"([0-9]{10,})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            req_num = match.group(1).strip()
            if len(req_num) >= 8:
                return req_num
    
    return None

async def _identify_intent_with_llm(text: str) -> Dict[str, Any]:
    """
    使用LLM识别用户意图（智能解析）
    
    Returns:
        {
            "intent": "QUERY_ORDER_DETAIL",
            "confidence": 0.9,
            "extracted": {"ebeln": "4500000123", "banfn": None}
        }
    """
    # 检查是否启用LLM
    use_llm = os.getenv("USE_LLM_MM_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("MM_AGENT_LLM_MODEL", "qwen-max-latest")
    
    if not use_llm or not openai_api_key or not openai_base_url:
        return None
    
    try:
        system_prompt = """你是一个物料管理(MM)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. CREATE_PURCHASE_ORDER - 创建采购订单（为生产订单XXX的缺料物料创建采购订单、创建采购订单、为XXX创建采购订单等，注意：这是创建操作，不是查询）
2. QUERY_ORDER_LIST - 查询采购订单列表（查询所有订单、订单列表、显示订单等）
3. QUERY_ORDER_DETAIL - 查询采购订单详情（用户提到订单号、查看订单、订单详情等）
4. QUERY_REQUISITION_LIST - 查询采购申请列表（查询所有申请、申请列表等）
5. QUERY_REQUISITION_DETAIL - 查询采购申请详情（用户提到申请号、查看申请、申请详情等）
6. QUERY_INFO_RECORD_LIST - 查询采购信息记录列表
7. QUERY_INFO_RECORD_DETAIL - 查询采购信息记录详情
8. QUERY_MATERIAL_DOCUMENT_LIST - 查询物料凭证列表
9. QUERY_MATERIAL_DOCUMENT_DETAIL - 查询物料凭证详情
10. NAVIGATE_ORDER_DETAIL - 跳转到采购订单详情页面
11. NAVIGATE_ORDER_LIST - 跳转到采购订单列表页面
12. NAVIGATE_REQUISITION_DETAIL - 跳转到采购申请详情页面
13. NAVIGATE_REQUISITION_LIST - 跳转到采购申请列表页面
14. SMALLTALK - 闲聊或询问如何使用

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "ebeln": "采购订单号（如果提到）",
        "banfn": "采购申请号（如果提到）",
        "infnr": "采购信息记录号（如果提到）",
        "mblnr": "物料凭证号（如果提到）"
    },
    "reasoning": "简要说明识别理由"
}

注意：
- 采购订单号通常是10位数字
- 采购申请号通常是10位数字
- **如果用户提到"为生产订单XXX的缺料物料创建采购订单"、"创建采购订单"、"为XXX创建采购订单"、"为缺料物料创建采购订单"等，应该是CREATE_PURCHASE_ORDER，而不是QUERY_ORDER_LIST**
- **创建采购订单的意图优先级高于查询订单列表，如果同时提到"创建"和"采购订单"，应该识别为CREATE_PURCHASE_ORDER**
- 如果用户提到"查看订单XXX"、"订单XXX的详情"、"查询订单XXX"等，应该是QUERY_ORDER_DETAIL
- 如果只提到"订单列表"、"所有订单"等（没有提到"创建"），应该是QUERY_ORDER_LIST
- 优先提取订单号、申请号，即使表达不完整也要识别"""

        user_prompt = f"用户查询：{text}\n\n请识别意图并提取关键信息。"
        
        resp = requests.post(
            f"{openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": openai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 300
            },
            timeout=10
        )
        
        resp.raise_for_status()
        data = resp.json()
        completion = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 尝试解析JSON
        try:
            cleaned = completion.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
            if cleaned.endswith('```'):
                cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            cleaned = cleaned.strip()
            
            try:
                result = json.loads(cleaned)
                logger.info(f"LLM识别意图成功: {result}")
                return result
            except json.JSONDecodeError:
                brace_count = 0
                start_idx = cleaned.find('{')
                if start_idx >= 0:
                    for i in range(start_idx, len(cleaned)):
                        if cleaned[i] == '{':
                            brace_count += 1
                        elif cleaned[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_str = cleaned[start_idx:i+1]
                                result = json.loads(json_str)
                                logger.info(f"LLM识别意图成功（提取后）: {result}")
                                return result
        except json.JSONDecodeError as e:
            logger.warning(f"LLM返回格式不正确: {completion}, 错误: {e}")
        except Exception as e:
            logger.warning(f"解析LLM响应失败: {completion}, 错误: {e}")
        
        return None
        
    except Exception as e:
        logger.warning(f"LLM意图识别失败: {e}")
        return None

def _identify_intent(text: str) -> str:
    """
    识别用户意图（规则式匹配，作为备选方案）
    """
    text_lower = text.lower()
    
    # 创建采购订单意图（优先级最高，因为"创建"比"查询"更重要）
    if any(keyword in text_lower for keyword in ["创建采购订单", "创建订单", "为", "缺料物料"]):
        if any(keyword in text_lower for keyword in ["采购订单", "订单"]) or "缺料物料" in text_lower:
            return "CREATE_PURCHASE_ORDER"
    
    # 页面跳转意图
    if any(keyword in text_lower for keyword in ["跳转", "打开", "进入", "去", "导航"]):
        if "采购订单" in text_lower and "列表" in text_lower:
            return "NAVIGATE_ORDER_LIST"
        elif "采购订单" in text_lower and ("详情" in text_lower or "显示" in text_lower):
            return "NAVIGATE_ORDER_DETAIL"
        elif "采购申请" in text_lower and "列表" in text_lower:
            return "NAVIGATE_REQUISITION_LIST"
        elif "采购申请" in text_lower and ("详情" in text_lower or "显示" in text_lower):
            return "NAVIGATE_REQUISITION_DETAIL"
    
    # 采购订单查询意图
    if _extract_purchase_order_number(text):
        if any(keyword in text_lower for keyword in ["详情", "信息", "查看", "显示"]):
            return "QUERY_ORDER_DETAIL"
        else:
            return "QUERY_ORDER_DETAIL"
    
    if any(keyword in text_lower for keyword in ["采购订单", "订单"]):
        if any(keyword in text_lower for keyword in ["详情", "显示", "查看", "信息"]):
            return "QUERY_ORDER_DETAIL"
        elif any(keyword in text_lower for keyword in ["列表", "所有", "全部"]):
            return "QUERY_ORDER_LIST"
        else:
            return "QUERY_ORDER_LIST"
    
    # 采购申请查询意图
    if _extract_purchase_requisition_number(text):
        return "QUERY_REQUISITION_DETAIL"
    
    if any(keyword in text_lower for keyword in ["采购申请", "申请"]):
        if any(keyword in text_lower for keyword in ["详情", "显示", "查看", "信息"]):
            return "QUERY_REQUISITION_DETAIL"
        elif any(keyword in text_lower for keyword in ["列表", "所有", "全部"]):
            return "QUERY_REQUISITION_LIST"
        else:
            return "QUERY_REQUISITION_LIST"
    
    # 采购信息记录查询意图
    if any(keyword in text_lower for keyword in ["采购信息记录", "信息记录"]):
        return "QUERY_INFO_RECORD_LIST"
    
    # 物料凭证查询意图
    if any(keyword in text_lower for keyword in ["物料凭证", "凭证"]):
        return "QUERY_MATERIAL_DOCUMENT_LIST"
    
    # 默认：闲聊
    return "SMALLTALK"

async def _handle_smalltalk_with_llm(query: str, intent: str) -> Dict[str, Any]:
    """处理闲聊或超出能力范围的问题，使用LLM自动回答"""
    use_llm = os.getenv("USE_LLM_MM_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("MM_AGENT_LLM_MODEL", "qwen-max-latest")
    
    explanation = None
    
    if use_llm and openai_api_key and openai_base_url:
        try:
            system_prompt = """你是物料管理(MM)系统的智能助手。你的主要能力包括：
1. 查询采购订单列表和详情
2. 查询采购申请列表和详情
3. 查询采购信息记录
4. 查询物料凭证

当用户的问题不在你的能力范围内时，请友好地说明你能做什么，并给出一些示例。
用简洁、专业、友好的中文回答。不要编造具体的数据或表格。"""

            resp = requests.post(
                f"{openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": openai_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=15
            )
            
            resp.raise_for_status()
            data = resp.json()
            explanation = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            
            if explanation:
                logger.info(f"LLM自动回答成功，长度: {len(explanation)}")
            else:
                logger.warning("LLM返回空内容")
                
        except Exception as e:
            logger.warning(f"LLM自动回答失败: {e}")
    
    # 如果LLM失败或未启用，使用默认回答
    if not explanation:
        explanation = (
            "我是MM Agent，可以帮助您：\n"
            "1. 查询采购订单列表和详情（例如：查询采购订单列表、查看订单4500000123的详情）\n"
            "2. 查询采购申请列表和详情（例如：查询采购申请列表、查看申请4500000123的详情）\n"
            "3. 查询采购信息记录（例如：查询采购信息记录）\n"
            "4. 查询物料凭证（例如：查询物料凭证）\n\n"
            "请告诉我您需要什么帮助？"
        )
    
    return {
        "success": True,
        "intent": intent,
        "data": {
            "type": "text",
            "text": explanation
        },
        "message": explanation
    }

@router.post("/mm-agent/ai-query")
async def mm_ai_query(
    payload: Dict[str, Any],
    mm_service: MMService = Depends(get_mm_service),
    message_service: AgentMessageService = Depends(get_message_service),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> Dict[str, Any]:
    """
    MM模块AI查询接口
    
    支持的功能：
    1. 查询采购订单列表和详情
    2. 查询采购申请列表和详情
    3. 查询采购信息记录
    4. 查询物料凭证
    
    Request Body:
        {
            "query": "查询最近的采购订单"
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
        
        # 注意：不再在这里检查消息，消息会在用户打开对话时加载
        # 消息通过conversation_id关联到对话，用户打开对话时会自动加载
        
        if not query:
            raise HTTPException(status_code=400, detail="query不能为空")
        
        logger.info(f"收到MM Agent查询: {query}")
        
        # 识别意图：优先使用LLM，失败则使用规则匹配
        intent = None
        extracted = {}
        llm_result = await _identify_intent_with_llm(query)
        
        if llm_result and llm_result.get("intent"):
            intent = llm_result.get("intent")
            confidence = llm_result.get("confidence", 0.0)
            extracted = llm_result.get("extracted", {})
            logger.info(f"LLM识别意图: {intent}, 置信度: {confidence}, 提取信息: {extracted}")
            
            if confidence < 0.5:
                logger.warning(f"LLM置信度太低({confidence})，回退到规则匹配")
                intent = None
        
        # 如果LLM识别失败或置信度太低，使用规则匹配
        if not intent:
            intent = _identify_intent(query)
            logger.info(f"规则匹配识别意图: {intent}")
            
            # 使用规则提取订单号等信息
            if not extracted.get("ebeln"):
                extracted["ebeln"] = _extract_purchase_order_number(query)
            if not extracted.get("banfn"):
                extracted["banfn"] = _extract_purchase_requisition_number(query)
        
        # 根据意图处理
        if intent == "CREATE_PURCHASE_ORDER":
            # 创建采购订单
            context = payload.get("context", {})
            items = context.get("items", [])
            aufnr = context.get("aufnr", "")
            internal_aufnr = context.get("internal_aufnr", "")
            source_agent = context.get("source_agent", "pp-agent")
            conversation_id = payload.get("conversation_id")
            
            if not items or len(items) == 0:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "缺少物料信息，无法创建采购订单"
                }
            
            # 构建物料列表描述
            material_list = []
            for item in items:
                matnr = item.get("matnr", "")
                matnr_name = item.get("matnr_name") or item.get("maktx", "")
                need_qty = item.get("need_qty", 0)
                available_qty = item.get("actual_available_qty", 0)
                purchase_qty = max(0, need_qty - available_qty)
                meins = item.get("meins", "PC")
                
                if matnr_name:
                    material_list.append(f"物料 {matnr_name}({matnr}) 需要采购 {purchase_qty} {meins}")
                else:
                    material_list.append(f"物料 {matnr} 需要采购 {purchase_qty} {meins}")
            
            material_desc = "，".join(material_list)
            
            # 返回消息，提示用户需要在前端创建采购订单
            # 根据订单类型（生产订单或内部订单）生成不同的消息
            message = f"已收到创建采购订单请求。"
            if internal_aufnr:
                message += f"内部订单号：{internal_aufnr}。"
            elif aufnr:
                message += f"生产订单号：{aufnr}。"
            message += f"需要采购的物料：{material_desc}。"
            message += "请前往MM Agent前端页面创建采购订单，或使用'创建采购订单'功能。"
            
            # 将消息保存到 agent-message 系统，以便前端能够加载显示
            try:
                # 从context中获取sender_user_id（如果pp-agent传递了）
                # 如果没有，设置为None，这样所有用户都能看到这个消息
                receiver_user_id = context.get("sender_user_id")
                
                # 注意：由于pp-agent直接调用API，可能没有传递用户ID
                # 设置为None，让所有用户都能看到这个消息
                # 前端在加载消息时，会通过receiver_user_id匹配或NULL匹配来获取消息
                
                message_result = message_service.send_message(
                    sender_agent=source_agent,
                    receiver_agent="mm-agent",
                    message_type="CREATE_PURCHASE_ORDER_REQUEST",
                    content={
                        "action": "CREATE_PURCHASE_ORDER",
                        "data": {
                            "type": "create_purchase_order_request",
                            "items": items,
                            "aufnr": aufnr,
                            "internal_aufnr": internal_aufnr,
                            "source_agent": source_agent,
                            "material_desc": material_desc,
                            "message": message
                        }
                    },
                    sender_user_id=receiver_user_id,
                    receiver_user_id=receiver_user_id,  # 如果为None，所有用户都能看到（通过receive_messages的OR条件）
                    conversation_id=conversation_id,
                    priority="HIGH",
                    mandt=x_mandt,
                    tenant_id=x_tenant_id
                )
                logger.info(f"已保存创建采购订单消息到agent-message系统: messageId={message_result.get('messageId')}, conversationId={message_result.get('conversationId')}, receiver_user_id={receiver_user_id}")
            except Exception as e:
                logger.error(f"保存消息到agent-message系统失败: {e}", exc_info=True)
                # 即使保存失败，也返回响应
            
            return {
                "success": True,
                "intent": intent,
                "message": message,
                "data": {
                    "type": "create_purchase_order_request",
                    "items": items,
                    "aufnr": aufnr,
                    "internal_aufnr": internal_aufnr,
                    "source_agent": source_agent,
                    "material_desc": material_desc
                }
            }
        
        elif intent == "QUERY_ORDER_LIST":
            # 查询采购订单列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            params = {
                "current": current,
                "size": size
            }
            
            result = await mm_service.get_purchase_order_list(params=params)
            
            # 格式化响应
            mm_data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_list",
                    "orders": mm_data.get("records", []),
                    "total": mm_data.get("total", 0),
                    "current": mm_data.get("current", current),
                    "size": mm_data.get("size", size)
                }
            }
        
        elif intent == "QUERY_ORDER_DETAIL":
            # 查询采购订单详情
            ebeln = extracted.get("ebeln")
            if not ebeln:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供采购订单号，例如：查看订单4500000123的详情"
                }
            
            result = await mm_service.get_purchase_order_detail(ebeln)
            
            if result.get("code") == 200:
                order_data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "order_detail",
                        "order": order_data
                    }
                }
            else:
                return {
                    "success": False,
                    "intent": intent,
                    "message": result.get("msg", "查询采购订单详情失败")
                }
        
        elif intent == "QUERY_REQUISITION_LIST":
            # 查询采购申请列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            params = {
                "current": current,
                "size": size
            }
            
            result = await mm_service.get_purchase_requisition_list(params=params)
            
            # 格式化响应
            mm_data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "requisition_list",
                    "requisitions": mm_data.get("records", []),
                    "total": mm_data.get("total", 0),
                    "current": mm_data.get("current", current),
                    "size": mm_data.get("size", size)
                }
            }
        
        elif intent == "QUERY_REQUISITION_DETAIL":
            # 查询采购申请详情
            banfn = extracted.get("banfn")
            if not banfn:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供采购申请号，例如：查看申请4500000123的详情"
                }
            
            result = await mm_service.get_purchase_requisition_detail(banfn)
            
            if result.get("code") == 200:
                req_data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "requisition_detail",
                        "requisition": req_data
                    }
                }
            else:
                return {
                    "success": False,
                    "intent": intent,
                    "message": result.get("msg", "查询采购申请详情失败")
                }
        
        elif intent == "QUERY_INFO_RECORD_LIST":
            # 查询采购信息记录列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            params = {
                "current": current,
                "size": size
            }
            
            result = await mm_service.get_purchase_info_record_list(params=params)
            
            # 格式化响应
            mm_data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "info_record_list",
                    "info_records": mm_data.get("records", []),
                    "total": mm_data.get("total", 0),
                    "current": mm_data.get("current", current),
                    "size": mm_data.get("size", size)
                }
            }
        
        elif intent == "QUERY_MATERIAL_DOCUMENT_LIST":
            # 查询物料凭证列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            params = {
                "current": current,
                "size": size
            }
            
            result = await mm_service.get_material_document_list(params=params)
            
            # 格式化响应
            mm_data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "material_document_list",
                    "documents": mm_data.get("records", []),
                    "total": mm_data.get("total", 0),
                    "current": mm_data.get("current", current),
                    "size": mm_data.get("size", size)
                }
            }
        
        elif intent in ["NAVIGATE_ORDER_DETAIL", "NAVIGATE_ORDER_LIST", 
                        "NAVIGATE_REQUISITION_DETAIL", "NAVIGATE_REQUISITION_LIST"]:
            # 页面跳转意图
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "navigate",
                    "path": intent.replace("NAVIGATE_", "").lower()
                },
                "message": f"准备跳转到{intent.replace('NAVIGATE_', '')}"
            }
        
        else:
            # 默认：闲聊
            return await _handle_smalltalk_with_llm(query, intent)
            
    except Exception as e:
        logger.error(f"MM Agent查询失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"查询失败: {str(e)}"
        }

