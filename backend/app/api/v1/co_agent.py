"""
CO Agent AI查询接口
支持自然语言查询成本对象、内部订单、CO-PA、CO月结流程等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
import os
import json
import requests
from datetime import datetime
from app.services.co_service import COService
from app.services.agent_message_service import AgentMessageService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建COService实例，并传递token和租户信息
def get_co_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> COService:
    """创建COService实例，并传递认证token和租户信息"""
    service = COService()
    
    # 优先从Authorization头获取token（bearer格式）
    token = None
    if authorization:
        logger.info(f"收到Authorization头: {authorization[:20]}...")
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            logger.info(f"从Authorization头提取token (长度: {len(token)})")
        else:
            logger.warning(f"Authorization头格式不正确: {authorization[:20]}...")
    
    # 如果Authorization头没有token，尝试从Blade-Auth头获取
    if not token and blade_auth:
        logger.info(f"收到Blade-Auth头: {blade_auth[:20]}...")
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()
            logger.info(f"从Blade-Auth头提取token (长度: {len(token)})")
        elif blade_auth.lower().startswith("crypto "):
            token = blade_auth.strip()
        else:
            token = blade_auth.strip()
            logger.info(f"从Blade-Auth头提取token（无前缀）(长度: {len(token)})")
    
    # 设置token到service
    if token:
        service.set_token(token)
    
    # 设置租户信息
    mandt = x_mandt
    if not mandt or mandt == "null" or mandt.strip() == "":
        mandt = x_tenant_id
    
    if mandt and mandt != "null" and mandt.strip() != "":
        service.set_mandt(mandt.strip())
        logger.info(f"设置mandt: {mandt.strip()}")
    
    if x_tenant_id and x_tenant_id != "null" and x_tenant_id.strip() != "":
        service.set_tenant_id(x_tenant_id.strip())
        logger.info(f"设置tenantId: {x_tenant_id.strip()}")
    
    return service

def get_message_service() -> AgentMessageService:
    """创建AgentMessageService实例"""
    return AgentMessageService()

# ========== 辅助函数：提取信息 ==========

def _extract_order_number(text: str) -> Optional[str]:
    """
    从文本中提取订单号（生产订单或内部订单）
    订单号通常是12位数字
    
    Returns:
        订单号，如果未找到则返回None
    """
    patterns = [
        r'(?:订单号|订单编号|生产订单号|内部订单号)[\s:：]?(\d{12})',
        r'订单\s*(\d{12})',
        r'\b(\d{12})\b',  # 12位数字
        r'\b(8\d{11})\b',  # 以8开头的12位数字（内部订单或生产订单）
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]
    
    return None

def _extract_controlling_area(text: str) -> Optional[str]:
    """
    从文本中提取控制范围（kokrs）
    
    Returns:
        控制范围，如果未找到则返回None
    """
    patterns = [
        r'(?:控制范围|控制区域|kokrs)[\s:：]?([A-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def _extract_year_period(text: str) -> Optional[Dict[str, str]]:
    """
    从文本中提取会计年度和期间
    
    Returns:
        {"gjahr": "2025", "monat": "01"} 或 None
    """
    # 匹配年份
    year_patterns = [
        r'(?:年度|年)[\s:：]?(\d{4})',
        r'(\d{4})年',
        r'20\d{2}',  # 2000-2099
    ]
    
    # 匹配月份
    month_patterns = [
        r'(?:期间|月份|月)[\s:：]?(\d{1,2})',
        r'(\d{1,2})月',
        r'第(\d{1,2})期',
    ]
    
    gjahr = None
    monat = None
    
    for pattern in year_patterns:
        match = re.search(pattern, text)
        if match:
            gjahr = match.group(1) if match.lastindex >= 1 else match.group(0)
            break
    
    for pattern in month_patterns:
        match = re.search(pattern, text)
        if match:
            monat = match.group(1) if match.lastindex >= 1 else match.group(0)
            if len(monat) == 1:
                monat = f"0{monat}"
            break
    
    if gjahr:
        return {"gjahr": gjahr, "monat": monat}
    
    return None

async def _identify_intent_with_llm(text: str) -> Dict[str, Any]:
    """
    使用LLM识别用户意图（智能解析）
    
    Returns:
        {
            "intent": "QUERY_COST_OBJECT_LIST",
            "confidence": 0.9,
            "extracted": {"orderNumber": "890000000001"}
        }
    """
    use_llm = os.getenv("USE_LLM_CO_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("CO_AGENT_LLM_MODEL", "qwen-max-latest")
    
    if not use_llm or not openai_api_key or not openai_base_url:
        return None
    
    try:
        system_prompt = """你是一个成本核算(CO)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_COST_OBJECT_LIST - 查询成本对象列表（查询成本对象、所有成本对象、成本对象查询等）
2. QUERY_COST_OBJECT_DETAIL - 查询成本对象详情（查看成本对象、成本对象详情、成本对象信息等）
3. SETTLE_COST_OBJECT - 成本对象结算（结算成本对象、生产订单结算、成本结算等）
4. QUERY_INTERNAL_ORDER_LIST - 查询内部订单列表（查询内部订单、所有内部订单、内部订单查询等）
5. QUERY_INTERNAL_ORDER_DETAIL - 查询内部订单详情（查看内部订单、内部订单详情、内部订单信息等）
6. EXPLODE_BOM_FOR_INTERNAL_ORDER - 内部订单BOM分解（BOM展开、BOM分解、展开BOM等）
7. SETTLE_INTERNAL_ORDER - 内部订单结算（结算内部订单、内部订单结算等）
8. QUERY_PA_REVENUE_LIST - 查询CO-PA销售收入列表（CO-PA销售收入、销售收入列表等）
9. QUERY_PA_COST_LIST - 查询CO-PA销售成本列表（CO-PA销售成本、销售成本列表等）
10. QUERY_CO_MONTH_END_STATUS - 查询CO月结状态（CO月结状态、CO月结进度、CO月结情况等）
11. EXECUTE_CO_MONTH_END_STEP - 执行单个CO月结步骤（执行CO月结步骤、运行CO月结步骤等，需要指定步骤代码）
12. EXECUTE_CO_MONTH_END_ALL_STEPS - 执行所有CO月结步骤/自动月结（执行所有步骤、自动月结、执行全部步骤等）
13. SMALLTALK - 闲聊或询问如何使用

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "orderNumber": "订单号（如果提到，通常是12位数字）",
        "controllingArea": "控制范围（如果提到）",
        "gjahr": "会计年度（如果提到，如2025）",
        "monat": "会计期间（如果提到，如01、02等）",
        "settlementTargetType": "结算目标类型（如果提到，如COST_CENTER-成本中心）",
        "settlementTarget": "结算目标（如果提到，如成本中心号或科目代码）"
    },
    "reasoning": "简要说明识别理由"
}

注意：
- 订单号通常是12位数字，以8开头
- 会计年度是4位数字，如2025
- 会计期间是2位数字，如01、02等
- 如果用户提到"月结"、"CO月结"等，需要判断是查询状态还是执行步骤
- 如果用户提到"结算"，需要区分是成本对象结算还是内部订单结算
- 置信度要求：对于明确的意图（如包含订单号的查询），置信度应该>=0.8；对于模糊的意图，置信度可以>=0.6"""

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
    识别用户意图（规则匹配）
    
    Returns:
        意图类型
    """
    text_lower = text.lower()
    
    # 成本对象相关
    if "成本对象" in text_lower:
        if "结算" in text_lower:
            return "SETTLE_COST_OBJECT"
        elif "列表" in text_lower or "查询" in text_lower or "所有" in text_lower:
            return "QUERY_COST_OBJECT_LIST"
        else:
            # 如果有订单号，查询详情；否则查询列表
            if _extract_order_number(text):
                return "QUERY_COST_OBJECT_DETAIL"
            return "QUERY_COST_OBJECT_LIST"
    
    # 内部订单相关
    if "内部订单" in text_lower:
        if "bom" in text_lower or "分解" in text_lower or "展开" in text_lower:
            return "EXPLODE_BOM_FOR_INTERNAL_ORDER"
        elif "结算" in text_lower:
            return "SETTLE_INTERNAL_ORDER"
        elif "列表" in text_lower or "查询" in text_lower or "所有" in text_lower:
            return "QUERY_INTERNAL_ORDER_LIST"
        else:
            # 如果有订单号，查询详情；否则查询列表
            if _extract_order_number(text):
                return "QUERY_INTERNAL_ORDER_DETAIL"
            return "QUERY_INTERNAL_ORDER_LIST"
    
    # CO-PA相关
    if "co-pa" in text_lower or "copa" in text_lower or "盈利性分析" in text_lower:
        if "收入" in text_lower:
            return "QUERY_PA_REVENUE_LIST"
        elif "成本" in text_lower:
            return "QUERY_PA_COST_LIST"
        else:
            return "QUERY_PA_REVENUE_LIST"  # 默认查询收入
    
    # CO月结相关
    if "月结" in text_lower and ("co" in text_lower or "成本" in text_lower):
        if "状态" in text_lower or "进度" in text_lower or "情况" in text_lower:
            return "QUERY_CO_MONTH_END_STATUS"
        elif "所有步骤" in text_lower or "全部步骤" in text_lower or "自动月结" in text_lower or "所有" in text_lower:
            return "EXECUTE_CO_MONTH_END_ALL_STEPS"
        elif "步骤" in text_lower:
            return "EXECUTE_CO_MONTH_END_STEP"
        else:
            return "QUERY_CO_MONTH_END_STATUS"  # 默认查询状态
    
    # 默认返回成本对象列表查询
    return "QUERY_COST_OBJECT_LIST"

@router.post("/co-agent/ai-query")
async def co_ai_query(
    payload: Dict[str, Any],
    co_service: COService = Depends(get_co_service),
    message_service: AgentMessageService = Depends(get_message_service),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> Dict[str, Any]:
    """
    CO模块AI查询接口
    
    支持的功能：
    1. 查询成本对象列表和详情
    2. 成本对象结算
    3. 查询内部订单列表和详情
    4. 内部订单BOM分解
    5. 内部订单结算
    6. 查询CO-PA销售收入/成本列表
    7. CO月结流程管理
    
    Request Body:
        {
            "query": "查询成本对象列表"
        }
    
    Returns:
        {
            "success": true,
            "intent": "QUERY_COST_OBJECT_LIST",
            "data": {
                "type": "cost_object_list",
                "cost_objects": [...],
                "total": 100
            }
        }
    """
    try:
        query = payload.get("query", "").strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="query不能为空")
        
        logger.info(f"收到CO Agent查询: {query}")
        
        # 识别意图：优先使用LLM，失败则使用规则匹配
        intent = None
        extracted = {}
        llm_result = await _identify_intent_with_llm(query)
        
        if llm_result and llm_result.get("intent"):
            intent = llm_result.get("intent")
            confidence = llm_result.get("confidence", 0.0)
            extracted = llm_result.get("extracted", {})
            logger.info(f"LLM识别意图: {intent}, 置信度: {confidence}, 提取信息: {extracted}")
            
            if confidence < 0.3:
                logger.warning(f"LLM置信度太低({confidence})，回退到规则匹配")
                intent = None
        
        # 如果LLM识别失败或置信度太低，使用规则匹配作为fallback
        if not intent:
            intent = _identify_intent(query)
            logger.info(f"规则匹配识别意图: {intent}")
            
            # 使用规则提取信息
            if not extracted.get("orderNumber"):
                extracted["orderNumber"] = _extract_order_number(query)
            if not extracted.get("controllingArea"):
                extracted["controllingArea"] = _extract_controlling_area(query)
            if not extracted.get("gjahr") or not extracted.get("monat"):
                period = _extract_year_period(query)
                if period:
                    extracted.update(period)
        
        # 根据意图处理
        if intent == "QUERY_COST_OBJECT_LIST":
            # 查询成本对象列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            result = await co_service.get_cost_object_list(
                current=current,
                size=size,
                order_number=extracted.get("orderNumber"),
                matnr=extracted.get("matnr"),
                werks=extracted.get("werks"),
            )
            
            # 后端返回格式：{"code": 200, "data": [...], "msg": "success"}
            # data 字段是一个列表，不是分页对象
            backend_data = result.get("data", [])
            
            # 确保 backend_data 是列表
            if not isinstance(backend_data, list):
                backend_data = []
            
            # 手动实现分页（因为后端不提供分页）
            total = len(backend_data)
            start_idx = (current - 1) * size
            end_idx = start_idx + size
            paginated_list = backend_data[start_idx:end_idx]
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "cost_object_list",
                    "cost_objects": paginated_list,
                    "total": total,
                    "current": current,
                    "size": size
                }
            }
        
        elif intent == "QUERY_COST_OBJECT_DETAIL":
            # 查询成本对象详情
            order_number = extracted.get("orderNumber") or _extract_order_number(query)
            if not order_number:
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供生产订单号，例如：查看成本对象890000000001"
                    },
                    "message": "请提供生产订单号"
                }
            
            try:
                result = await co_service.get_cost_object_detail(order_number)
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "查询成本对象详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"查询成本对象 {order_number} 详情失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "cost_object_detail",
                        "cost_object": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询成本对象详情失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询成本对象 {order_number} 详情时出错：{str(e)}"
                }
        
        elif intent == "SETTLE_COST_OBJECT":
            # 成本对象结算
            order_number = extracted.get("orderNumber") or _extract_order_number(query)
            if not order_number:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供生产订单号"
                }
            
            settlement_data = payload.get("settlement_data") or {}
            settlement_date = settlement_data.get("settlementDate") or extracted.get("settlementDate")
            settle_rule = settlement_data.get("settleRule") or extracted.get("settleRule")
            
            try:
                result = await co_service.settle_cost_object(
                    order_number=order_number,
                    settlement_date=settlement_date,
                    settle_rule=settle_rule
                )
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "成本对象结算失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"成本对象 {order_number} 结算失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "cost_object_settled",
                        "result": result.get("data")
                    },
                    "message": f"成本对象 {order_number} 结算成功"
                }
            except Exception as e:
                logger.error(f"成本对象结算失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"成本对象 {order_number} 结算时出错：{str(e)}"
                }
        
        elif intent == "QUERY_INTERNAL_ORDER_LIST":
            # 查询内部订单列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            result = await co_service.get_internal_order_list(
                current=current,
                size=size,
                order_number=extracted.get("orderNumber"),
                controlling_area=extracted.get("controllingArea"),
            )
            
            data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "internal_order_list",
                    "internal_orders": data.get("records", []),
                    "total": data.get("total", 0),
                    "current": data.get("current", current),
                    "size": data.get("size", size)
                }
            }
        
        elif intent == "QUERY_INTERNAL_ORDER_DETAIL":
            # 查询内部订单详情
            order_number = extracted.get("orderNumber") or _extract_order_number(query)
            if not order_number:
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供内部订单号，例如：查看内部订单808000000008"
                    },
                    "message": "请提供内部订单号"
                }
            
            try:
                controlling_area = extracted.get("controllingArea") or payload.get("controlling_area")
                result = await co_service.get_internal_order_detail(
                    order_number=order_number,
                    controlling_area=controlling_area
                )
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "查询内部订单详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"查询内部订单 {order_number} 详情失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "internal_order_detail",
                        "internal_order": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询内部订单详情失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询内部订单 {order_number} 详情时出错：{str(e)}"
                }
        
        elif intent == "EXPLODE_BOM_FOR_INTERNAL_ORDER":
            # 内部订单BOM分解
            order_number = extracted.get("orderNumber") or _extract_order_number(query)
            if not order_number:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供内部订单号"
                }
            
            try:
                bom_data = payload.get("bom_data") or {}
                matnr = bom_data.get("matnr") or extracted.get("matnr")
                werks = bom_data.get("werks") or extracted.get("werks")
                
                result = await co_service.explode_bom_tree_for_internal_order(
                    order_number=order_number,
                    matnr=matnr,
                    werks=werks
                )
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "BOM分解失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"内部订单 {order_number} BOM分解失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "bom_tree",
                        "bom_tree": result.get("data")
                    },
                    "message": f"内部订单 {order_number} BOM分解成功"
                }
            except Exception as e:
                logger.error(f"内部订单BOM分解失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"内部订单 {order_number} BOM分解时出错：{str(e)}"
                }
        
        elif intent == "SETTLE_INTERNAL_ORDER":
            # 内部订单结算
            order_number = extracted.get("orderNumber") or _extract_order_number(query)
            if not order_number:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供内部订单号"
                }
            
            try:
                settlement_data = payload.get("settlement_data") or {}
                controlling_area = settlement_data.get("controllingArea") or extracted.get("controllingArea")
                settlement_target_type = settlement_data.get("settlementTargetType") or extracted.get("settlementTargetType")
                settlement_target = settlement_data.get("settlementTarget") or extracted.get("settlementTarget")
                settlement_date = settlement_data.get("settlementDate") or extracted.get("settlementDate")
                
                result = await co_service.settle_internal_order(
                    order_number=order_number,
                    controlling_area=controlling_area,
                    settlement_target_type=settlement_target_type,
                    settlement_target=settlement_target,
                    settlement_date=settlement_date
                )
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "内部订单结算失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"内部订单 {order_number} 结算失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "internal_order_settled",
                        "result": result.get("data")
                    },
                    "message": f"内部订单 {order_number} 结算成功"
                }
            except Exception as e:
                logger.error(f"内部订单结算失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"内部订单 {order_number} 结算时出错：{str(e)}"
                }
        
        elif intent == "QUERY_PA_REVENUE_LIST":
            # 查询CO-PA销售收入列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            fiscal_year = extracted.get("gjahr") or payload.get("fiscal_year")
            period = extracted.get("monat") or payload.get("period")
            
            if not fiscal_year:
                period_info = _extract_year_period(query)
                if period_info:
                    fiscal_year = period_info.get("gjahr")
                    period = period_info.get("monat")
            
            if not fiscal_year:
                fiscal_year = str(datetime.now().year)
            
            try:
                result = await co_service.get_pa_revenue_list(
                    current=current,
                    size=size,
                    fiscal_year=fiscal_year,
                    period=period
                )
                
                data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "pa_revenue_list",
                        "revenues": data.get("records", []),
                        "total": data.get("total", 0),
                        "current": data.get("current", current),
                        "size": data.get("size", size)
                    }
                }
            except Exception as e:
                logger.error(f"查询CO-PA销售收入列表失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询CO-PA销售收入列表时出错：{str(e)}"
                }
        
        elif intent == "QUERY_PA_COST_LIST":
            # 查询CO-PA销售成本列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            fiscal_year = extracted.get("gjahr") or payload.get("fiscal_year")
            period = extracted.get("monat") or payload.get("period")
            
            if not fiscal_year:
                period_info = _extract_year_period(query)
                if period_info:
                    fiscal_year = period_info.get("gjahr")
                    period = period_info.get("monat")
            
            if not fiscal_year:
                fiscal_year = str(datetime.now().year)
            
            try:
                result = await co_service.get_pa_cost_list(
                    current=current,
                    size=size,
                    fiscal_year=fiscal_year,
                    period=period
                )
                
                data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "pa_cost_list",
                        "costs": data.get("records", []),
                        "total": data.get("total", 0),
                        "current": data.get("current", current),
                        "size": data.get("size", size)
                    }
                }
            except Exception as e:
                logger.error(f"查询CO-PA销售成本列表失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询CO-PA销售成本列表时出错：{str(e)}"
                }
        
        elif intent == "QUERY_CO_MONTH_END_STATUS":
            # 查询CO月结状态
            controlling_area = extracted.get("controllingArea") or payload.get("controllingArea") or payload.get("controlling_area")
            if not controlling_area:
                controlling_area = _extract_controlling_area(query)
            
            gjahr = extracted.get("gjahr") or payload.get("fiscalYear") or payload.get("fiscal_year")
            monat = extracted.get("monat") or payload.get("period")
            
            if not gjahr or not monat:
                period_info = _extract_year_period(query)
                if period_info:
                    gjahr = period_info.get("gjahr")
                    monat = period_info.get("monat")
            
            # 如果缺少控制范围，使用默认值或返回错误
            if not controlling_area:
                controlling_area = "1000"  # 默认控制范围，实际应从配置获取
            
            if not gjahr or not monat:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供会计年度和期间，例如：查询2025年1月的CO月结状态"
                }
            
            try:
                fiscal_year = int(gjahr)
                period_int = int(monat) if monat.isdigit() else int(monat.lstrip('0'))
                
                result = await co_service.get_co_closing_process_status(
                    controlling_area=controlling_area,
                    fiscal_year=fiscal_year,
                    period=period_int
                )
                
                backend_data = result.get("data", {})
                if not isinstance(backend_data, dict):
                    backend_data = {}
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "co_closing_process_status",
                        "controllingArea": controlling_area,
                        "fiscalYear": fiscal_year,
                        "period": period_int,
                        "stepStatusList": backend_data.get("stepStatusList", []),
                        "queryTime": backend_data.get("queryTime")
                    }
                }
            except Exception as e:
                logger.error(f"查询CO月结状态失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询CO月结状态时出错：{str(e)}"
                }
        
        elif intent == "EXECUTE_CO_MONTH_END_ALL_STEPS":
            # 执行所有CO月结步骤（自动月结）
            controlling_area = extracted.get("controllingArea") or payload.get("controllingArea") or payload.get("controlling_area")
            if not controlling_area:
                controlling_area = _extract_controlling_area(query)
            
            gjahr = extracted.get("gjahr") or payload.get("fiscalYear") or payload.get("fiscal_year")
            monat = extracted.get("monat") or payload.get("period")
            test_run = payload.get("testRun", False) if payload.get("testRun") is not None else False
            
            if not gjahr or not monat:
                period_info = _extract_year_period(query)
                if period_info:
                    gjahr = period_info.get("gjahr")
                    monat = period_info.get("monat")
            
            if not controlling_area:
                controlling_area = "1000"  # 默认控制范围
            
            if not gjahr or not monat:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供会计年度和期间"
                }
            
            try:
                fiscal_year = int(gjahr)
                period_int = int(monat) if monat.isdigit() else int(monat.lstrip('0'))
                
                result = await co_service.execute_all_co_closing_steps(
                    controlling_area=controlling_area,
                    fiscal_year=fiscal_year,
                    period=period_int,
                    test_run=test_run
                )
                
                backend_data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "co_closing_step_executed",
                        "controllingArea": controlling_area,
                        "fiscalYear": fiscal_year,
                        "period": period_int,
                        "result": backend_data,
                        "allSteps": True  # 标识是执行所有步骤
                    },
                    "message": f"CO自动月结执行完成（控制范围：{controlling_area}，年度：{fiscal_year}，期间：{period_int}）"
                }
            except Exception as e:
                logger.error(f"执行CO自动月结失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"执行CO自动月结时出错：{str(e)}"
                }
        
        elif intent == "EXECUTE_CO_MONTH_END_STEP":
            # 执行单个CO月结步骤
            controlling_area = extracted.get("controllingArea") or payload.get("controllingArea") or payload.get("controlling_area")
            if not controlling_area:
                controlling_area = _extract_controlling_area(query)
            
            gjahr = extracted.get("gjahr") or payload.get("fiscalYear") or payload.get("fiscal_year")
            monat = extracted.get("monat") or payload.get("period")
            step_code = extracted.get("stepCode") or payload.get("stepCode") or payload.get("step_code")
            test_run = payload.get("testRun", False) if payload.get("testRun") is not None else False
            
            if not gjahr or not monat:
                period_info = _extract_year_period(query)
                if period_info:
                    gjahr = period_info.get("gjahr")
                    monat = period_info.get("monat")
            
            if not controlling_area:
                controlling_area = "1000"  # 默认控制范围
            
            if not gjahr or not monat:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供会计年度和期间"
                }
            
            # 如果没有提供步骤代码，尝试从查询中提取
            if not step_code:
                # 可以从查询中提取步骤名称，然后映射到步骤代码
                text_lower = query.lower()
                step_map = {
                    "分配": "KSU5",
                    "分摊": "KSV5",
                    "内部订单": "KO8G",
                    "结算规则": "AIAB",
                    "在建工程": "AIBU"
                }
                for keyword, code in step_map.items():
                    if keyword in text_lower:
                        step_code = code
                        break
                
                if not step_code:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": "请指定要执行的步骤代码（KSU5/KSV5/KO8G/AIAB/AIBU），例如：执行2025年1月的实际分配步骤"
                    }
            
            try:
                fiscal_year = int(gjahr)
                period_int = int(monat) if monat.isdigit() else int(monat.lstrip('0'))
                
                result = await co_service.execute_co_closing_step(
                    controlling_area=controlling_area,
                    fiscal_year=fiscal_year,
                    period=period_int,
                    step_code=step_code,
                    test_run=test_run
                )
                
                backend_data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "co_closing_step_executed",
                        "controllingArea": controlling_area,
                        "fiscalYear": fiscal_year,
                        "period": period_int,
                        "stepCode": step_code,
                        "result": backend_data
                    },
                    "message": f"CO月结步骤 {step_code} 执行成功"
                }
            except Exception as e:
                logger.error(f"执行CO月结步骤失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"执行CO月结步骤时出错：{str(e)}"
                }
        
        else:
            # 未知意图或闲聊
            return {
                "success": False,
                "intent": intent or "UNKNOWN",
                "data": {
                    "type": "text",
                    "text": "抱歉，我无法理解您的请求。\n\n支持的功能：\n1. 查询成本对象列表和详情\n2. 成本对象结算\n3. 查询内部订单列表和详情\n4. 内部订单BOM分解\n5. 内部订单结算\n6. 查询CO-PA销售收入/成本列表\n7. CO月结流程管理"
                },
                "message": "无法识别意图"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CO Agent查询失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "intent": "ERROR",
            "message": f"查询失败：{str(e)}"
        }
