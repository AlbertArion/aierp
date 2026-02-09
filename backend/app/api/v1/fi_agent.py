"""
FI Agent AI查询接口
支持自然语言查询会计凭证、月结流程、三大报表等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
import os
import json
import requests
from datetime import datetime
from app.services.fi_service import FIService
from app.services.agent_message_service import AgentMessageService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建FIService实例，并传递token和租户信息
def get_fi_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    accept_language: Optional[str] = Header(None, alias="Accept-Language")
) -> FIService:
    """创建FIService实例，并传递认证token和租户信息"""
    service = FIService()
    
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
    
    # 设置语言信息
    if accept_language:
        service.set_accept_language(accept_language)
        logger.info(f"设置Accept-Language到FI服务: {accept_language}")
    
    return service

def get_message_service() -> AgentMessageService:
    """创建AgentMessageService实例"""
    return AgentMessageService()

# ========== 辅助函数：提取信息 ==========

def _extract_document_number(text: str) -> Optional[str]:
    """
    从文本中提取凭证号（belnr）
    凭证号通常是10位数字
    
    Returns:
        凭证号，如果未找到则返回None
    """
    patterns = [
        r'(?:凭证号|凭证编号|会计凭证号)[\s:：]?(\d{10})',
        r'凭证\s*(\d{10})',
        r'\b(\d{10})\b',  # 10位数字
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]
    
    return None

def _extract_year_month(text: str) -> Optional[Dict[str, str]]:
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

def _extract_account_number(text: str) -> Optional[str]:
    """
    从文本中提取科目编号（saknr）
    
    Returns:
        科目编号，如果未找到则返回None
    """
    patterns = [
        r'(?:科目|科目编号|科目号)[\s:：]?([A-Z0-9]+)',
        r'科目\s*([A-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def _extract_company_code(text: str) -> Optional[str]:
    """
    从文本中提取公司代码（bukrs）
    公司代码通常是4位字符或数字
    
    Returns:
        公司代码，如果未找到则返回None
    """
    patterns = [
        r'(?:公司代码|公司编号|公司号)[\s:：]?([A-Z0-9]{4})',
        r'公司\s*([A-Z0-9]{4})',
        r'\b([A-Z0-9]{4})\b',  # 4位字符或数字
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

async def _identify_intent_with_llm(text: str) -> Dict[str, Any]:
    """
    使用LLM识别用户意图（智能解析）
    
    Returns:
        {
            "intent": "QUERY_DOCUMENT_LIST",
            "confidence": 0.9,
            "extracted": {"belnr": "1000000001", "gjahr": "2025", "monat": "01"}
        }
    """
    # 优先从配置服务读取，fallback到环境变量
    from app.services.config_service import ConfigService
    config_service = ConfigService()
    
    use_llm = config_service.is_llm_enabled("fi")
    if not use_llm:
        return None
    
    llm_config = config_service.get_llm_config("fi")
    openai_api_key = llm_config["api_key"]
    openai_base_url = llm_config["base_url"]
    openai_model = llm_config["model"]
    
    if not openai_api_key or not openai_base_url:
        return None
    
    try:
        system_prompt = """你是一个财务会计(FI)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_DOCUMENT_LIST - 查询会计凭证列表（查询凭证列表、所有凭证、凭证查询等）
2. QUERY_DOCUMENT_DETAIL - 查询会计凭证详情（查看凭证、凭证详情、凭证信息等）
3. CREATE_DOCUMENT - 创建会计凭证（录入凭证、创建凭证、新增凭证等）
4. UPDATE_DOCUMENT - 更新会计凭证（修改凭证、编辑凭证、更新凭证等）
5. DELETE_DOCUMENT - 删除会计凭证（删除凭证、作废凭证等）
6. RECEIVE_DOCUMENT_MESSAGE - 接收会计凭证消息（接收凭证消息、凭证消息接收等）
7. START_MONTH_END - 启动月结流程（启动月结、开始月结、执行月结等）
8. QUERY_MONTH_END_STATUS - 查询月结状态（月结状态、月结进度、月结情况等）
9. EXECUTE_MONTH_END_STEP - 执行单个月结步骤（执行月结步骤、运行月结步骤等，需要指定步骤代码）
10. CLOSE_MONTH - 关闭会计期间/自动月结（关闭期间、期间关闭、自动月结、执行所有步骤、执行全部步骤等）
11. QUERY_BALANCE_SHEET - 查询资产负债表（资产负债表、资产负债表查询等）
12. QUERY_PROFIT_LOSS - 查询利润表（利润表、损益表、利润表查询、损益表查询等）
13. QUERY_CASH_FLOW - 查询现金流量表（现金流量表、现金流量表查询等）
14. QUERY_ACCOUNT_BALANCE - 查询科目余额（科目余额、余额查询等）
15. QUERY_GENERAL_LEDGER - 查询总账（总账、总账查询、科目总账等）
16. QUERY_ACCOUNT_LIST - 查询科目列表（查询科目列表、所有科目、科目查询、科目主数据查询等）
17. QUERY_ACCOUNT_DETAIL - 查询科目详情（查看科目详情、科目信息、查看科目等，需要提供科目代码）
18. QUERY_PRODUCTION_SETTLEMENT - 查询生产订单结算凭证（生产订单结算、生产完工结算等）
19. QUERY_INTERNAL_ORDER_SETTLEMENT - 查询内部订单结算凭证（内部订单结算、内部订单结算凭证等）
20. SMALLTALK - 闲聊或询问如何使用

注意：新增的凭证生成流程（生产完工入库自动结算、内部订单结算等）通过业务单据自动生成，
可以通过查询凭证列表或凭证详情来查看这些自动生成的凭证。

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "belnr": "凭证号（如果提到，通常是10位数字）",
        "gjahr": "会计年度（如果提到，如2025）",
        "monat": "会计期间（如果提到，如01、02等）",
        "saknr": "科目编号（如果提到，用于查询科目详情或余额）",
        "account_code": "科目代码（如果提到，用于查询科目详情）",
        "account_name": "科目名称（如果提到，用于筛选科目列表）",
        "account_type": "科目类型（如果提到）",
        "status": "状态（如果提到，如启用、停用等）",
        "bukrs": "公司代码（如果提到）"
    },
    "reasoning": "简要说明识别理由"
}

注意：
- 凭证号通常是10位数字
- 会计年度是4位数字，如2025
- 会计期间是2位数字，如01、02等
- 如果用户提到"三大报表"、"财务报表"等，需要进一步判断是哪个报表
- 如果用户提到"月结"、"月结流程"等，需要判断是启动、查询状态还是执行步骤
- 如果用户提到"科目列表"、"所有科目"、"查询科目"等，应该识别为QUERY_ACCOUNT_LIST
- 如果用户提到"查看科目"、"科目详情"、"科目信息"等且提到科目代码，应该识别为QUERY_ACCOUNT_DETAIL
- 优先提取凭证号、年度、期间、科目编号、科目代码等信息，即使表达不完整也要识别
- 置信度要求：对于明确的意图（如包含凭证号的查询），置信度应该>=0.8；对于模糊的意图，置信度可以>=0.6"""

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
    
    # 三大报表查询
    if "资产负债表" in text_lower:
        return "QUERY_BALANCE_SHEET"
    if "利润表" in text_lower or "损益表" in text_lower:
        return "QUERY_PROFIT_LOSS"
    if "现金流量表" in text_lower:
        return "QUERY_CASH_FLOW"
    
    # 月结相关
    if "月结" in text_lower:
        if "自动月结" in text_lower or ("所有步骤" in text_lower and "执行" in text_lower) or ("全部步骤" in text_lower and "执行" in text_lower):
            return "CLOSE_MONTH"  # 自动月结 = 执行所有步骤 = 关闭期间
        elif "启动" in text_lower or "开始" in text_lower or "执行" in text_lower:
            return "START_MONTH_END"
        elif "状态" in text_lower or "进度" in text_lower or "情况" in text_lower:
            return "QUERY_MONTH_END_STATUS"
        elif "步骤" in text_lower:
            return "EXECUTE_MONTH_END_STEP"
        elif "关闭" in text_lower:
            return "CLOSE_MONTH"
        else:
            return "QUERY_MONTH_END_STATUS"  # 默认查询状态
    
    # 凭证相关
    if "凭证" in text_lower:
        if "创建" in text_lower or "录入" in text_lower or "新增" in text_lower:
            return "CREATE_DOCUMENT"
        elif "修改" in text_lower or "编辑" in text_lower or "更新" in text_lower:
            return "UPDATE_DOCUMENT"
        elif "删除" in text_lower or "作废" in text_lower:
            return "DELETE_DOCUMENT"
        elif "消息" in text_lower or "接收" in text_lower:
            return "RECEIVE_DOCUMENT_MESSAGE"
        elif "列表" in text_lower or "查询" in text_lower or "所有" in text_lower:
            return "QUERY_DOCUMENT_LIST"
        else:
            # 如果有凭证号，查询详情；否则查询列表
            if _extract_document_number(text):
                return "QUERY_DOCUMENT_DETAIL"
            return "QUERY_DOCUMENT_LIST"
    
    # 科目相关查询
    if "科目" in text_lower:
        if "详情" in text_lower or "信息" in text_lower or ("查看" in text_lower and _extract_account_number(text)):
            return "QUERY_ACCOUNT_DETAIL"
        elif "余额" in text_lower or ("余额" in text_lower and "科目" in text_lower):
            return "QUERY_ACCOUNT_BALANCE"
        elif "列表" in text_lower or "所有" in text_lower or "查询" in text_lower:
            return "QUERY_ACCOUNT_LIST"
        elif _extract_account_number(text):
            return "QUERY_ACCOUNT_DETAIL"
        else:
            return "QUERY_ACCOUNT_LIST"  # 默认查询科目列表
    
    # 科目余额查询（单独提到余额，但前面已经处理了科目相关的）
    if "余额" in text_lower:
        return "QUERY_ACCOUNT_BALANCE"
    
    # 总账查询
    if "总账" in text_lower:
        return "QUERY_GENERAL_LEDGER"
    
    # 默认返回凭证列表查询
    return "QUERY_DOCUMENT_LIST"

@router.post("/fi-agent/ai-query")
async def fi_ai_query(
    payload: Dict[str, Any],
    fi_service: FIService = Depends(get_fi_service),
    message_service: AgentMessageService = Depends(get_message_service),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    accept_language: Optional[str] = Header(None, alias="Accept-Language")
) -> Dict[str, Any]:
    """
    FI模块AI查询接口
    
    支持的功能：
    1. 查询会计凭证列表和详情
    2. 创建、更新、删除会计凭证
    3. 接收会计凭证消息
    4. 月结流程管理
    5. 三大报表查询（资产负债表、利润表、现金流量表）
    6. 科目余额和总账查询
    
    Request Body:
        {
            "query": "查询2025年1月的资产负债表"
        }
    
    Returns:
        {
            "success": true,
            "intent": "QUERY_BALANCE_SHEET",
            "data": {
                "type": "balance_sheet",
                "report": {...}
            }
        }
    """
    try:
        query = payload.get("query", "").strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="query不能为空")
        
        logger.info(f"收到FI Agent查询: {query}")
        
        # 使用AgentModeAdapter统一识别意图
        from app.utils.agent_mode_adapter import AgentModeAdapter
        adapter = AgentModeAdapter()
        intent_result = await adapter.identify_intent(query, "fi")
        
        # 处理未识别的情况
        if intent_result.get("unrecognized"):
            return {
                "success": False,
                "message": "抱歉，我没有识别到您的操作。请尝试使用以下方式：\n1. 使用关键词查询（如：查询凭证、查看订单等）\n2. 点击页面上的功能按钮进行操作",
                "suggestions": [
                    "查询凭证列表",
                    "查看凭证详情",
                    "创建凭证",
                    "查询科目列表",
                    "查询余额"
                ],
                "intent": None
            }
        
        intent = intent_result.get("intent")
        extracted = intent_result.get("extracted", {})
        mode = intent_result.get("mode", "rule")
        
        logger.info(f"识别意图: {intent}, 模式: {mode}, 提取信息: {extracted}")
        
        # 根据意图处理
        if intent == "QUERY_DOCUMENT_LIST":
            # 查询凭证列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            result = await fi_service.get_accounting_document_list(
                current=current,
                size=size,
                **{k: v for k, v in extracted.items() if v and k != "belnr"}
            )
            
            data = result.get("data", {})
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "document_list",
                    "documents": data.get("records", []),
                    "total": data.get("total", 0),
                    "current": data.get("current", current),
                    "size": data.get("size", size)
                }
            }
        
        elif intent == "QUERY_DOCUMENT_DETAIL":
            # 查询凭证详情
            belnr = extracted.get("belnr") or _extract_document_number(query)
            if not belnr:
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供凭证号，例如：查看凭证1000000001"
                    },
                    "message": "请提供凭证号"
                }
            
            try:
                result = await fi_service.get_accounting_document_detail(belnr)
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "查询凭证详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"查询凭证 {belnr} 详情失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "document_detail",
                        "document": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询凭证详情失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询凭证 {belnr} 详情时出错：{str(e)}"
                }
        
        elif intent == "CREATE_DOCUMENT":
            # 创建凭证
            document_data = payload.get("document_data")
            if not document_data:
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供凭证数据，例如：{\"header\": {...}, \"items\": [...]}"
                    },
                    "message": "请提供凭证数据"
                }
            
            try:
                result = await fi_service.create_accounting_document(document_data)
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "document_created",
                        "result": result.get("data")
                    },
                    "message": "凭证创建成功"
                }
            except Exception as e:
                logger.error(f"创建凭证失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"创建凭证时出错：{str(e)}"
                }
        
        elif intent == "UPDATE_DOCUMENT":
            # 更新凭证
            belnr = extracted.get("belnr") or _extract_document_number(query)
            document_data = payload.get("document_data")
            
            if not belnr or not document_data:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供凭证号和更新数据"
                }
            
            try:
                result = await fi_service.update_accounting_document(belnr, document_data)
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "document_updated",
                        "result": result.get("data")
                    },
                    "message": "凭证更新成功"
                }
            except Exception as e:
                logger.error(f"更新凭证失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"更新凭证时出错：{str(e)}"
                }
        
        elif intent == "DELETE_DOCUMENT":
            # 删除凭证
            belnr = extracted.get("belnr") or _extract_document_number(query)
            if not belnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供凭证号"
                }
            
            try:
                result = await fi_service.delete_accounting_document(belnr)
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "document_deleted",
                        "result": result.get("data")
                    },
                    "message": "凭证删除成功"
                }
            except Exception as e:
                logger.error(f"删除凭证失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"删除凭证时出错：{str(e)}"
                }
        
        elif intent == "RECEIVE_DOCUMENT_MESSAGE":
            # 接收凭证消息
            message_data = payload.get("message_data")
            if not message_data:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供消息数据"
                }
            
            try:
                result = await fi_service.receive_accounting_document_message(message_data)
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "message_received",
                        "result": result.get("data")
                    },
                    "message": "凭证消息接收成功"
                }
            except Exception as e:
                logger.error(f"接收凭证消息失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"接收凭证消息时出错：{str(e)}"
                }
        
        elif intent == "QUERY_MONTH_END_STATUS" or intent == "START_MONTH_END":
            # 查询FI月结状态或启动月结流程
            company_code = extracted.get("bukrs") or payload.get("companyCode") or payload.get("bukrs")
            if not company_code:
                company_code = _extract_company_code(query)
            
            gjahr = extracted.get("gjahr") or payload.get("fiscalYear") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("period") or payload.get("monat")
            
            if not gjahr or not monat:
                period = _extract_year_month(query)
                if period:
                    gjahr = period.get("gjahr")
                    monat = period.get("monat")
            
            # 如果缺少公司代码，使用默认值或返回错误
            if not company_code:
                company_code = "1000"  # 默认公司代码，实际应从配置获取
            
            if not gjahr or not monat:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供会计年度和期间，例如：查询2025年1月的月结状态"
                }
            
            try:
                fiscal_year = int(gjahr)
                period_int = int(monat) if monat.isdigit() else int(monat.lstrip('0'))
                
                result = await fi_service.get_fi_closing_process_status(
                    company_code=company_code,
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
                        "type": "fi_closing_process_status",
                        "companyCode": company_code,
                        "fiscalYear": fiscal_year,
                        "period": period_int,
                        "steps": backend_data.get("steps", {}),
                        "totalSteps": backend_data.get("totalSteps", 0),
                        "successCount": backend_data.get("successCount", 0),
                        "failCount": backend_data.get("failCount", 0),
                        "progress": backend_data.get("progress", 0)
                    }
                }
            except Exception as e:
                logger.error(f"查询FI月结状态失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询FI月结状态时出错：{str(e)}"
                }
        
        elif intent == "EXECUTE_MONTH_END_STEP":
            # 执行FI月结步骤
            company_code = extracted.get("bukrs") or payload.get("companyCode") or payload.get("bukrs")
            if not company_code:
                company_code = _extract_company_code(query)
            
            gjahr = extracted.get("gjahr") or payload.get("fiscalYear") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("period") or payload.get("monat")
            step_code = extracted.get("stepCode") or payload.get("stepCode") or payload.get("step_code")
            test_run = payload.get("testRun", False) if payload.get("testRun") is not None else False
            
            if not gjahr or not monat:
                period = _extract_year_month(query)
                if period:
                    gjahr = period.get("gjahr")
                    monat = period.get("monat")
            
            if not company_code:
                company_code = "1000"  # 默认公司代码
            
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
                    "打开": "OB52_OPEN",
                    "供应商": "FBL1N",
                    "总账": "FBL3N",
                    "客户": "FBL5N",
                    "分配": "KSU5",
                    "分摊": "KSV5",
                    "内部订单": "KO8G",
                    "在建工程": "AIBU",
                    "折旧": "AFAB",
                    "关闭": "OB52_CLOSE"
                }
                for keyword, code in step_map.items():
                    if keyword in text_lower:
                        step_code = code
                        break
                
                if not step_code:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": "请指定要执行的步骤代码，例如：执行2025年1月的供应商科目核对步骤"
                    }
            
            try:
                fiscal_year = int(gjahr)
                period_int = int(monat) if monat.isdigit() else int(monat.lstrip('0'))
                
                result = await fi_service.execute_fi_closing_step(
                    company_code=company_code,
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
                        "type": "fi_closing_step_executed",
                        "companyCode": company_code,
                        "fiscalYear": fiscal_year,
                        "period": period_int,
                        "stepCode": step_code,
                        "result": backend_data
                    },
                    "message": f"FI月结步骤 {step_code} 执行成功"
                }
            except Exception as e:
                logger.error(f"执行FI月结步骤失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"执行FI月结步骤时出错：{str(e)}"
                }
        
        elif intent == "CLOSE_MONTH":
            # 关闭会计期间（执行所有步骤，最后一步是关闭）
            company_code = extracted.get("bukrs") or payload.get("companyCode") or payload.get("bukrs")
            if not company_code:
                company_code = _extract_company_code(query)
            
            gjahr = extracted.get("gjahr") or payload.get("fiscalYear") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("period") or payload.get("monat")
            test_run = payload.get("testRun", False) if payload.get("testRun") is not None else False
            
            if not gjahr or not monat:
                period = _extract_year_month(query)
                if period:
                    gjahr = period.get("gjahr")
                    monat = period.get("monat")
            
            if not company_code:
                company_code = "1000"  # 默认公司代码
            
            if not gjahr or not monat:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供会计年度和期间"
                }
            
            try:
                fiscal_year = int(gjahr)
                period_int = int(monat) if monat.isdigit() else int(monat.lstrip('0'))
                
                # 执行所有月结步骤
                result = await fi_service.execute_all_fi_closing_steps(
                    company_code=company_code,
                    fiscal_year=fiscal_year,
                    period=period_int,
                    test_run=test_run
                )
                
                backend_data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "fi_closing_all_steps_executed",
                        "companyCode": company_code,
                        "fiscalYear": fiscal_year,
                        "period": period_int,
                        "testRun": test_run,
                        "result": backend_data
                    },
                    "message": "FI月结所有步骤执行完成"
                }
            except Exception as e:
                logger.error(f"执行FI月结所有步骤失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"关闭会计期间时出错：{str(e)}"
                }
        
        elif intent == "QUERY_BALANCE_SHEET":
            # 查询资产负债表
            gjahr = extracted.get("gjahr") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("monat")
            bukrs = extracted.get("bukrs") or payload.get("bukrs")
            
            if not gjahr:
                period = _extract_year_month(query)
                if period:
                    gjahr = period.get("gjahr")
                    monat = period.get("monat")
            
            if not gjahr:
                # 默认使用当前年度
                gjahr = str(datetime.now().year)
            
            try:
                result = await fi_service.get_balance_sheet(
                    gjahr=gjahr,
                    monat=monat,
                    bukrs=bukrs
                )
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "balance_sheet",
                        "report": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询资产负债表失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询资产负债表时出错：{str(e)}"
                }
        
        elif intent == "QUERY_PROFIT_LOSS":
            # 查询利润表
            gjahr = extracted.get("gjahr") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("monat")
            bukrs = extracted.get("bukrs") or payload.get("bukrs")
            
            if not gjahr:
                period = _extract_year_month(query)
                if period:
                    gjahr = period.get("gjahr")
                    monat = period.get("monat")
            
            if not gjahr:
                gjahr = str(datetime.now().year)
            
            try:
                result = await fi_service.get_profit_loss_statement(
                    gjahr=gjahr,
                    monat=monat,
                    bukrs=bukrs
                )
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "profit_loss",
                        "report": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询利润表失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询利润表时出错：{str(e)}"
                }
        
        elif intent == "QUERY_CASH_FLOW":
            # 查询现金流量表
            gjahr = extracted.get("gjahr") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("monat")
            bukrs = extracted.get("bukrs") or payload.get("bukrs")
            
            if not gjahr:
                period = _extract_year_month(query)
                if period:
                    gjahr = period.get("gjahr")
                    monat = period.get("monat")
            
            if not gjahr:
                gjahr = str(datetime.now().year)
            
            try:
                result = await fi_service.get_cash_flow_statement(
                    gjahr=gjahr,
                    monat=monat,
                    bukrs=bukrs
                )
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "cash_flow",
                        "report": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询现金流量表失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询现金流量表时出错：{str(e)}"
                }
        
        elif intent == "QUERY_ACCOUNT_BALANCE":
            # 查询科目余额
            saknr = extracted.get("saknr") or payload.get("saknr")
            gjahr = extracted.get("gjahr") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("monat")
            bukrs = extracted.get("bukrs") or payload.get("bukrs")
            
            if not saknr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供科目编号"
                }
            
            if not gjahr:
                gjahr = str(datetime.now().year)
            
            try:
                result = await fi_service.get_account_balance(
                    saknr=saknr,
                    gjahr=gjahr,
                    monat=monat,
                    bukrs=bukrs
                )
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "account_balance",
                        "balance": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询科目余额失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询科目余额时出错：{str(e)}"
                }
        
        elif intent == "QUERY_GENERAL_LEDGER":
            # 查询总账
            gjahr = extracted.get("gjahr") or payload.get("gjahr")
            monat = extracted.get("monat") or payload.get("monat")
            bukrs = extracted.get("bukrs") or payload.get("bukrs")
            saknr = extracted.get("saknr") or payload.get("saknr")
            
            if not gjahr:
                gjahr = str(datetime.now().year)
            
            try:
                result = await fi_service.get_general_ledger(
                    gjahr=gjahr,
                    monat=monat,
                    bukrs=bukrs,
                    saknr=saknr
                )
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "general_ledger",
                        "ledger": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询总账失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询总账时出错：{str(e)}"
                }
        
        elif intent == "QUERY_ACCOUNT_LIST":
            # 查询科目列表
            current = payload.get("current", 1)
            size = payload.get("size", 10)
            
            # 构建查询参数
            filters = {}
            if extracted.get("account_code"):
                filters["accountCode"] = extracted.get("account_code")
            if extracted.get("account_name"):
                filters["accountName"] = extracted.get("account_name")
            if extracted.get("account_type"):
                filters["accountType"] = extracted.get("account_type")
            if extracted.get("status"):
                filters["status"] = extracted.get("status")
            
            try:
                result = await fi_service.get_account_list(
                    current=current,
                    size=size,
                    **filters
                )
                
                data = result.get("data", {})
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "account_list",
                        "accounts": data.get("records", []),
                        "total": data.get("total", 0),
                        "current": data.get("current", current),
                        "size": data.get("size", size)
                    }
                }
            except Exception as e:
                logger.error(f"查询科目列表失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询科目列表时出错：{str(e)}"
                }
        
        elif intent == "QUERY_ACCOUNT_DETAIL":
            # 查询科目详情
            account_code = extracted.get("account_code") or extracted.get("saknr") or _extract_account_number(query)
            
            if not account_code:
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供科目代码，例如：查看科目1001"
                    },
                    "message": "请提供科目代码"
                }
            
            try:
                result = await fi_service.get_account_detail(account_code)
                
                if result.get("code") != 200:
                    error_msg = result.get("msg", "查询科目详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"查询科目 {account_code} 详情失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "account_detail",
                        "account": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询科目详情失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询科目 {account_code} 详情时出错：{str(e)}"
                }
        
        else:
            # 未知意图或闲聊
            return {
                "success": False,
                "intent": intent or "UNKNOWN",
                "data": {
                    "type": "text",
                    "text": "抱歉，我无法理解您的请求。\n\n支持的功能：\n1. 查询科目列表和详情\n2. 查询会计凭证列表和详情\n3. 创建、更新、删除会计凭证\n4. 接收会计凭证消息\n5. 月结流程管理\n6. 三大报表查询（资产负债表、利润表、现金流量表）\n7. 科目余额和总账查询"
                },
                "message": "无法识别意图"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FI Agent查询失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "intent": "ERROR",
            "message": f"查询失败：{str(e)}"
        }
