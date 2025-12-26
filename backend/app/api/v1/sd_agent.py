"""
SD Agent AI查询接口
支持自然语言查询销售订单、ATP检查、创建交货单等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
import os
import json
import requests
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

def _extract_delivery_number(text: str) -> Optional[str]:
    """
    从文本中提取交货单号（8位数字，可能以8开头）
    
    Returns:
        交货单号（如 "8000000048"），如果未找到则返回None
    """
    import re
    # 匹配8位数字，可能以8开头
    pattern = r'\b8\d{7}\b'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0]
    return None

def _extract_order_number(text: str) -> Optional[str]:
    """
    从文本中提取订单号
    支持多种格式：VB2025000059, VB2025000059, 订单号VB2025000059等
    """
    patterns = [
        r"(?:订单号|订单|SO|VBELN)[\s\-:]?([A-Z0-9\-]+)",
        r"(VB\d{10,})",  # VB开头的订单号（优先匹配）
        r"([A-Z]{2,4}[\-]?\d{8,})",
        r"([0-9]{10,})",  # 纯数字订单号
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            order_num = match.group(1).strip()
            # 过滤掉太短的数字（可能是年份等）
            if len(order_num) >= 8:
                logger.debug(f"从文本 '{text}' 中提取到订单号: {order_num} (使用模式: {pattern})")
                return order_num
    
    logger.debug(f"无法从文本 '{text}' 中提取订单号")
    return None

def _extract_production_order_number(text: str) -> Optional[str]:
    """
    从文本中提取生产订单号（aufnr）
    生产订单号通常是10位数字，如8900000103
    
    Returns:
        生产订单号（如 "8900000103"），如果未找到则返回None
    """
    import re
    # 匹配生产订单相关关键词后的数字
    patterns = [
        r'(?:生产订单|生产订单号|aufnr)[\s:：]?(\d{10})',
        r'生产订单\s*(\d{10})',
        r'\b(89\d{8}|8\d{9})\b',  # 10位数字，通常以8或89开头
        r'\b(\d{10})\b',  # 10位数字（通用匹配）
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            # 返回第一个匹配的10位数字
            for match in matches:
                if len(match) == 10:
                    return match
    
    return None

def _extract_internal_order_number(text: str) -> Optional[str]:
    """
    从文本中提取内部订单号（aufnr）
    内部订单号通常是12位数字，如808000000008
    
    Returns:
        内部订单号（如 "808000000008"），如果未找到则返回None
    """
    import re
    # 匹配内部订单相关关键词后的数字
    patterns = [
        r'(?:内部订单|内部订单号)[\s:：]?(\d{12})',
        r'内部订单\s*(\d{12})',
        r'\b(808\d{9})\b',  # 12位数字，以808开头（内部订单编号范围）
        r'\b(\d{12})\b',  # 12位数字（通用匹配）
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            # 返回第一个匹配的12位数字
            for match in matches:
                if len(match) == 12:
                    return match
    
    return None

async def _identify_intent_with_llm(text: str) -> Dict[str, Any]:
    """
    使用LLM识别用户意图（智能解析）
    
    Returns:
        {
            "intent": "QUERY_ORDER_DETAIL",
            "confidence": 0.9,
            "extracted": {"vbeln": "VB2025000059", "delivery_vbeln": None}
        }
    """
    # 检查是否启用LLM
    use_llm = os.getenv("USE_LLM_SD_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("SD_AGENT_LLM_MODEL", "qwen-max-latest")
    
    if not use_llm or not openai_api_key or not openai_base_url:
        return None
    
    try:
        system_prompt = """你是一个销售与分销(SD)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_ORDER_LIST - 查询销售订单列表（查询所有订单、订单列表、显示订单等）
2. QUERY_ORDER_DETAIL - 查询销售订单详情（用户提到订单号、查看订单、订单详情等）
3. NAVIGATE_ORDER_DETAIL - 跳转到订单详情页面（跳转、打开、进入订单详情等）
4. NAVIGATE_ORDER_LIST - 跳转到订单列表页面（跳转到订单列表等）
5. NAVIGATE_ORDER_EDIT - 跳转到订单编辑页面（修改、编辑订单等）
6. ATP_CHECK - 销售订单ATP物料可用性检查（检查销售订单的atp、可用性、库存检查、物料可用、库存够等，注意：这是针对销售订单的）
7. CHECK_PRODUCTION_ORDER_MATERIAL - 生产订单物料可用性检查（齐套性检查）（检查生产订单的物料可用性、齐套性检查等，注意：这是针对生产订单的，不是销售订单）
8. CHECK_INTERNAL_ORDER_MATERIAL - 内部订单物料可用性检查（齐套性检查）（检查内部订单的物料可用性、齐套性检查等，注意：这是针对内部订单的，内部订单号通常是12位数字，如808000000008）
9. CREATE_DELIVERY - 创建交货单（创建交货单、生成交货单、自动交货、交货等）
10. POST_DELIVERY - 交货单过账（过账、发货过账、交货单过账等）
11. CREATE_INVOICE - 创建发票（开票、创建发票、生成发票等）
12. COPY_ORDER - 复制订单（复制订单、基于订单创建等）
13. CREATE_SALES_ORDER - 创建销售订单（创建销售订单、基于昨天的最后一个订单复制等）
14. NAVIGATE_INVOICE - 跳转到发票页面
15. NAVIGATE_DELIVERY - 跳转到交货单页面
16. NAVIGATE_DOCUMENT_FLOW - 跳转到单据流页面
17. QUERY_INTERNAL_ORDER - 查询内部订单详情（查看内部订单、内部订单详情、内部订单信息等，内部订单号通常是12位数字，如808000000008）
18. SMALLTALK - 闲聊或询问如何使用

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "vbeln": "销售订单号（如果提到）",
        "delivery_vbeln": "交货单号（如果提到，通常是8位数字，可能以8开头）",
        "invoice_vbeln": "发票号（如果提到）",
        "aufnr": "生产订单号（如果提到，通常是10位数字，如8900000103）",
        "internal_aufnr": "内部订单号（如果提到，通常是12位数字，如808000000008）",
        "sales_group": "销售组名称（如果提到，如'经销商销售组'、'直销组'等）",
        "sales_office": "销售办事处名称（如果提到，如'华东'、'华北'、'华南'、'西南'、'西北'、'华中'等）"
    },
    "reasoning": "简要说明识别理由"
}

注意：
- 销售订单号通常是VB开头+数字，或纯数字（10位以上）
- 交货单号通常是8位数字，可能以8开头（如8000000048）
- 发票号通常是10位数字
- 生产订单号通常是10位数字，如8900000103（注意区分：生产订单号是10位数字，销售订单号可能也是10位，但通常有VB前缀或上下文表明是销售订单）
- **内部订单号通常是12位数字，如808000000008**（以808开头，用于内部成本核算）
- **销售组名称**：如果用户提到"销售组改为XXX"、"改为XXX销售组"等，提取XXX作为sales_group
- **销售办事处名称**：如果用户提到"华东"、"华北"、"华南"、"西南"、"西北"、"华中"等，提取对应的销售办事处名称作为sales_office
- 如果用户提到"查看订单XXX"、"订单XXX的详情"、"查询订单XXX"等，应该是QUERY_ORDER_DETAIL
- 如果用户提到"跳转到订单XXX"、"打开订单XXX"等，应该是NAVIGATE_ORDER_DETAIL
- 如果只提到"订单列表"、"所有订单"等，应该是QUERY_ORDER_LIST
- **如果用户提到"内部订单"，应该识别为 QUERY_INTERNAL_ORDER，并将订单号提取为internal_aufnr**
- **重要区分**：
  * 如果提到"生产订单"的"物料可用性"、"齐套性检查"等，应该识别为 CHECK_PRODUCTION_ORDER_MATERIAL，并将订单号提取为aufnr
  * 如果提到"内部订单"的"物料可用性"、"齐套性检查"等，应该识别为 CHECK_INTERNAL_ORDER_MATERIAL，并将订单号提取为internal_aufnr
  * 如果提到"销售订单"或仅提到"订单"的"ATP"、"可用性检查"等，应该识别为 ATP_CHECK，并将订单号提取为vbeln
  * 如果同时提到"生产订单"和"物料可用性"，必须识别为 CHECK_PRODUCTION_ORDER_MATERIAL，而不是 ATP_CHECK
  * 如果同时提到"内部订单"和"物料可用性"或"齐套性检查"，必须识别为 CHECK_INTERNAL_ORDER_MATERIAL，而不是 QUERY_INTERNAL_ORDER
  * 如果仅提到"内部订单"（没有提到齐套性检查），应该识别为 QUERY_INTERNAL_ORDER，并将订单号提取为internal_aufnr
- 优先提取订单号、交货单号、发票号、生产订单号、内部订单号、销售组名称，即使表达不完整也要识别
- **置信度要求**：对于明确的意图（如包含订单号的查询），置信度应该>=0.8；对于模糊的意图，置信度可以>=0.6"""

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
                "temperature": 0.1,  # 降低温度以提高准确性
                "max_tokens": 300
            },
            timeout=10
        )
        
        resp.raise_for_status()
        data = resp.json()
        completion = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 尝试解析JSON
        try:
            # 先去掉markdown代码块标记（```json 和 ```）
            cleaned = completion.strip()
            if cleaned.startswith('```'):
                # 去掉开头的 ```json 或 ```
                cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
            if cleaned.endswith('```'):
                # 去掉结尾的 ```
                cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            cleaned = cleaned.strip()
            
            # 提取JSON部分（使用更强大的正则表达式，支持嵌套）
            # 先尝试直接解析整个cleaned字符串
            try:
                result = json.loads(cleaned)
                logger.info(f"LLM识别意图成功: {result}")
                return result
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取JSON对象（支持嵌套）
                # 使用平衡括号匹配
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
        elif any(keyword in text_lower for keyword in ["过账", "发货过账", "交货单过账", "过账交货单"]):
            return "POST_DELIVERY"
        elif any(keyword in text_lower for keyword in ["开票", "创建发票", "生成发票", "发票"]):
            return "CREATE_INVOICE"
        else:
            # 如果提到订单号但没有明确意图，默认查询详情
            return "QUERY_ORDER_DETAIL"
    
    # ATP检查
    if any(keyword in text_lower for keyword in ["atp", "可用性检查", "库存检查", "物料可用性", "检查库存"]):
        return "ATP_CHECK"
    
    # 创建交货单
    if any(keyword in text_lower for keyword in ["创建交货单", "生成交货单", "自动创建交货单", "创建发货单"]):
        return "CREATE_DELIVERY"
    
    # 交货单过账
    if any(keyword in text_lower for keyword in ["过账", "发货过账", "交货单过账", "过账交货单", "为这个外向交货单过账"]):
        return "POST_DELIVERY"
    
    # 创建发票
    if any(keyword in text_lower for keyword in ["开票", "创建发票", "生成发票", "为这个外向交货单开票", "为交货单开票"]):
        return "CREATE_INVOICE"
    
    # 创建销售订单（基于昨天的最后一个订单复制）
    if any(keyword in text_lower for keyword in ["创建销售订单", "复制订单", "基于", "昨天的", "最后一个订单"]):
        if "复制" in text_lower or "基于" in text_lower:
            return "CREATE_SALES_ORDER"
    
    # 默认：闲聊
    return "SMALLTALK"

async def _handle_smalltalk_with_llm(query: str, intent: str) -> Dict[str, Any]:
    """
    处理闲聊或超出能力范围的问题，使用LLM自动回答
    
    Args:
        query: 用户查询
        intent: 识别的意图（通常是SMALLTALK）
        
    Returns:
        包含LLM回答的响应
    """
    # 检查是否启用LLM
    use_llm = os.getenv("USE_LLM_SD_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("SD_AGENT_LLM_MODEL", "qwen-max-latest")
    
    explanation = None
    
    if use_llm and openai_api_key and openai_base_url:
        try:
            system_prompt = """你是销售与分销(SD)系统的智能助手。你的主要能力包括：
1. 查询销售订单列表和详情
2. ATP物料可用性检查
3. 自动创建交货单
4. 交货单过账
5. 创建发票
6. 复制订单
7. 创建销售订单

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
            "我是SD Agent，可以帮助您：\n"
            "1. 查询销售订单列表和详情（例如：查询销售订单列表、查看订单VB2025000059的详情）\n"
            "2. ATP物料可用性检查（例如：检查订单VB2025000059的ATP、检查库存）\n"
            "3. 创建交货单（例如：为订单VB2025000059创建交货单）\n"
            "4. 交货单过账（例如：为交货单8000000048过账）\n"
            "5. 创建发票（例如：为交货单8000000048开票）\n"
            "6. 复制订单（例如：复制订单VB2025000059）\n\n"
            "请告诉我您需要什么帮助？"
        )
    
    return {
        "success": True,
        "intent": intent,
        "data": {
            "type": "text",
            "text": explanation
        },
        "message": explanation  # 将LLM的回答也放在message字段，方便前端直接显示
    }

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
        
        # 识别意图：优先使用LLM，失败则使用规则匹配
        intent = None
        extracted = {}
        llm_result = await _identify_intent_with_llm(query)
        
        if llm_result and llm_result.get("intent"):
            # LLM识别成功
            intent = llm_result.get("intent")
            confidence = llm_result.get("confidence", 0.0)
            extracted = llm_result.get("extracted", {})
            logger.info(f"LLM识别意图: {intent}, 置信度: {confidence}, 提取信息: {extracted}")
            
            # 如果置信度太低（<0.3），回退到规则匹配
            if confidence < 0.3:
                logger.warning(f"LLM置信度太低({confidence})，回退到规则匹配")
                intent = None
        
        # 如果LLM识别失败或置信度太低，使用规则匹配作为fallback
        if not intent:
            intent = _identify_intent(query)
            logger.info(f"规则匹配识别意图: {intent}")
            
            # 使用规则提取订单号等信息（作为LLM提取的补充）
            if not extracted.get("vbeln"):
                extracted["vbeln"] = _extract_order_number(query)
            if not extracted.get("delivery_vbeln"):
                extracted["delivery_vbeln"] = _extract_delivery_number(query)
            if not extracted.get("aufnr"):
                extracted["aufnr"] = _extract_production_order_number(query)
            if not extracted.get("internal_aufnr"):
                extracted["internal_aufnr"] = _extract_internal_order_number(query)
        
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
            # 优先使用LLM提取的订单号，否则使用规则提取，最后尝试从上下文获取
            vbeln = extracted.get("vbeln") or _extract_order_number(query) or payload.get("context", {}).get("vbeln")
            if not vbeln:
                # 如果没有订单号，返回友好提示，建议用户提供订单号或查询订单列表
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供销售订单号，例如：查看订单VB2025000059\n\n或者您可以：\n1. 查询销售订单列表（例如：查询销售订单列表）\n2. 查看最近的订单"
                    },
                    "message": "请提供销售订单号，例如：查看订单VB2025000059"
                }
            
            try:
                result = await sd_service.get_order_detail(vbeln)
            
                # 检查订单是否存在
                if result.get("code") != 200:
                    error_msg = result.get("msg", "查询订单详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"查询订单 {vbeln} 详情失败：{error_msg}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "order_detail",
                        "order": result.get("data")
                    }
                }
            except Exception as e:
                logger.error(f"查询订单详情失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"查询订单 {vbeln} 详情时出错：{str(e)}"
                }
        
        elif intent == "QUERY_INTERNAL_ORDER":
            # 查询内部订单详情
            # 优先使用LLM提取的内部订单号，否则使用规则提取
            internal_aufnr_from_llm = extracted.get("internal_aufnr")
            # 处理LLM返回空字符串的情况
            if internal_aufnr_from_llm and isinstance(internal_aufnr_from_llm, str) and internal_aufnr_from_llm.strip():
                internal_aufnr = internal_aufnr_from_llm.strip()
            else:
                # LLM未提取到，尝试使用规则提取
                internal_aufnr = _extract_internal_order_number(query)
            
            # 如果还是没有订单号，返回友好提示
            if not internal_aufnr or (isinstance(internal_aufnr, str) and not internal_aufnr.strip()):
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": "请提供内部订单号，例如：查看内部订单808000000008\n\n内部订单号通常是12位数字，以808开头。"
                    },
                    "message": "请提供内部订单号，例如：查看内部订单808000000008"
                }
            
            try:
                result = await sd_service.get_internal_order_detail(internal_aufnr)
                
                # 检查订单是否存在
                if result.get("code") != 200:
                    error_msg = result.get("msg", "查询内部订单详情失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "text",
                            "text": f"查询内部订单 {internal_aufnr} 失败：{error_msg}"
                        },
                        "message": f"查询内部订单 {internal_aufnr} 失败：{error_msg}"
                    }
                
                order_data = result.get("data")
                if not order_data:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "text",
                            "text": f"未找到内部订单 {internal_aufnr}"
                        },
                        "message": f"未找到内部订单 {internal_aufnr}"
                    }
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "internal_order_detail",
                        "order": order_data,
                        "aufnr": internal_aufnr
                    },
                    "message": f"查询内部订单 {internal_aufnr} 成功"
                }
            except Exception as e:
                logger.error(f"查询内部订单详情失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "data": {
                        "type": "text",
                        "text": f"查询内部订单 {internal_aufnr} 时出错：{str(e)}"
                    },
                    "message": f"查询内部订单 {internal_aufnr} 时出错：{str(e)}"
                }
        
        elif intent == "ATP_CHECK" or intent == "CREATE_DELIVERY":
            # ATP检查或创建交货单
            # 优先使用LLM提取的订单号，否则使用规则提取，最后尝试从上下文获取
            vbeln = extracted.get("vbeln") or _extract_order_number(query)
            
            # 如果还没有订单号，尝试从请求的上下文信息中获取
            if not vbeln:
                context = payload.get("context", {})
                vbeln = context.get("vbeln")
                if vbeln:
                    logger.info(f"从上下文获取订单号: {vbeln}")
            
            if not vbeln:
                # 根据意图区分提示文案
                if intent == "CREATE_DELIVERY":
                    error_message = "请提供销售订单号，例如：为订单 VB2025000059 创建交货单"
                else:
                    error_message = "请提供销售订单号，例如：检查订单 VB2025000059 的物料可用性。如果当前页面显示了订单详情，也可以直接说'检查物料可用性'，系统会自动使用当前订单。"
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
                    
                    # ★★★ 修复：从上下文（货物移动凭证）获取库存地点信息，并应用到行项目中 ★★★
                    # 如果上下文中有货物移动凭证信息，使用其中的库存地点
                    context = payload.get("context", {})
                    receipt = context.get("receipt")  # 货物移动凭证
                    if receipt:
                        # 从货物移动凭证中获取库存地点信息
                        receipt_lgort = receipt.get("lgort")
                        receipt_werks = receipt.get("werks")
                        receipt_lips = receipt.get("lips", [])  # 行项目列表
                        
                        # 如果有库存地点信息，应用到订单行项目中
                        if receipt_lgort and order_info.get("psList"):
                            ps_list = order_info.get("psList", [])
                            for ps in ps_list:
                                # 如果行项目的物料与货物移动凭证中的物料匹配，使用货物移动凭证的库存地点
                                # 优先匹配物料号，如果没有物料号，匹配物料描述
                                ps_matnr = ps.get("matnr")
                                ps_maktx = ps.get("maktx") or ps.get("arktx")
                                
                                # 在货物移动凭证的行项目中查找匹配的物料
                                matched = False
                                for receipt_lip in receipt_lips:
                                    receipt_matnr = receipt_lip.get("matnr")
                                    receipt_maktx = receipt_lip.get("maktx") or receipt_lip.get("arktx")
                                    
                                    # 匹配物料号或物料描述
                                    if (ps_matnr and receipt_matnr and ps_matnr == receipt_matnr) or \
                                       (ps_maktx and receipt_maktx and ps_maktx == receipt_maktx):
                                        # 使用货物移动凭证的库存地点和工厂
                                        if receipt_lgort:
                                            ps["lgort"] = receipt_lgort
                                            logger.info(f"从货物移动凭证应用库存地点到行项目: 物料={ps_matnr or ps_maktx}, 库存地点={receipt_lgort}")
                                        if receipt_werks:
                                            ps["werks"] = receipt_werks
                                        matched = True
                                        break
                                
                                # 如果没有匹配到具体的行项目，但货物移动凭证有库存地点，也应用（适用于单物料场景）
                                if not matched and receipt_lgort and len(receipt_lips) == 1:
                                    ps["lgort"] = receipt_lgort
                                    if receipt_werks:
                                        ps["werks"] = receipt_werks
                                    logger.info(f"从货物移动凭证应用库存地点到行项目（单物料）: 物料={ps_matnr or ps_maktx}, 库存地点={receipt_lgort}")
                    
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
                        # 注意：success 应该返回 True，因为请求已成功处理并返回了检查结果
                        # 业务结果的"失败"通过 data.type: "atp_check_failed" 来表示
                        return {
                            "success": True,
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
        
        elif intent == "CHECK_PRODUCTION_ORDER_MATERIAL":
            # 生产订单物料可用性检查（齐套性检查）
            # 优先使用LLM提取的生产订单号，否则使用规则提取，最后尝试从上下文获取
            aufnr = extracted.get("aufnr") or _extract_production_order_number(query)
            
            # 如果还没有生产订单号，尝试从请求的上下文信息中获取
            if not aufnr:
                context = payload.get("context", {})
                aufnr = context.get("aufnr")
                if aufnr:
                    logger.info(f"从上下文获取生产订单号: {aufnr}")
            
            if not aufnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供生产订单号，例如：检查生产订单8900000103的物料可用性"
                }
            
            try:
                # 调用生产订单物料可用性检查（齐套性检查）
                check_result = await sd_service.check_production_order_material_availability(aufnr)
                
                # 检查结果格式：如果是标准响应格式，使用code字段；如果不是，可能需要直接使用data
                result_code = check_result.get("code")
                if result_code is None:
                    # 如果没有code字段，可能是直接返回的数据，尝试判断是否有success字段
                    if check_result.get("success") is not False:
                        result_code = 200
                    else:
                        result_code = 500
                
                # 处理服务不可用的情况（503）
                if result_code == 503:
                    error_type = check_result.get("error_type")
                    if error_type == "SERVICE_UNAVAILABLE":
                        order_info = check_result.get("order_info", {})
                        resb_list = order_info.get("resb_list", [])
                        resb_count = order_info.get("resb_count", 0)
                        
                        # 即使服务不可用，也提供BOM组件信息
                        resb_summary = []
                        if resb_list:
                            for resb in resb_list[:10]:  # 只显示前10个组件
                                resb_summary.append({
                                    "matnr": resb.get("matnr"),
                                    "maktx": resb.get("maktx"),
                                    "bdmng": resb.get("bdmng"),
                                    "meins": resb.get("meins") or resb.get("erfme"),
                                    "werks": resb.get("werks")
                                })
                        
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "production_order_material_check_service_unavailable",
                                "message": check_result.get("message", "物料可用性检查服务暂时不可用"),
                                "aufnr": aufnr,
                                "resb_count": resb_count,
                                "resb_list": resb_summary,
                                "suggestion": "请启动物料需求管理服务（sinocst-module-me）后重试，或手动检查物料库存。"
                            }
                        }
                
                if result_code == 200:
                    # 齐套检查返回的数据是一个列表，如果列表为空，说明所有物料都充足
                    not_enough_list = check_result.get("data", [])
                    
                    # 检查是否是"无法检查"的情况（resbList为空）
                    error_type = check_result.get("error_type")
                    if error_type == "NO_BOM_DATA":
                        error_msg = check_result.get("message", "生产订单没有BOM组件数据，无法进行齐套性检查")
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "production_order_material_check_failed",
                                "message": f"生产订单 {aufnr} 的齐套性检查失败：{error_msg}。请确保生产订单已正确创建BOM组件数据。",
                                "aufnr": aufnr
                            }
                        }
                    
                    if not not_enough_list or len(not_enough_list) == 0:
                        # 齐套检查通过，但需要返回所有物料信息以供前端展示
                        # 获取order_info中的resb_list和mareq_items来补充字段
                        order_info = check_result.get("order_info", {})
                        resb_list = order_info.get("resb_list", [])
                        mareq_items = order_info.get("mareq_items", [])
                        
                        # 构建物料映射表，方便快速查找
                        resb_map = {}
                        for resb in resb_list:
                            matnr = resb.get("matnr")
                            if matnr and matnr not in resb_map:
                                resb_map[matnr] = resb
                        
                        # 优先使用mareq_items，因为它包含了更完整的信息
                        mareq_map = {}
                        for mareq in mareq_items:
                            matnr = mareq.get("matnr")
                            if matnr and matnr not in mareq_map:
                                mareq_map[matnr] = mareq
                        
                        # 使用mareq_items作为数据源（如果没有，则使用resb_list）
                        all_materials = mareq_items if mareq_items else resb_list
                        
                        # 构建查询库存的参数列表（使用mandt字段）
                        inventory_query_list = []
                        for material in all_materials:
                            matnr = material.get("matnr")
                            werks = material.get("werks")
                            
                            if matnr and werks:
                                inventory_query_list.append({
                                    "mandt": material.get("mandt", "600"),  # 默认mandt
                                    "matnr": matnr,
                                    "werks": werks,
                                    "lgort": material.get("lgort") or ""
                                })
                        
                        # 查询库存信息
                        inventory_map = {}
                        if inventory_query_list:
                            try:
                                inventory_result = await sd_service._request(
                                    method="POST",
                                    path="/sinocst-module-wm/sinocst-mard/mard/getStatusById",
                                    json=inventory_query_list
                                )
                                if inventory_result.get("code") == 200:
                                    inventory_data = inventory_result.get("data", [])
                                    # 建立映射：key = matnr-werks-lgort 或 matnr-werks
                                    for inv in inventory_data:
                                        matnr_key = inv.get("matnr")
                                        if matnr_key:
                                            # 如果有库存地点，使用matnr-werks-lgort作为key，否则使用matnr-werks
                                            lgort_key = inv.get("lgort") or ""
                                            werks_key = inv.get("werks") or ""
                                            key = f"{matnr_key}-{werks_key}-{lgort_key}" if lgort_key else f"{matnr_key}-{werks_key}"
                                            if key not in inventory_map:
                                                inventory_map[key] = inv
                                            # 同时使用matnr作为key，方便查找
                                            if matnr_key not in inventory_map:
                                                inventory_map[matnr_key] = inv
                            except Exception as e:
                                logger.warning(f"查询库存信息失败: {e}")
                                # 查询失败不影响主流程，继续使用空数据
                        
                        # 构建所有物料的items列表
                        all_materials_items = []
                        for material in all_materials:
                            matnr = material.get("matnr")
                            if not matnr:
                                continue
                            
                            # 从mareq_map或resb_map中获取完整信息
                            mareq_info = mareq_map.get(matnr)
                            resb_info = resb_map.get(matnr)
                            source_info = mareq_info or resb_info or material
                            
                            werks = source_info.get("werks") or ""
                            lgort = source_info.get("lgort") or ""
                            meins = source_info.get("erfme") or source_info.get("meins") or ""
                            # 确保bdmng是数字类型
                            bdmng_raw = source_info.get("bdmng") or source_info.get("plmng") or source_info.get("erfmg") or 0
                            try:
                                bdmng = float(bdmng_raw) if bdmng_raw else 0
                            except (ValueError, TypeError):
                                bdmng = 0
                            maktx = source_info.get("maktx") or ""
                            
                            # 查找库存信息（先尝试精确匹配，再尝试只匹配matnr）
                            inventory_info = None
                            if lgort and werks:
                                key = f"{matnr}-{werks}-{lgort}"
                                inventory_info = inventory_map.get(key)
                            if not inventory_info and werks:
                                key = f"{matnr}-{werks}"
                                inventory_info = inventory_map.get(key)
                            if not inventory_info:
                                inventory_info = inventory_map.get(matnr) or {}
                            
                            # 修复：优先使用库存查询返回的lgort（实际有库存的库存地点）
                            if inventory_info and inventory_info.get("lgort"):
                                lgort = inventory_info.get("lgort")
                                logger.info(f"物料 {matnr} 使用库存查询返回的库存地点：{lgort}")
                            
                            # 确保库存数量是数字类型
                            labst_raw = inventory_info.get("labst") or 0
                            speme_raw = inventory_info.get("speme") or 0
                            insme_raw = inventory_info.get("insme") or 0
                            einme_raw = inventory_info.get("einme") or 0  # 受限制库存
                            try:
                                labst = float(labst_raw) if labst_raw else 0
                            except (ValueError, TypeError):
                                labst = 0
                            try:
                                speme = float(speme_raw) if speme_raw else 0
                            except (ValueError, TypeError):
                                speme = 0
                            try:
                                insme = float(insme_raw) if insme_raw else 0
                            except (ValueError, TypeError):
                                insme = 0
                            try:
                                einme = float(einme_raw) if einme_raw else 0
                            except (ValueError, TypeError):
                                einme = 0
                            
                            # 修复：冻结库存不应该是负数，如果为负数，说明数据异常
                            # 当speme为负数时，可能表示实际可用库存，需要特殊处理
                            if speme < 0:
                                # 如果speme为负数，说明labst可能不准确，实际可用库存应该是|speme|
                                # 但为了保持数据一致性，我们将speme设为0，并使用labst + |speme|作为实际可用库存
                                actual_available_qty = max(0, labst - speme)  # labst - (-|speme|) = labst + |speme|
                                # 修正labst：如果labst为0但speme为负数，说明真正的总库存应该是|speme|
                                if labst == 0:
                                    labst = abs(speme)
                                    speme = 0
                                    logger.info(
                                        f"物料 {matnr} 在工厂 {werks} 库存地点 {lgort} 的库存数据修正："
                                        f"speme为负数({speme_raw})，修正后总库存(labst)={labst}, 冻结库存(speme)=0"
                                    )
                                else:
                                    # labst不为0，但speme为负数，将speme设为0
                                    speme = 0
                                    logger.warning(
                                        f"物料 {matnr} 在工厂 {werks} 库存地点 {lgort} 的库存数据异常："
                                        f"冻结库存(speme)为负数({speme_raw})，已修正为0"
                                    )
                            else:
                                # 正常情况：计算实际可用库存 = 非限制库存 - 冻结库存
                                actual_available_qty = max(0, labst - speme)
                            
                            # 添加日志：如果labst为0但实际可用库存大于0，记录警告
                            if labst == 0 and actual_available_qty > 0 and speme >= 0:
                                logger.warning(
                                    f"物料 {matnr} 在工厂 {werks} 库存地点 {lgort} 的库存数据异常："
                                    f"总库存(labst)={labst}, 冻结库存(speme)={speme}, "
                                    f"实际可用库存={actual_available_qty}, 质检库存(insme)={insme}, "
                                    f"受限制库存(einme)={einme}。"
                                    f"如果实际可用库存大于0，可能是查询返回的labst不正确，"
                                    f"或者实际可用库存的计算考虑了其他因素（如预留库存、绑定订单库存等）。"
                                )
                            
                            # 根据实际库存判断物料是否充足
                            is_available = actual_available_qty >= bdmng
                            if is_available:
                                message = f"库存充足：需要 {bdmng} {meins}，实际可用 {actual_available_qty} {meins}"
                            else:
                                message = f"库存不足：需要 {bdmng} {meins}，实际可用 {actual_available_qty} {meins}"
                            
                            # 修复：如果物料充足且生产订单没有库存地点，默认选中自由库L001
                            if is_available and (not lgort or lgort.strip() == ""):
                                lgort = "L001"
                                logger.info(f"物料 {matnr} 充足且没有库存地点，默认设置为L001")
                            
                            # 构建物料项数据
                            material_item = {
                                "matnr": matnr,
                                "matnr_name": maktx,  # 前端使用matnr_name字段
                                "maktx": maktx,  # 保留maktx字段以兼容
                                "werks": werks,
                                "lgort": lgort,  # 使用修复后的lgort（如果为空则默认为L001）
                                "meins": meins,
                                "need_qty": bdmng,
                                "labst": labst,
                                "speme": speme,
                                "insme": insme,
                                "actual_available_qty": actual_available_qty,
                                "is_available": is_available,  # 根据实际库存判断
                                "relatnr": source_info.get("relatnr") or aufnr,  # 关联订单号
                                "rspos": source_info.get("rspos") or "",  # 预留项目号
                                "message": message
                            }
                            all_materials_items.append(material_item)
                        
                        # 检查是否所有物料都充足
                        all_available = all(item.get("is_available", False) for item in all_materials_items)
                        
                        # 生成仓储管理列表（warehouse_list）：只包含充足且已设置库存地点的物料
                        warehouse_list = []
                        for item in all_materials_items:
                            if item.get("is_available", False) and item.get("lgort"):
                                warehouse_list.append({
                                    "matnr": item.get("matnr"),
                                    "matnr_name": item.get("matnr_name") or item.get("maktx"),
                                    "menge": item.get("need_qty"),
                                    "meins": item.get("meins"),
                                    "werks": item.get("werks"),
                                    "lgort": item.get("lgort")
                                })
                        
                        if all_available:
                            return {
                                "success": True,
                                "intent": intent,
                                "data": {
                                    "type": "production_order_material_check",
                                    "message": f"生产订单 {aufnr} 的齐套性检查完成，所有物料库存充足，可以进行生产。",
                                    "aufnr": aufnr,
                                    "items": all_materials_items,
                                    "warehouse_list": warehouse_list  # 添加仓储管理列表
                                }
                            }
                        else:
                            # 有物料不足，返回失败结果
                            not_enough_items = [item for item in all_materials_items if not item.get("is_available", False)]
                            material_names = [item.get("maktx", item.get("matnr", "")) for item in not_enough_items]
                            material_names_str = "、".join(material_names[:5])  # 最多显示5个物料
                            if len(not_enough_items) > 5:
                                material_names_str += f"等{len(not_enough_items)}个物料"
                            
                            return {
                                "success": True,
                                "intent": intent,
                                "data": {
                                    "type": "production_order_material_check_failed",
                                    "message": f"生产订单 {aufnr} 的齐套性检查未通过，物料{material_names_str}库存不足。",
                                    "aufnr": aufnr,
                                    "items": all_materials_items
                                }
                            }
                    else:
                        # 齐套检查失败，有物料不足
                        # 获取order_info中的resb_list和mareq_items来补充字段
                        order_info = check_result.get("order_info", {})
                        resb_list = order_info.get("resb_list", [])
                        mareq_items = order_info.get("mareq_items", [])
                        
                        # 构建物料映射表，方便快速查找
                        # 使用matnr作为key，如果有多个记录，使用第一个匹配的
                        resb_map = {}
                        for resb in resb_list:
                            matnr = resb.get("matnr")
                            if matnr and matnr not in resb_map:
                                resb_map[matnr] = resb
                        
                        # 优先使用mareq_items，因为它包含了更完整的信息
                        mareq_map = {}
                        for mareq in mareq_items:
                            matnr = mareq.get("matnr")
                            if matnr and matnr not in mareq_map:
                                mareq_map[matnr] = mareq
                        
                        # 构建查询库存的参数列表（使用mandt字段）
                        inventory_query_list = []
                        for item in not_enough_list:
                            matnr = item.get("matnr")
                            # 从resb_list或mareq_items中查找对应物料的详细信息
                            resb_info = resb_map.get(matnr)
                            mareq_info = mareq_map.get(matnr)
                            
                            # 优先使用mareq_info，因为它包含了更完整的信息（包括werks和lgort）
                            source_info = mareq_info or resb_info or {}
                            
                            # 构建库存查询参数
                            werks = source_info.get("werks")
                            if werks:
                                inventory_query_list.append({
                                    "mandt": source_info.get("mandt", "600"),  # 默认mandt
                                    "matnr": matnr,
                                    "werks": werks,
                                    "lgort": source_info.get("lgort") or ""
                                })
                        
                        # 查询库存信息（如果有物料需要查询）
                        inventory_map = {}
                        if inventory_query_list:
                            try:
                                inventory_result = await sd_service._request(
                                    method="POST",
                                    path="/sinocst-module-wm/sinocst-mard/mard/getStatusById",
                                    json=inventory_query_list
                                )
                                if inventory_result.get("code") == 200:
                                    inventory_data = inventory_result.get("data", [])
                                    # 建立映射：key = matnr
                                    for inv in inventory_data:
                                        matnr_key = inv.get("matnr")
                                        if matnr_key:
                                            inventory_map[matnr_key] = inv
                            except Exception as e:
                                logger.warning(f"查询库存信息失败: {e}")
                                # 查询失败不影响主流程，继续使用空数据
                        
                        # 格式化不足的物料信息
                        not_enough_materials = []
                        for item in not_enough_list:
                            matnr = item.get("matnr")
                            maktx = item.get("maktx") or ""
                            
                            # 从resb_list或mareq_items中查找对应物料的详细信息
                            resb_info = resb_map.get(matnr)
                            mareq_info = mareq_map.get(matnr)
                            
                            # 优先使用mareq_info，因为它包含了更完整的信息
                            source_info = mareq_info or resb_info or {}
                            
                            werks = source_info.get("werks") or ""
                            lgort = source_info.get("lgort") or ""
                            meins = source_info.get("erfme") or source_info.get("meins") or ""
                            # 确保bdmng是数字类型
                            bdmng_raw = source_info.get("bdmng") or source_info.get("plmng") or 0
                            try:
                                bdmng = float(bdmng_raw) if bdmng_raw else 0
                            except (ValueError, TypeError):
                                bdmng = 0
                            
                            # 查找库存信息（先尝试精确匹配，再尝试只匹配matnr）
                            inventory_info = None
                            if lgort and werks:
                                key = f"{matnr}-{werks}-{lgort}"
                                inventory_info = inventory_map.get(key)
                            if not inventory_info and werks:
                                key = f"{matnr}-{werks}"
                                inventory_info = inventory_map.get(key)
                            if not inventory_info:
                                inventory_info = inventory_map.get(matnr) or {}
                            
                            # 修复：优先使用库存查询返回的lgort（实际有库存的库存地点）
                            if inventory_info and inventory_info.get("lgort"):
                                lgort = inventory_info.get("lgort")
                                logger.info(f"物料 {matnr} 使用库存查询返回的库存地点：{lgort}")
                            
                            # 确保库存数量是数字类型
                            labst_raw = inventory_info.get("labst") or 0
                            speme_raw = inventory_info.get("speme") or 0
                            insme_raw = inventory_info.get("insme") or 0
                            try:
                                labst = float(labst_raw) if labst_raw else 0
                            except (ValueError, TypeError):
                                labst = 0
                            try:
                                speme = float(speme_raw) if speme_raw else 0
                            except (ValueError, TypeError):
                                speme = 0
                            try:
                                insme = float(insme_raw) if insme_raw else 0
                            except (ValueError, TypeError):
                                insme = 0
                            
                            # 修复：冻结库存不应该是负数，如果为负数，说明数据异常
                            # 当speme为负数时，可能表示实际可用库存，需要特殊处理
                            if speme < 0:
                                # 如果speme为负数，说明labst可能不准确，实际可用库存应该是|speme|
                                # 但为了保持数据一致性，我们将speme设为0，并使用labst + |speme|作为实际可用库存
                                actual_available_qty = max(0, labst - speme)  # labst - (-|speme|) = labst + |speme|
                                # 修正labst：如果labst为0但speme为负数，说明真正的总库存应该是|speme|
                                if labst == 0:
                                    labst = abs(speme)
                                    speme = 0
                                    logger.info(
                                        f"物料 {matnr} 在工厂 {werks} 库存地点 {lgort} 的库存数据修正："
                                        f"speme为负数({speme_raw})，修正后总库存(labst)={labst}, 冻结库存(speme)=0"
                                    )
                                else:
                                    # labst不为0，但speme为负数，将speme设为0
                                    speme = 0
                                    logger.warning(
                                        f"物料 {matnr} 在工厂 {werks} 库存地点 {lgort} 的库存数据异常："
                                        f"冻结库存(speme)为负数({speme_raw})，已修正为0"
                                    )
                            else:
                                # 正常情况：计算实际可用库存 = 非限制库存 - 冻结库存
                                actual_available_qty = max(0, labst - speme)
                            
                            # 构建物料项数据
                            material_item = {
                                "matnr": matnr,
                                "matnr_name": maktx,  # 前端使用matnr_name字段
                                "maktx": maktx,  # 保留maktx字段以兼容
                                "werks": werks,
                                "lgort": lgort,
                                "meins": meins,
                                "need_qty": bdmng,
                                "labst": labst,
                                "speme": speme,
                                "insme": insme,
                                "actual_available_qty": actual_available_qty,
                                "is_available": False,  # 因为这是not_enough_list中的物料
                                "relatnr": item.get("relatnr"),  # 关联订单号
                                "rspos": source_info.get("rspos") or "",  # 预留项目号
                                "message": f"库存不足：需要 {bdmng} {meins}，实际可用 {actual_available_qty} {meins}"
                            }
                            not_enough_materials.append(material_item)
                        
                        material_names = [item.get("maktx", item.get("matnr", "")) for item in not_enough_list]
                        material_names_str = "、".join(material_names[:5])  # 最多显示5个物料
                        if len(not_enough_list) > 5:
                            material_names_str += f"等{len(not_enough_list)}个物料"
                        
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "production_order_material_check_failed",
                                "message": f"生产订单 {aufnr} 的齐套性检查未通过，物料{material_names_str}库存不足。",
                                "aufnr": aufnr,
                                "items": not_enough_materials
                            }
                        }
                else:
                    error_msg = check_result.get("msg", "齐套性检查失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "production_order_material_check_failed",
                            "message": f"生产订单 {aufnr} 的齐套性检查失败：{error_msg}",
                            "aufnr": aufnr
                        }
                    }
            except Exception as e:
                error_msg = str(e)
                logger.error(f"生产订单齐套性检查失败: {error_msg}", exc_info=True)
                
                # 检查是否是服务连接错误
                if "Connection reset" in error_msg or "Connection" in error_msg or "连接" in error_msg:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "production_order_material_check_failed",
                            "message": f"生产订单 {aufnr} 的齐套性检查失败：无法连接到后端服务（可能是sinocst-master-data服务未正常运行或网络连接问题）。错误详情：{error_msg}",
                            "aufnr": aufnr
                        }
                    }
                elif "获取生产订单详情失败" in error_msg:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "production_order_material_check_failed",
                            "message": f"{error_msg}。请确认生产订单号是否正确，或生产订单是否存在。",
                            "aufnr": aufnr
                        }
                    }
                else:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "production_order_material_check_failed",
                            "message": f"生产订单 {aufnr} 的齐套性检查时出错：{error_msg}",
                            "aufnr": aufnr
                        }
                    }
        
        elif intent == "CHECK_INTERNAL_ORDER_MATERIAL":
            # 内部订单物料可用性检查（齐套性检查）
            # 优先使用LLM提取的内部订单号，否则使用规则提取，最后尝试从上下文获取
            internal_aufnr = extracted.get("internal_aufnr") or _extract_internal_order_number(query)
            
            # 如果还没有内部订单号，尝试从请求的上下文信息中获取
            if not internal_aufnr:
                context = payload.get("context", {})
                internal_aufnr = context.get("internal_aufnr") or context.get("aufnr")
                if internal_aufnr:
                    logger.info(f"从上下文获取内部订单号: {internal_aufnr}")
            
            if not internal_aufnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供内部订单号，例如：检查内部订单808000000008的齐套性"
                }
            
            try:
                # 调用内部订单物料可用性检查（齐套性检查）
                check_result = await sd_service.check_internal_order_material_availability(internal_aufnr)
                
                # 检查结果格式：如果是标准响应格式，使用code字段；如果不是，可能需要直接使用data
                result_code = check_result.get("code")
                if result_code is None:
                    # 如果没有code字段，可能是直接返回的数据，尝试判断是否有success字段
                    if check_result.get("success") is not False:
                        result_code = 200
                    else:
                        result_code = 500
                
                # 处理服务不可用的情况（503）
                if result_code == 503:
                    error_type = check_result.get("error_type")
                    if error_type == "SERVICE_UNAVAILABLE":
                        order_info = check_result.get("order_info", {})
                        bom_list = order_info.get("bom_list", [])
                        bom_count = order_info.get("bom_count", 0)
                        
                        # 即使服务不可用，也提供BOM组件信息
                        bom_summary = []
                        if bom_list:
                            for bom_item in bom_list[:10]:  # 只显示前10个组件
                                matnr = bom_item.get("idnrk") or bom_item.get("matnr", "")
                                maktx = bom_item.get("ojtxp") or bom_item.get("maktx", "")
                                menge = bom_item.get("menge") or bom_item.get("bdmng", 0)
                                meins = bom_item.get("meins") or bom_item.get("erfme", "")
                                bom_summary.append(f"{matnr}({maktx}) {menge} {meins}")
                        
                        summary_text = "\n".join(bom_summary) if bom_summary else "无BOM组件数据"
                        if bom_count > 10:
                            summary_text += f"\n... 还有 {bom_count - 10} 个组件"
                        
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "internal_order_material_check_failed",
                                "message": f"内部订单 {internal_aufnr} 的齐套性检查服务暂时不可用。\n\n内部订单有 {bom_count} 个BOM组件：\n{summary_text}\n\n请确保物料需求管理服务（sinocst-module-me）已启动并运行在端口9999。",
                                "internal_aufnr": internal_aufnr,
                                "error_type": "SERVICE_UNAVAILABLE"
                            }
                        }
                
                # 处理没有BOM数据的情况（400）
                if result_code == 400:
                    error_type = check_result.get("error_type")
                    if error_type in ["NO_BOM_DATA", "NO_VALID_BOM_DATA", "NO_MATERIAL"]:
                        return {
                            "success": False,
                            "intent": intent,
                            "data": {
                                "type": "internal_order_material_check_failed",
                                "message": check_result.get("message", f"内部订单 {internal_aufnr} 没有BOM组件数据，无法进行齐套性检查。请先执行BOM展开。"),
                                "internal_aufnr": internal_aufnr,
                                "error_type": error_type
                            }
                        }
                
                # 处理成功的情况（200）
                if result_code == 200:
                    # 获取检查结果数据
                    check_data = check_result.get("data", [])
                    order_info = check_result.get("order_info", {})
                    bom_list = order_info.get("bom_list", [])
                    mareq_items = order_info.get("mareq_items", [])
                    order_quantity = order_info.get("order_quantity", 1)
                    
                    # 处理检查结果，构建物料项列表
                    all_materials_items = []
                    bom_map = {}
                    for bom_item in bom_list:
                        matnr = bom_item.get("idnrk") or bom_item.get("matnr")
                        if matnr:
                            bom_map[matnr] = bom_item
                    
                    # 如果check_data为空，从BOM列表构建物料明细（所有物料都充足的情况）
                    if not check_data:
                        # 从BOM列表构建物料明细
                        for bom_item in bom_list:
                            matnr = bom_item.get("idnrk") or bom_item.get("matnr")
                            if not matnr:
                                continue
                            
                            maktx = bom_item.get("ojtxp") or bom_item.get("maktx") or ""
                            werks = bom_item.get("werks") or ""
                            lgort = bom_item.get("lgort") or ""
                            meins = bom_item.get("meins") or bom_item.get("erfme") or ""
                            bdmng = bom_item.get("menge") or bom_item.get("bdmng") or 0
                            
                            # 如果物料充足且没有库存地点，默认设置为L001
                            if not lgort or lgort.strip() == "":
                                lgort = "L001"
                            
                            material_item = {
                                "matnr": matnr,
                                "matnr_name": maktx,
                                "maktx": maktx,
                                "werks": werks,
                                "lgort": lgort,
                                "meins": meins,
                                "need_qty": bdmng,
                                "labst": 0,  # 所有物料充足时，库存信息可能不在check_data中
                                "speme": 0,
                                "insme": 0,
                                "actual_available_qty": bdmng,  # 假设充足，实际值应该从库存查询
                                "is_available": True,
                                "relatnr": internal_aufnr,
                                "message": f"库存充足：需要 {bdmng} {meins}"
                            }
                            all_materials_items.append(material_item)
                    else:
                        # 有检查结果，处理检查数据
                        for check_item in check_data:
                            matnr = check_item.get("matnr")
                            bom_item = bom_map.get(matnr, {})
                            
                            maktx = bom_item.get("ojtxp") or bom_item.get("maktx") or check_item.get("maktx", "")
                            werks = check_item.get("werks") or bom_item.get("werks", "")
                            lgort = check_item.get("lgort") or bom_item.get("lgort", "")
                            meins = bom_item.get("meins") or bom_item.get("erfme") or check_item.get("erfme", "")
                            bdmng = check_item.get("bdmng") or check_item.get("plmng", 0)
                            labst = check_item.get("labst", 0)
                            speme = check_item.get("speme", 0)
                            insme = check_item.get("insme", 0)
                            
                            # 计算实际可用库存
                            actual_available_qty = float(labst) - float(speme) - float(insme)
                            
                            # 判断物料是否充足
                            is_available = actual_available_qty >= float(bdmng)
                            if is_available:
                                message = f"库存充足：需要 {bdmng} {meins}，实际可用 {actual_available_qty} {meins}"
                            else:
                                message = f"库存不足：需要 {bdmng} {meins}，实际可用 {actual_available_qty} {meins}"
                            
                            # 如果物料充足且没有库存地点，默认设置为L001
                            if is_available and (not lgort or lgort.strip() == ""):
                                lgort = "L001"
                            
                            material_item = {
                                "matnr": matnr,
                                "matnr_name": maktx,
                                "maktx": maktx,
                                "werks": werks,
                                "lgort": lgort,
                                "meins": meins,
                                "need_qty": bdmng,
                                "labst": labst,
                                "speme": speme,
                                "insme": insme,
                                "actual_available_qty": actual_available_qty,
                                "is_available": is_available,
                                "relatnr": internal_aufnr,
                                "message": message
                            }
                            all_materials_items.append(material_item)
                    
                    # 检查是否所有物料都充足
                    all_available = all(item.get("is_available", False) for item in all_materials_items)
                    
                    # 生成仓储管理列表
                    warehouse_list = []
                    for item in all_materials_items:
                        if item.get("is_available", False) and item.get("lgort"):
                            warehouse_list.append({
                                "matnr": item.get("matnr"),
                                "matnr_name": item.get("matnr_name") or item.get("maktx"),
                                "menge": item.get("need_qty"),
                                "meins": item.get("meins"),
                                "werks": item.get("werks"),
                                "lgort": item.get("lgort")
                            })
                    
                    if all_available:
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "internal_order_material_check",
                                "message": f"内部订单 {internal_aufnr} 的齐套性检查完成，所有物料库存充足，可以进行投料。",
                                "internal_aufnr": internal_aufnr,
                                "items": all_materials_items,
                                "warehouse_list": warehouse_list
                            }
                        }
                    else:
                        # 有物料不足，返回失败结果
                        not_enough_items = [item for item in all_materials_items if not item.get("is_available", False)]
                        material_names = [item.get("maktx", item.get("matnr", "")) for item in not_enough_items]
                        material_names_str = "、".join(material_names[:5])
                        if len(not_enough_items) > 5:
                            material_names_str += f"等{len(not_enough_items)}个物料"
                        
                        return {
                            "success": True,
                            "intent": intent,
                            "data": {
                                "type": "internal_order_material_check_failed",
                                "message": f"内部订单 {internal_aufnr} 的齐套性检查未通过，物料{material_names_str}库存不足。",
                                "internal_aufnr": internal_aufnr,
                                "items": all_materials_items
                            }
                        }
                else:
                    error_msg = check_result.get("msg", "齐套性检查失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "internal_order_material_check_failed",
                            "message": f"内部订单 {internal_aufnr} 的齐套性检查失败：{error_msg}",
                            "internal_aufnr": internal_aufnr
                        }
                    }
            except Exception as e:
                error_msg = str(e)
                logger.error(f"内部订单齐套性检查失败: {error_msg}", exc_info=True)
                
                # 检查是否是服务连接错误
                if "Connection reset" in error_msg or "Connection" in error_msg or "连接" in error_msg:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "internal_order_material_check_failed",
                            "message": f"内部订单 {internal_aufnr} 的齐套性检查失败：无法连接到后端服务（可能是sinocst-module-co或sinocst-module-me服务未正常运行或网络连接问题）。错误详情：{error_msg}",
                            "internal_aufnr": internal_aufnr
                        }
                    }
                elif "获取内部订单详情失败" in error_msg or "内部订单不存在" in error_msg:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "internal_order_material_check_failed",
                            "message": f"{error_msg}。请确认内部订单号是否正确，或内部订单是否存在。",
                            "internal_aufnr": internal_aufnr
                        }
                    }
                else:
                    return {
                        "success": False,
                        "intent": intent,
                        "data": {
                            "type": "internal_order_material_check_failed",
                            "message": f"内部订单 {internal_aufnr} 的齐套性检查时出错：{error_msg}",
                            "internal_aufnr": internal_aufnr
                        }
                    }
        
        elif intent == "POST_DELIVERY":
            # 交货单过账
            # 优先使用LLM提取的交货单号，否则使用规则提取
            delivery_vbeln = extracted.get("delivery_vbeln") or _extract_delivery_number(query)
            if not delivery_vbeln:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供交货单号，例如：为交货单8000000048过账"
                }
            
            try:
                result = await sd_service.post_delivery(delivery_vbeln)
                
                if result.get("code") == 200:
                    return {
                        "success": True,
                        "intent": intent,
                        "data": {
                            "type": "delivery_posted",
                            "message": f"交货单 {delivery_vbeln} 过账成功！",
                            "vbeln": delivery_vbeln
                        }
                    }
                else:
                    error_msg = result.get("msg", "过账失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"交货单 {delivery_vbeln} 过账失败：{error_msg}"
                    }
            except Exception as e:
                logger.error(f"交货单过账失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"交货单过账时出错：{str(e)}"
                }
        
        elif intent == "CREATE_INVOICE":
            # 创建发票（从交货单开票）
            # 优先使用LLM提取的交货单号，否则使用规则提取
            delivery_vbeln = extracted.get("delivery_vbeln") or _extract_delivery_number(query)
            if not delivery_vbeln:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供交货单号，例如：为交货单8000000048开票"
                }
            
            try:
                result = await sd_service.create_invoice_from_delivery(delivery_vbeln)
                
                if result.get("code") == 200:
                    invoice_vbeln = result.get("data")
                    return {
                        "success": True,
                        "intent": intent,
                        "data": {
                            "type": "invoice_created",
                            "message": f"为交货单 {delivery_vbeln} 创建发票成功！发票号：{invoice_vbeln}",
                            "delivery_vbeln": delivery_vbeln,
                            "invoice_vbeln": invoice_vbeln
                        }
                    }
                else:
                    error_msg = result.get("msg", "开票失败")
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"为交货单 {delivery_vbeln} 开票失败：{error_msg}"
                    }
            except Exception as e:
                logger.error(f"创建发票失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "intent": intent,
                    "message": f"创建发票时出错：{str(e)}"
                }
        
        elif intent == "COPY_ORDER":
            # 根据指定订单复制创建新订单
            # 优先从用户查询中直接提取订单号（最准确），然后使用LLM提取，最后使用规则提取
            # 注意：不要使用上下文中的订单号，因为用户可能想复制其他订单
            vbeln = None
            
            # 1. 优先从用户查询中直接提取（最准确）
            direct_extract = _extract_order_number(query)
            if direct_extract:
                vbeln = direct_extract
                logger.info(f"从用户查询中直接提取到订单号: {vbeln}")
            
            # 2. 如果直接提取失败，使用LLM提取的结果
            if not vbeln and extracted.get("vbeln"):
                vbeln = extracted.get("vbeln")
                logger.info(f"使用LLM提取的订单号: {vbeln}")
            
            # 3. 如果都失败，返回错误
            if not vbeln:
                logger.warning(f"无法从查询中提取订单号: {query}")
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供要复制的订单号，例如：根据订单VB2025000091复制并创建新订单"
                }
            
            logger.info(f"准备复制订单: {vbeln}, 用户查询: {query}")
            
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
                
                # 记录源订单信息
                logger.info(f"获取到源订单 {vbeln} 的详情，订单类型: {source_order.get('auart')}, 客户: {source_order.get('kunnrAgvName')}")
                
                # 检查源订单是否有行项目
                ap_list = source_order.get("apList", [])
                if not ap_list or len(ap_list) == 0:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": f"源订单{vbeln}没有行项目数据，无法复制创建新订单。请选择有行项目的订单进行复制。"
                    }
                
                # 记录源订单的行项目详情
                logger.info(f"源订单 {vbeln} 有 {len(ap_list)} 个行项目:")
                for idx, item in enumerate(ap_list):
                    logger.info(f"  行项目 {idx + 1}: posnr={item.get('posnr')}, matnr={item.get('matnr')}, maktx={item.get('maktx')}, zmeng={item.get('zmeng')}, kwmeng={item.get('kwmeng')}")
                
                # 复制订单数据
                logger.info(f"开始复制订单数据，源订单行项目数量: {len(ap_list)}")
                new_order_data = _copy_order_data(source_order, query, extracted)
                logger.info(f"复制完成，新订单行项目数量: {len(new_order_data.get('apList', []))}")
                
                # 记录新订单的行项目详情用于调试
                if new_order_data.get('apList'):
                    logger.info("新订单的行项目详情:")
                    for idx, item in enumerate(new_order_data.get('apList', [])):
                        logger.info(f"  行项目 {idx + 1}: matnr={item.get('matnr')}, maktx={item.get('maktx')}, zmeng={item.get('zmeng')}, kwmeng={item.get('kwmeng')}, menge={item.get('menge')}")
                
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
                
                # 如果指定了销售组关键词，查找并设置销售组
                if "_sales_group_keyword" in new_order_data:
                    keyword = new_order_data.pop("_sales_group_keyword")
                    sales_group = await sd_service.get_sales_group_by_name(keyword)
                    
                    if sales_group:
                        new_order_data["vkgrp"] = sales_group.get("vkgrp")
                        new_order_data["vkgrpName"] = sales_group.get("bezei") or sales_group.get("vkgrpName", "")
                        logger.info(f"已设置销售组为：{new_order_data['vkgrp']} - {new_order_data.get('vkgrpName', '')}")
                    else:
                        logger.warning(f"未找到包含'{keyword}'的销售组，保持原订单的销售组")
                
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
            # 但是，如果提取到了订单号，应该使用COPY_ORDER逻辑
            vbeln_from_extract = extracted.get("vbeln") or _extract_order_number(query)
            if vbeln_from_extract:
                logger.info(f"虽然识别为CREATE_SALES_ORDER，但提取到了订单号 {vbeln_from_extract}，改用COPY_ORDER逻辑")
                # 改用COPY_ORDER逻辑
                intent = "COPY_ORDER"
                # 跳转到COPY_ORDER的处理逻辑（需要重新组织代码结构）
                # 这里先处理COPY_ORDER逻辑
                try:
                    # 获取源订单详情
                    source_order_result = await sd_service.get_order_detail(vbeln_from_extract)
                    
                    if source_order_result.get("code") != 200:
                        error_msg = source_order_result.get("msg", "获取订单详情失败")
                        return {
                            "success": False,
                            "intent": intent,
                            "message": f"获取订单{vbeln_from_extract}详情失败：{error_msg}"
                        }
                    
                    source_order = source_order_result.get("data")
                    if not source_order:
                        return {
                            "success": False,
                            "intent": intent,
                            "message": f"订单{vbeln_from_extract}不存在或无法获取订单信息"
                        }
                    
                    # 记录源订单信息
                    logger.info(f"获取到源订单 {vbeln_from_extract} 的详情，订单类型: {source_order.get('auart')}, 客户: {source_order.get('kunnrAgvName')}")
                    
                    # 检查源订单是否有行项目
                    ap_list = source_order.get("apList", [])
                    if not ap_list or len(ap_list) == 0:
                        return {
                            "success": False,
                            "intent": intent,
                            "message": f"源订单{vbeln_from_extract}没有行项目数据，无法复制创建新订单。请选择有行项目的订单进行复制。"
                        }
                    
                    # 记录源订单的行项目详情
                    logger.info(f"源订单 {vbeln_from_extract} 有 {len(ap_list)} 个行项目:")
                    for idx, item in enumerate(ap_list):
                        logger.info(f"  行项目 {idx + 1}: posnr={item.get('posnr')}, matnr={item.get('matnr')}, maktx={item.get('maktx')}, zmeng={item.get('zmeng')}, kwmeng={item.get('kwmeng')}")
                    
                    # 复制订单数据
                    logger.info(f"开始复制订单数据，源订单行项目数量: {len(ap_list)}")
                    new_order_data = _copy_order_data(source_order, query, extracted)
                    logger.info(f"复制完成，新订单行项目数量: {len(new_order_data.get('apList', []))}")
                    
                    # 记录新订单的行项目详情用于调试
                    if new_order_data.get('apList'):
                        logger.info("新订单的行项目详情:")
                        for idx, item in enumerate(new_order_data.get('apList', [])):
                            logger.info(f"  行项目 {idx + 1}: matnr={item.get('matnr')}, maktx={item.get('maktx')}, zmeng={item.get('zmeng')}, kwmeng={item.get('kwmeng')}, menge={item.get('menge')}")
                    
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
                                return {
                                    "success": True,
                                    "intent": intent,
                                    "data": {
                                        "type": "order_created",
                                        "order": None,
                                        "message": f"基于订单{vbeln_from_extract}复制创建新订单成功！新订单号：{new_vbeln}（订单详情获取失败，请稍后查看）",
                                        "vbeln": new_vbeln,
                                        "source_vbeln": vbeln_from_extract
                                    }
                                }
                            
                            return {
                                "success": True,
                                "intent": intent,
                                "data": {
                                    "type": "order_created",
                                    "order": order_data,
                                    "message": f"基于订单{vbeln_from_extract}复制创建新订单成功！新订单号：{new_vbeln}",
                                    "vbeln": new_vbeln,
                                    "source_vbeln": vbeln_from_extract
                                }
                            }
                        except Exception as e:
                            logger.error(f"获取订单 {new_vbeln} 详情失败: {str(e)}", exc_info=True)
                            return {
                                "success": True,
                                "intent": intent,
                                "data": {
                                    "type": "order_created",
                                    "order": None,
                                    "message": f"基于订单{vbeln_from_extract}复制创建新订单成功！新订单号：{new_vbeln}（订单详情获取失败，请稍后查看）",
                                    "vbeln": new_vbeln,
                                    "source_vbeln": vbeln_from_extract
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
            
            # 如果没有提取到订单号，使用原来的逻辑（基于昨天的最后一个订单）
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
                new_order_data = _copy_order_data(yesterday_order, query, extracted)
                
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
                
                # 如果指定了销售组关键词，查找并设置销售组
                if "_sales_group_keyword" in new_order_data:
                    keyword = new_order_data.pop("_sales_group_keyword")
                    sales_group = await sd_service.get_sales_group_by_name(keyword)
                    
                    if sales_group:
                        new_order_data["vkgrp"] = sales_group.get("vkgrp")
                        new_order_data["vkgrpName"] = sales_group.get("bezei") or sales_group.get("vkgrpName", "")
                        logger.info(f"已设置销售组为：{new_order_data['vkgrp']} - {new_order_data.get('vkgrpName', '')}")
                    else:
                        logger.warning(f"未找到包含'{keyword}'的销售组，保持原订单的销售组")
                
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
                # 优先使用LLM提取的订单号，否则使用规则提取
                vbeln = (extracted.get("vbeln") or _extract_order_number(query)) if "ORDER" in intent else None
                
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
            # 闲聊或超出能力范围的问题，使用LLM自动回答
            return await _handle_smalltalk_with_llm(query, intent or "SMALLTALK")
    
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


def _copy_order_data(order_data: Dict[str, Any], query: str, extracted: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    复制订单数据并修改销售办事处和销售组
    
    Args:
        order_data: 原始订单数据
        query: 用户查询（用于提取要修改的销售办事处和销售组，作为fallback）
        extracted: LLM提取的信息（优先使用，包含sales_group等）
    
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
    
    # 从LLM提取的信息中获取销售办事处（优先），如果没有则使用关键词匹配作为fallback
    sales_office_keyword = None
    if extracted and extracted.get("sales_office"):
        sales_office_keyword = extracted.get("sales_office")
        logger.info(f"从LLM提取到销售办事处关键词: {sales_office_keyword}")
    else:
        # Fallback: 使用关键词匹配（仅在LLM未提取到时使用）
        query_lower = query.lower()
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
        logger.info(f"提取到销售办事处关键词: {sales_office_keyword}")
    
    # 从LLM提取的信息中获取销售组（优先），如果没有则使用正则匹配作为fallback
    sales_group_keyword = None
    if extracted and extracted.get("sales_group"):
        sales_group_keyword = extracted.get("sales_group")
        logger.info(f"从LLM提取到销售组关键词: {sales_group_keyword}")
    else:
        # Fallback: 使用正则匹配（仅在LLM未提取到时使用）
        if "销售组" in query or "销售组改为" in query or ("改为" in query and "销售组" in query):
            # 提取销售组名称（在"改为"、"销售组改为"等关键词之后）
            # 支持引号中的内容，如："销售组改为"经销商销售组""
            # 支持带空格的词组，如："销售组改为经销商销售组"
            patterns = [
                r"销售组改为\s*[""']([^""']+)[""']",  # 匹配引号中的完整内容（优先匹配）
                r"改为\s*[""']([^""']+)[""']",  # 匹配引号中的完整内容（优先匹配）
                r"销售组改为[：:\s]*([^，,。.\n并]+)(?=\s*(?:并|，|,|。|$)|$)",  # 匹配到"并"、逗号、句号或结束符（允许空格和中文，冒号可选）
                r"改为[：:\s]+([^，,。.\n并]+)(?=\s*(?:并|，|,|。|$)|$)",  # 匹配到"并"、逗号、句号或结束符（允许空格和中文）
            ]
            for pattern in patterns:
                match = re.search(pattern, query)
                if match:
                    sales_group_keyword = match.group(1).strip()
                    # 移除可能的引号
                    sales_group_keyword = sales_group_keyword.strip('"').strip("'").strip()
                    if sales_group_keyword:
                        logger.info(f"使用正则表达式 '{pattern}' 提取到销售组关键词: {sales_group_keyword}")
                        break
    
    # 如果指定了销售组关键词，需要异步获取（这里先设置一个标记，由调用方处理）
    if sales_group_keyword:
        new_order["_sales_group_keyword"] = sales_group_keyword
        logger.info(f"提取到销售组关键词: {sales_group_keyword}")
    
    # 复制行项目数据（如果存在）
    if "apList" in new_order and new_order["apList"]:
        # 确保apList是一个列表
        if not isinstance(new_order["apList"], list):
            logger.warning(f"apList不是列表类型: {type(new_order['apList'])}")
            new_order["apList"] = []
        else:
            # 深拷贝每个行项目，确保所有字段都被正确复制
            copied_items = []
            for idx, item in enumerate(new_order["apList"]):
                if not isinstance(item, dict):
                    logger.warning(f"行项目 {idx + 1} 不是字典类型: {type(item)}, 跳过")
                    continue
                
                # 深拷贝行项目
                import copy
                copied_item = copy.deepcopy(item)
                
                # 清空行项目号，让系统自动生成
                if "posnr" in copied_item:
                    copied_item["posnr"] = None
                
                # 清空订单号（行项目中的vbeln应该使用新订单号）
                if "vbeln" in copied_item:
                    copied_item["vbeln"] = None
                
                # 确保关键字段存在（物料号、数量等）
                matnr = copied_item.get("matnr")
                zmeng = copied_item.get("zmeng")
                kwmeng = copied_item.get("kwmeng")
                
                if not matnr:
                    logger.warning(f"行项目 {idx + 1} 缺少物料号(matnr): {copied_item}")
                else:
                    logger.debug(f"行项目 {idx + 1} 复制: matnr={matnr}, zmeng={zmeng}, kwmeng={kwmeng}")
                
                # 确保数量字段存在（优先使用zmeng，如果没有则使用kwmeng）
                if not zmeng and kwmeng:
                    copied_item["zmeng"] = kwmeng
                    logger.debug(f"行项目 {idx + 1} 使用kwmeng作为zmeng: {kwmeng}")
                
                # 统一数量字段，保留原值（前端会处理默认值显示）
                final_quantity = copied_item.get("zmeng") or copied_item.get("kwmeng") or copied_item.get("menge")
                if final_quantity is not None:
                    copied_item["zmeng"] = final_quantity
                    copied_item["kwmeng"] = final_quantity
                    copied_item["menge"] = final_quantity
                
                copied_items.append(copied_item)
            
            # 更新apList
            new_order["apList"] = copied_items
            logger.info(f"已复制 {len(copied_items)} 个行项目")
    
    return new_order

