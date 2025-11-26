#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PP Agent AI查询接口
支持自然语言查询生产订单、报工情况、月结异常检测等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
import os
import json
import requests
from app.services.pp_service import PPService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建PPService实例，并传递token
def get_pp_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth")
) -> PPService:
    """创建PPService实例，并传递认证token"""
    service = PPService()
    
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
        logger.info(f"Token已设置到PPService (长度: {len(token)})")
    else:
        logger.warning("未收到有效的token请求头")
    
    return service

def _extract_order_number(text: str) -> Optional[str]:
    """从文本中提取生产订单号（改进版，更智能）"""
    # 模式1: 明确的订单号标识
    patterns = [
        r"(?:订单号|订单|生产订单|工单|AUFNR|订单编号|单号)[\s\-:：]?([0-9]{10,12})",
        r"查看[订单]?\s*([0-9]{10,12})",
        r"查询[订单]?\s*([0-9]{10,12})",
        r"订单\s*([0-9]{10,12})",
        r"([0-9]{10,12})",  # 最后尝试匹配任意10-12位数字
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            order_num = match.group(1).strip()
            # 验证：订单号通常是10-12位
            if 10 <= len(order_num) <= 12:
                return order_num
    
    return None

def _extract_material_number(text: str) -> Optional[str]:
    """从文本中提取物料号"""
    patterns = [
        r"(?:物料号|物料|MATNR)[\s\-:]?([A-Z0-9\-]+)",
        r"([A-Z]{1,}[0-9]{6,})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matnr = match.group(1).strip()
            if len(matnr) >= 6:
                return matnr
    
    return None

async def _identify_intent_with_llm(text: str) -> Dict[str, Any]:
    """
    使用LLM识别用户意图（智能解析）
    
    Returns:
        {
            "intent": "QUERY_ORDER_DETAIL",
            "confidence": 0.9,
            "extracted": {"aufnr": "001010014285", "matnr": None}
        }
    """
    # 检查是否启用LLM
    use_llm = os.getenv("USE_LLM_PP_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("PP_AGENT_LLM_MODEL", "qwen-max-latest")
    
    if not use_llm or not openai_api_key or not openai_base_url:
        return None
    
    try:
        system_prompt = """你是一个生产计划(PP)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_ORDER_DETAIL - 查询生产订单详情（用户提到订单号、查看订单、订单详情等）
2. QUERY_ORDER_LIST - 查询生产订单列表（查询所有订单、订单列表等）
3. QUERY_WORK_REPORT - 查询报工一览表（报工、报工情况、报工明细等）
4. QUERY_UNREPORTED_WORK - 查询未报工情况（未报工、待报工、未完成报工等）
5. MONTH_END_CHECK - 月结异常检测（月结、异常检测等）
6. ORDER_STATUS_MONITOR - 订单状态监控（订单状态、进度、延迟等）
7. ADJUST_COLUMNS - 字段调整（移除字段、显示字段等）
8. SMALLTALK - 闲聊或询问如何使用

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "aufnr": "订单号（如果提到）",
        "matnr": "物料号（如果提到）",
        "werks": "工厂（如果提到）"
    },
    "reasoning": "简要说明识别理由"
}

注意：
- 订单号通常是10-12位数字
- 如果用户提到"查看订单XXX"、"订单XXX的详情"、"查询订单XXX"等，应该是QUERY_ORDER_DETAIL
- 如果只提到"订单列表"、"所有订单"等，应该是QUERY_ORDER_LIST
- 优先提取订单号，即使表达不完整也要识别"""

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
    识别用户意图（规则式匹配，作为备选方案）
    
    Returns:
        意图类型：NAVIGATE_*, QUERY_ORDER_*, QUERY_WORK_REPORT, QUERY_UNREPORTED_WORK,
        MONTH_END_CHECK, ADJUST_COLUMNS, SMALLTALK
    """
    text_lower = text.lower()
    
    # 字段调整意图（核心创新功能）
    if any(keyword in text_lower for keyword in ["移除", "隐藏", "不要显示", "去掉", "删除", "不显示"]):
        if any(keyword in text_lower for keyword in ["字段", "列", "单位", "类型", "工厂", "工序", "描述"]):
            return "ADJUST_COLUMNS"
    if any(keyword in text_lower for keyword in ["增加", "添加", "显示", "展示", "包含"]):
        if any(keyword in text_lower for keyword in ["字段", "列", "单位", "类型", "工厂", "工序", "描述"]):
            return "ADJUST_COLUMNS"
    if any(keyword in text_lower for keyword in ["恢复默认", "显示所有", "重置字段"]):
        return "ADJUST_COLUMNS"
    
    # 页面跳转意图
    if any(keyword in text_lower for keyword in ["跳转", "打开", "进入", "去", "导航"]):
        if "生产订单" in text_lower and "列表" in text_lower:
            return "NAVIGATE_ORDER_LIST"
        elif "生产订单" in text_lower and ("详情" in text_lower or "显示" in text_lower):
            return "NAVIGATE_ORDER_DETAIL"
        elif "报工" in text_lower:
            return "NAVIGATE_WORK_REPORT"
        elif "计划订单" in text_lower:
            return "NAVIGATE_PLANNED_ORDER"
        elif "物料需求" in text_lower or "mrp" in text_lower:
            return "NAVIGATE_MRP"
    
    # 未报工情况查询意图
    if any(keyword in text_lower for keyword in ["未报工", "待报工", "未完成报工"]):
        return "QUERY_UNREPORTED_WORK"
    
    # 报工查询意图
    if any(keyword in text_lower for keyword in ["报工", "报工情况", "报工一览表", "报工明细"]):
        return "QUERY_WORK_REPORT"
    
    # 生产订单查询意图 - 改进识别逻辑
    # 先检查是否包含订单号（更优先）
    if _extract_order_number(text):
        return "QUERY_ORDER_DETAIL"
    
    # 然后检查关键词
    if any(keyword in text_lower for keyword in ["生产订单", "订单", "工单"]):
        # 检查是否有关键词暗示是详情查询
        detail_keywords = ["详情", "显示", "查看", "详情", "信息", "详情", "的"]
        if any(keyword in text_lower for keyword in detail_keywords):
            return "QUERY_ORDER_DETAIL"
        # 检查是否有数字（可能是订单号）
        if re.search(r'\d{10,}', text):
            return "QUERY_ORDER_DETAIL"
        # 否则是列表查询
            return "QUERY_ORDER_LIST"
    
    # 月结异常检测意图
    if any(keyword in text_lower for keyword in ["月结", "异常检测", "检查异常", "异常数据"]):
        return "MONTH_END_CHECK"
    
    # 订单状态监控意图
    if any(keyword in text_lower for keyword in ["订单状态", "完成进度", "延迟", "进度"]):
        return "ORDER_STATUS_MONITOR"
    
    # 默认：闲聊
    return "SMALLTALK"

async def _handle_smalltalk_or_out_of_scope(query: str, intent: str) -> Dict[str, Any]:
    """
    处理闲聊或超出能力范围的问题，使用LLM自动回答
    
    Args:
        query: 用户查询
        intent: 识别的意图（通常是SMALLTALK）
        
    Returns:
        包含LLM回答的响应
    """
    # 检查是否启用LLM
    use_llm = os.getenv("USE_LLM_PP_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("PP_AGENT_LLM_MODEL", "qwen-max-latest")
    
    explanation = None
    
    if use_llm and openai_api_key and openai_base_url:
        try:
            system_prompt = """你是生产计划(PP)系统的智能助手。你的主要能力包括：
1. 查询生产订单列表和详情
2. 查询报工一览表
3. 查询未报工情况
4. 月结异常检测
5. 订单状态监控

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
            "我是PP Agent，可以帮助您：\n"
            "1. 查询生产订单列表和详情（例如：查询生产订单列表、查看订单001010014285的详情）\n"
            "2. 查询报工一览表（例如：查询报工一览表）\n"
            "3. 查询未报工情况（例如：查询未报工情况）\n"
            "4. 月结异常检测（例如：月结异常检测）\n"
            "5. 订单状态监控（例如：查询订单状态）\n\n"
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

@router.post("/pp-agent/ai-query")
async def pp_ai_query(
    payload: Dict[str, Any],
    pp_service: PPService = Depends(get_pp_service)
) -> Dict[str, Any]:
    """
    PP模块AI查询接口
    
    支持的功能：
    1. 查询生产订单列表
    2. 查询订单详情
    3. 查询报工一览表
    4. 查询未报工情况
    5. 月结异常检测
    6. 订单状态监控
    7. 字段动态调整（核心创新功能）
    8. 页面跳转
    
    Request Body:
        {
            "query": "查询未报工情况"
        }
    
    Returns:
        {
            "success": true,
            "intent": "QUERY_UNREPORTED_WORK",
            "data": {
                "type": "work_report_list",
                "items": [...],
                "total": 100
            }
        }
    """
    try:
        query = payload.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query不能为空")
        
        logger.info(f"收到PP Agent查询: {query}")
        
        # 识别意图：优先使用LLM，失败则使用规则匹配
        extracted = {}
        intent_result = await _identify_intent_with_llm(query)
        if intent_result and intent_result.get("confidence", 0) > 0.7:
            # LLM识别成功且置信度高
            intent = intent_result.get("intent", "SMALLTALK")
            extracted = intent_result.get("extracted", {})
            logger.info(f"LLM识别意图: {intent}, 置信度: {intent_result.get('confidence', 0)}, 提取信息: {extracted}")
        else:
            # 使用规则匹配
            intent = _identify_intent(query)
            logger.info(f"规则识别意图: {intent}")
        
        # 根据意图处理
        if intent == "QUERY_ORDER_LIST":
            # 提取查询参数
            params = {
                "current": 1,
                "size": 20  # 默认每页20条
            }
            matnr = extracted.get("matnr") or _extract_material_number(query)
            if matnr:
                params["matnr"] = matnr
            
            result = await pp_service.get_order_list(params)
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_list",
                    "orders": result.get("data", {}).get("records", []),
                    "total": result.get("data", {}).get("total", 0)
                },
                "message": "查询生产订单列表成功"
            }
        
        elif intent == "QUERY_ORDER_DETAIL":
            # 优先使用LLM提取的订单号，否则使用规则提取
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            if not aufnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供生产订单号，例如：查询生产订单001010014285 或 查看订单001010014285的详情"
                }
            
            result = await pp_service.get_order_detail(aufnr)
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_detail",
                    "order": result.get("data", {})
                },
                "message": f"查询生产订单{aufnr}详情成功"
            }
        
        elif intent == "QUERY_UNREPORTED_WORK":
            # 提取查询参数
            params = {}
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            if aufnr:
                params["aufnr"] = aufnr
            matnr = extracted.get("matnr") or _extract_material_number(query)
            if matnr:
                # 后端接口使用plnbez作为物料号参数
                params["plnbez"] = matnr
            
            result = await pp_service.get_unreported_work_list(params)
            
            # 检查result是否为None或不是字典
            if result is None:
                logger.warning("未报工情况查询返回None")
                return {
                    "success": False,
                    "intent": intent,
                    "message": "查询未报工情况失败：后端返回空数据",
                    "data": {
                        "type": "work_report_list",
                        "items": [],
                        "total": 0
                    }
                }
            
            # IPage对象包含records字段，需要转换为items
            page_data = result.get("data") if isinstance(result, dict) else {}
            if page_data is None:
                page_data = {}
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "work_report_list",
                    "items": page_data.get("records", []) if isinstance(page_data, dict) else [],
                    "total": page_data.get("total", 0) if isinstance(page_data, dict) else 0,
                    "column_config": page_data.get("column_config") if isinstance(page_data, dict) else None
                },
                "message": "查询未报工情况成功"
            }
        
        elif intent == "QUERY_WORK_REPORT":
            # 提取分页参数
            params = {
                "current": payload.get("current", 1),
                "size": payload.get("size", 10)
            }
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            if aufnr:
                params["aufnr"] = aufnr
            matnr = extracted.get("matnr") or _extract_material_number(query)
            if matnr:
                # 后端接口使用plnbez作为物料号参数
                params["plnbez"] = matnr
            
            result = await pp_service.get_work_report_list(params)
            
            # 检查result是否为None或不是字典
            if result is None:
                logger.warning("报工一览表查询返回None")
                return {
                    "success": False,
                    "intent": intent,
                    "message": "查询报工一览表失败：后端返回空数据",
                    "data": {
                        "type": "work_report_list",
                        "items": [],
                        "total": 0,
                        "current": 1,
                        "size": 10,
                        "pages": 0
                    }
                }
            
            # IPage对象包含records字段，需要转换为items
            page_data = result.get("data") if isinstance(result, dict) else {}
            if page_data is None:
                page_data = {}
            
            # 计算总页数
            total = page_data.get("total", 0) if isinstance(page_data, dict) else 0
            size = params.get("size", 10)
            pages = (total + size - 1) // size if total > 0 else 0
            current = params.get("current", 1)
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "work_report_list",
                    "items": page_data.get("records", []) if isinstance(page_data, dict) else [],
                    "total": total,
                    "current": current,
                    "size": size,
                    "pages": pages
                },
                "message": "查询报工一览表成功"
            }
        
        elif intent == "MONTH_END_CHECK":
            result = await pp_service.month_end_check()
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "anomaly_check_result",
                    "result": result.get("data", {})
                },
                "message": "月结异常检测完成"
            }
        
        elif intent == "ORDER_STATUS_MONITOR":
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            if not aufnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供生产订单号"
                }
            
            result = await pp_service.get_order_status(aufnr)
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "status_summary",
                    "status": result.get("data", {})
                },
                "message": f"查询订单{aufnr}状态成功"
            }
        
        elif intent == "ADJUST_COLUMNS":
            # 字段调整逻辑（核心创新功能）
            # 这里返回字段调整指令，由前端处理
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "column_adjustment",
                    "action": "remove" if any(kw in query.lower() for kw in ["移除", "隐藏", "不要显示", "去掉", "删除", "不显示"]) 
                             else "add" if any(kw in query.lower() for kw in ["增加", "添加", "显示", "展示", "包含"])
                             else "reset",
                    "user_message": query
                },
                "message": "字段调整指令已识别"
            }
        
        elif intent.startswith("NAVIGATE_"):
            # 页面跳转
            route_map = {
                "NAVIGATE_ORDER_LIST": "/manufacturing/production-control",
                "NAVIGATE_ORDER_DETAIL": "/manufacturing/production-control/detail",
                "NAVIGATE_WORK_REPORT": "/manufacturing-schedule/productionReport",
                "NAVIGATE_PLANNED_ORDER": "/manufacturing/planned-order/detail",
                "NAVIGATE_MRP": "/manufacturing/material-requirement-planning"
            }
            
            route = route_map.get(intent, "/manufacturing/production-control")
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "navigation",
                    "route": route,
                    "params": {"aufnr": aufnr} if aufnr else {}
                },
                "message": "正在为您跳转..."
            }
        
        else:
            # 闲聊或超出能力范围的问题，使用LLM自动回答
            return await _handle_smalltalk_or_out_of_scope(query, intent)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PP Agent查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/pp-agent/adjust-columns")
async def adjust_columns(
    payload: Dict[str, Any],
    pp_service: PPService = Depends(get_pp_service)
) -> Dict[str, Any]:
    """
    字段动态调整接口
    
    Request Body:
        {
            "action": "add" | "remove" | "reset",
            "fields": ["aufnr", "maktx", ...],
            "user_message": "在工序描述列后面增加工序控制码列",
            "current_columns": [...]
        }
    
    Returns:
        {
            "success": true,
            "columns": [...],
            "message": "已添加工序控制码列"
        }
    """
    try:
        action = payload.get("action", "add")
        fields = payload.get("fields", [])
        user_message = payload.get("user_message", "")
        current_columns = payload.get("current_columns", [])
        
        logger.info(f"收到字段调整请求: action={action}, fields={fields}, user_message={user_message}")
        
        # 默认列配置（与前端保持一致）
        default_columns = [
            {"field": "aufnr", "label": "生产订单号", "visible": True, "width": 160},
            {"field": "plnbez", "label": "物料号", "visible": True, "width": 120},
            {"field": "maktx", "label": "物料描述", "visible": True, "width": 200},
            {"field": "auart", "label": "订单类型", "visible": True, "width": 100},
            {"field": "werks", "label": "工厂", "visible": True, "width": 100},
            {"field": "vornr", "label": "工序", "visible": True, "width": 100},
            {"field": "ltxa1", "label": "工序描述", "visible": True, "width": 150},
            {"field": "steus", "label": "工序控制码", "visible": False, "width": 120},
            {"field": "mgvrg", "label": "目标数量", "visible": True, "width": 120},
            {"field": "lmnga", "label": "已确认数量", "visible": True, "width": 120},
            {"field": "xmnga", "label": "报废数量", "visible": True, "width": 120},
            {"field": "diff_qty", "label": "差异数量", "visible": True, "width": 120},
            {"field": "gmein", "label": "基本计量单位", "visible": True, "width": 120}
        ]
        
        # 字段映射（中文名到字段名）
        field_mappings = {
            "工序控制码": "steus",
            "控制码": "steus",
            "steus": "steus"
        }
        
        # 如果没有提供当前列配置，使用默认配置
        if not current_columns or len(current_columns) == 0:
            current_columns = default_columns.copy()
        
        # 处理字段调整
        result_columns = current_columns.copy()
        message = ""
        
        if action == "add":
            # 添加字段
            fields_to_add = []
            for field in fields:
                # 如果字段不在当前列配置中，添加它
                existing = next((col for col in result_columns if col.get("field") == field), None)
                if not existing:
                    # 从默认配置中查找
                    default_col = next((col for col in default_columns if col.get("field") == field), None)
                    if default_col:
                        # 在工序描述（ltxa1）后面插入
                        ltxa1_index = next((i for i, col in enumerate(result_columns) if col.get("field") == "ltxa1"), -1)
                        if ltxa1_index >= 0:
                            result_columns.insert(ltxa1_index + 1, {**default_col, "visible": True})
                        else:
                            result_columns.append({**default_col, "visible": True})
                        fields_to_add.append(default_col.get("label", field))
            
            # 检查用户消息中是否提到了工序控制码
            if "工序控制码" in user_message or "控制码" in user_message or "steus" in user_message.lower():
                existing_steus = next((col for col in result_columns if col.get("field") == "steus"), None)
                ltxa1_index = next((i for i, col in enumerate(result_columns) if col.get("field") == "ltxa1"), -1)
                
                if not existing_steus:
                    # 如果字段不存在，在工序描述（ltxa1）后面插入工序控制码
                    if ltxa1_index >= 0:
                        result_columns.insert(ltxa1_index + 1, {
                            "field": "steus",
                            "label": "工序控制码",
                            "visible": True,
                            "width": 120
                        })
                        fields_to_add.append("工序控制码")
                else:
                    # 如果字段已存在，确保它在正确的位置（ltxa1后面）且可见
                    current_steus_index = next((i for i, col in enumerate(result_columns) if col.get("field") == "steus"), -1)
                    
                    # 如果不在正确位置，先移除再插入
                    if current_steus_index >= 0 and ltxa1_index >= 0 and current_steus_index != ltxa1_index + 1:
                        steus_col = result_columns.pop(current_steus_index)
                        steus_col["visible"] = True
                        # 重新查找ltxa1的位置（因为索引可能已改变）
                        ltxa1_index = next((i for i, col in enumerate(result_columns) if col.get("field") == "ltxa1"), -1)
                        if ltxa1_index >= 0:
                            result_columns.insert(ltxa1_index + 1, steus_col)
                        else:
                            result_columns.append(steus_col)
                        fields_to_add.append("工序控制码")
                    elif not existing_steus.get("visible", False):
                        # 如果存在但不可见，设置为可见
                        existing_steus["visible"] = True
                        fields_to_add.append("工序控制码")
            
            if fields_to_add:
                message = f"已添加字段：{', '.join(fields_to_add)}"
            else:
                message = "字段调整完成"
        
        elif action == "remove":
            # 移除字段（设置为不可见）
            fields_to_remove = []
            for field in fields:
                for col in result_columns:
                    if col.get("field") == field:
                        col["visible"] = False
                        fields_to_remove.append(col.get("label", field))
            
            if fields_to_remove:
                message = f"已移除字段：{', '.join(fields_to_remove)}"
            else:
                message = "字段调整完成"
        
        elif action == "reset":
            # 重置为默认配置
            result_columns = default_columns.copy()
            message = "已重置为默认列配置"
        
        return {
            "success": True,
            "columns": result_columns,
            "message": message
        }
    
    except Exception as e:
        logger.error(f"字段调整失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"字段调整失败: {str(e)}")
