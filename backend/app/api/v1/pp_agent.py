#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PP Agent AI查询接口
支持自然语言查询生产订单、报工情况、月结异常检测等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, AsyncGenerator
import re
import logging
import os
import json
import httpx
import requests  # 保留requests用于非流式请求
import asyncio
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

def _extract_process_number(text: str) -> Optional[str]:
    """从文本中提取工序号（vornr）"""
    patterns = [
        r"(?:工序号|工序|VORNR)[\s\-:：，,]?([0-9]{1,4})",
        r"([0-9]{1,4})[\s\-]?工序",
        r"工序[\s\-:：，,]?([0-9]{1,4})",
        # 匹配"物料XXX，工序YYY"这种格式
        r"物料[^，,]*[，,]\s*工序\s*([0-9]{1,4})",
        r"物料[^，,]*[，,]\s*([0-9]{1,4})\s*工序",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            vornr = match.group(1).strip()
            # 工序号通常是1-4位数字
            if 1 <= len(vornr) <= 4:
                return vornr
    
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
8. GENERATE_ABAP_CODE - 生成ABAP代码（生成、abap、代码等）
9. SMALLTALK - 闲聊或询问如何使用

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "aufnr": "订单号（如果提到）",
        "matnr": "物料号（如果提到）",
        "vornr": "工序号（如果提到）",
        "werks": "工厂（如果提到）"
    },
    "reasoning": "简要说明识别理由"
}

注意：
- 订单号通常是10-12位数字
- 物料号通常是字母+数字组合，至少6位
- 工序号通常是1-4位数字
- 如果用户提到"查看订单XXX"、"订单XXX的详情"、"查询订单XXX"等，应该是QUERY_ORDER_DETAIL
- 如果用户提到"查询XXX订单的报工情况"、"查询XXX物料，XXX工序的报工情况"，应该是QUERY_WORK_REPORT
- 如果只提到"订单列表"、"所有订单"等，应该是QUERY_ORDER_LIST
- 优先提取订单号、物料号、工序号，即使表达不完整也要识别"""

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
    
    # ABAP代码生成意图 - 优先检查，避免被其他规则误识别
    if any(keyword in text_lower for keyword in ["生成abap", "生成abap代码", "生成代码", "abap代码", "生成查询", "根据需求生成", "根据如下需求", "生成查询xxx"]):
        return "GENERATE_ABAP_CODE"
    
    # 字段调整意图（核心创新功能）
    if any(keyword in text_lower for keyword in ["移除", "隐藏", "不要显示", "去掉", "删除", "不显示"]):
        if any(keyword in text_lower for keyword in ["字段", "列", "单位", "类型", "工厂", "工序", "描述"]):
            return "ADJUST_COLUMNS"
    if any(keyword in text_lower for keyword in ["增加", "添加", "显示", "展示", "包含"]):
        if any(keyword in text_lower for keyword in ["字段", "列", "单位", "类型", "工厂", "工序", "描述"]):
            # 排除"显示字段"在生成代码场景中的情况
            if not any(keyword in text_lower for keyword in ["生成", "abap", "代码", "查询xxx"]):
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
    
    # 报工查询意图（包括已报工、部分报工查询）
    if any(keyword in text_lower for keyword in ["报工", "报工情况", "报工一览表", "报工明细", "已报工", "报工完成", "部分报工", "已部分报工"]):
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

async def _generate_abap_code(query: str, tables: list = None, conditions: list = None, fields: list = None) -> Dict[str, Any]:
    """
    根据业务需求生成ABAP代码
    
    Args:
        query: 用户查询文本
        tables: 标准表列表（可选，从查询中提取）
        conditions: 查询条件列表（可选，从查询中提取）
        fields: 显示字段列表（可选，从查询中提取）
        
    Returns:
        包含生成的ABAP代码的响应
    """
    # 检查是否启用LLM
    use_llm = os.getenv("USE_LLM_PP_AGENT", "true").lower() == "true"
    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model = os.getenv("PP_AGENT_LLM_MODEL", "qwen-max-latest")
    
    if not use_llm or not openai_api_key or not openai_base_url:
        return {
            "success": False,
            "message": "LLM服务未配置，无法生成ABAP代码"
        }
    
    try:
        # 构建系统提示词
        system_prompt = """你是一个SAP ABAP开发专家。请根据用户提供的业务需求、标准表、查询条件和显示字段，生成标准的ABAP代码。

要求：
1. 生成完整的ABAP报表程序代码
2. 使用标准的SAP表结构
3. 包含SELECT语句、内表定义、循环处理等
4. 代码要规范、可执行
5. 包含必要的注释说明
6. 使用标准的ABAP语法

代码结构应该包括：
- REPORT声明
- TABLES声明
- TYPES声明（如果使用自定义结构，必须先定义结构类型）
- DATA声明（内表和工作区，包括ALV相关的结构）
- SELECT-OPTIONS（查询条件）
- SELECT语句（数据查询）
- LOOP处理（数据循环，填充ALV内表）
- ALV显示（使用REUSE_ALV_GRID_DISPLAY，支持Excel导出）

重要：自定义结构定义
- 如果代码中使用了自定义结构（如TYPE TABLE OF zcoois_output），必须在使用之前定义该结构
- 使用TYPES语句定义结构类型，包含所有显示字段
- 结构定义应该在DATA声明之前
- 结构字段应该根据显示字段需求定义，包括字段名和数据类型
- 例如：如果显示字段包括"生产订单号、物料号、物料描述"等，则结构应该包含对应的字段（如aufnr、matnr、maktx等）

ALV要求：
- 必须使用ALV方式显示数据，不要使用WRITE语句
- 优先使用REUSE_ALV_GRID_DISPLAY（网格显示，支持Excel导出）
- 定义FIELDCATALOG来指定显示字段的属性（字段名、描述、对齐方式等）
- 使用LAYOUT结构设置ALV显示样式
- 支持Excel导出功能（ALV默认支持）

请直接返回ABAP代码，不要包含markdown代码块标记。"""

        # 构建用户提示词
        user_prompt = f"""请根据以下业务需求生成ABAP代码：

用户需求：{query}
"""
        
        # 如果用户输入中包含了详细的需求描述（如报工一览表-ZCOOIS），尝试提取更多信息
        query_lower = query.lower()
        
        # 提取标准表信息
        if tables:
            user_prompt += f"\n标准表：{', '.join(tables)}"
        else:
            # 尝试从查询中提取表名
            extracted_tables = []
            sap_table_keywords = {
                "报工": ["AUFK", "JEST", "AFVC", "MAKT", "AFKO", "AFVV"],
                "订单": ["AUFK", "AFKO", "AFPO", "JEST"],
                "物料": ["MAKT", "MARA"],
                "采购": ["EKKO", "EKPO", "EKBE", "EKKN"],
                "用户": ["AGR_HIER", "AGR_DEFINE", "AGR_USERS", "USER_ADDRS"]
            }
            for keyword, table_list in sap_table_keywords.items():
                if keyword in query:
                    extracted_tables.extend(table_list)
            if extracted_tables:
                user_prompt += f"\n标准表：{', '.join(list(set(extracted_tables)))}"
        
        # 提取查询条件
        if conditions:
            user_prompt += f"\n查询条件：{', '.join(conditions)}"
        else:
            # 尝试从查询中提取条件
            extracted_conditions = []
            condition_keywords = ["工厂", "生产订单号", "预留单号", "需求日期", "移动类型", "物料号", "用户名", "事务码", "角色"]
            for keyword in condition_keywords:
                if keyword in query:
                    extracted_conditions.append(keyword)
            if extracted_conditions:
                user_prompt += f"\n查询条件：{', '.join(extracted_conditions)}"
        
        # 提取显示字段
        if fields:
            user_prompt += f"\n显示字段：{', '.join(fields)}"
        else:
            # 尝试从查询中提取字段
            extracted_fields = []
            field_keywords = ["生产订单号", "物料号", "物料描述", "订单类型", "工厂", "工序", "目标数量", "已确认数量", "报废数量", "差异数量", "基本计量单位"]
            for keyword in field_keywords:
                if keyword in query:
                    extracted_fields.append(keyword)
            if extracted_fields:
                user_prompt += f"\n显示字段：{', '.join(extracted_fields)}"
        
        user_prompt += "\n\n请生成完整的ABAP报表程序代码，包括：\n1. REPORT声明\n2. TABLES声明（根据标准表）\n3. TYPES声明（如果使用自定义结构，必须先定义结构类型，包含所有显示字段）\n4. DATA声明（内表和工作区，包括ALV相关的结构：FIELDCATALOG、LAYOUT等）\n5. SELECT-OPTIONS（查询条件）\n6. SELECT语句（数据查询，包含表关联）\n7. LOOP处理（数据循环，填充ALV内表）\n8. ALV显示（使用REUSE_ALV_GRID_DISPLAY，支持Excel导出）\n9. 必要的注释说明\n\n重要要求：\n1. 必须使用ALV方式显示，不要使用WRITE语句。需要定义FIELDCATALOG来指定显示字段的属性（字段名、描述、对齐方式等）。\n2. 如果代码中使用了自定义结构（如TYPE TABLE OF zcoois_output），必须在使用之前使用TYPES语句定义该结构，包含所有需要的字段。结构定义应该在DATA声明之前。\n3. 确保生成的代码可以直接运行，所有使用的结构都必须有定义。"
        
        logger.info(f"开始生成ABAP代码，查询：{query}")
        
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
                "temperature": 0.1,  # 降低温度以提高代码准确性
                "max_tokens": 3000  # ABAP代码可能较长
            },
            timeout=180  # 增加超时时间到180秒，因为生成ABAP代码可能需要较长时间
        )
        
        resp.raise_for_status()
        data = resp.json()
        abap_code = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        
        # 清理代码（去掉markdown代码块标记）
        if abap_code:
            # 去掉开头的 ```abap 或 ```
            abap_code = re.sub(r'^```(?:abap)?\s*\n?', '', abap_code, flags=re.IGNORECASE)
            # 去掉结尾的 ```
            abap_code = re.sub(r'\n?```\s*$', '', abap_code)
            abap_code = abap_code.strip()
        
        if abap_code:
            logger.info(f"ABAP代码生成成功，长度: {len(abap_code)}")
            return {
                "success": True,
                "abap_code": abap_code,
                "message": "ABAP代码生成成功"
            }
        else:
            logger.warning("LLM返回空代码")
            return {
                "success": False,
                "message": "ABAP代码生成失败：LLM返回空内容"
            }
            
    except Exception as e:
        logger.error(f"生成ABAP代码失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"ABAP代码生成失败: {str(e)}"
        }

async def _generate_abap_code_stream(
    query: str,
    tables: Optional[list] = None,
    conditions: Optional[list] = None,
    fields: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    流式生成ABAP代码
    
    Args:
        query: 用户查询
        tables: 标准表列表
        conditions: 查询条件列表
        fields: 显示字段列表
        
    Yields:
        SSE格式的数据块
    """
    try:
        # 检查是否启用LLM
        use_llm = os.getenv("USE_LLM_PP_AGENT", "true").lower() == "true"
        openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
        openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        openai_model = os.getenv("PP_AGENT_LLM_MODEL", "qwen-max-latest")
        
        if not use_llm or not openai_api_key or not openai_base_url:
            yield f"data: {json.dumps({'error': 'LLM服务未配置'}, ensure_ascii=False)}\n\n"
            return
        
        # 构建系统提示词（与_generate_abap_code相同）
        system_prompt = """你是一个专业的ABAP开发专家，擅长根据业务需求生成标准的ABAP报表程序代码。

你的任务是：
1. 根据用户提供的业务需求，生成完整的、可运行的ABAP报表程序
2. 使用SAP标准表和标准字段
3. 遵循ABAP编程规范和最佳实践
4. 代码要清晰、易读，包含必要的注释

ABAP报表程序的标准结构包括：
- REPORT声明
- TABLES声明
- TYPES声明（如果使用自定义结构，必须先定义结构类型）
- DATA声明（内表和工作区，包括ALV相关的结构）
- SELECT-OPTIONS（查询条件）
- SELECT语句（数据查询）
- LOOP处理（数据循环，填充ALV内表）
- ALV显示（使用REUSE_ALV_GRID_DISPLAY，支持Excel导出）

重要：自定义结构定义
- 如果代码中使用了自定义结构（如TYPE TABLE OF zcoois_output），必须在使用之前定义该结构
- 使用TYPES语句定义结构类型，包含所有显示字段
- 结构定义应该在DATA声明之前
- 结构字段应该根据显示字段需求定义，包括字段名和数据类型
- 例如：如果显示字段包括"生产订单号、物料号、物料描述"等，则结构应该包含对应的字段（如aufnr、matnr、maktx等）
- 确保所有字段都有正确的数据类型（如CHAR、NUMC、DEC等）

重要要求：
1. 必须使用ALV方式显示数据，不要使用WRITE语句
2. 优先使用REUSE_ALV_GRID_DISPLAY（网格显示，支持Excel导出）
3. 需要定义FIELDCATALOG来指定显示字段的属性（字段名、描述、对齐方式等）
4. 使用LAYOUT结构设置ALV显示样式
5. 支持Excel导出功能（ALV默认支持）
6. 确保生成的代码可以直接运行，所有使用的结构都必须有定义

ALV标准用法：
- 定义内表结构用于ALV显示
- 使用REUSE_ALV_FIELDCATALOG_MERGE或手动构建FIELDCATALOG
- 调用REUSE_ALV_GRID_DISPLAY显示数据
- 使用LAYOUT结构设置ALV显示样式（如列宽、颜色等）

请直接返回ABAP代码，不要包含markdown代码块标记。"""

        # 构建用户提示词（与_generate_abap_code相同）
        user_prompt = f"""请根据以下业务需求生成ABAP代码：

用户需求：{query}
"""
        
        query_lower = query.lower()
        
        # 提取标准表信息
        if tables:
            user_prompt += f"\n标准表：{', '.join(tables)}"
        else:
            extracted_tables = []
            sap_table_keywords = {
                "报工": ["AUFK", "JEST", "AFVC", "MAKT", "AFKO", "AFVV"],
                "订单": ["AUFK", "AFKO", "AFPO", "JEST"],
                "物料": ["MAKT", "MARA"],
                "采购": ["EKKO", "EKPO", "EKBE", "EKKN"],
                "用户": ["AGR_HIER", "AGR_DEFINE", "AGR_USERS", "USER_ADDRS"]
            }
            for keyword, table_list in sap_table_keywords.items():
                if keyword in query:
                    extracted_tables.extend(table_list)
            if extracted_tables:
                user_prompt += f"\n标准表：{', '.join(list(set(extracted_tables)))}"
        
        # 提取查询条件
        if conditions:
            user_prompt += f"\n查询条件：{', '.join(conditions)}"
        else:
            extracted_conditions = []
            condition_keywords = ["工厂", "生产订单号", "预留单号", "需求日期", "移动类型", "物料号", "用户名", "事务码", "角色"]
            for keyword in condition_keywords:
                if keyword in query:
                    extracted_conditions.append(keyword)
            if extracted_conditions:
                user_prompt += f"\n查询条件：{', '.join(extracted_conditions)}"
        
        # 提取显示字段
        if fields:
            user_prompt += f"\n显示字段：{', '.join(fields)}"
        else:
            extracted_fields = []
            field_keywords = ["生产订单号", "物料号", "物料描述", "订单类型", "工厂", "工序", "目标数量", "已确认数量", "报废数量", "差异数量", "基本计量单位"]
            for keyword in field_keywords:
                if keyword in query:
                    extracted_fields.append(keyword)
            if extracted_fields:
                user_prompt += f"\n显示字段：{', '.join(extracted_fields)}"
        
        user_prompt += "\n\n请生成完整的ABAP报表程序代码，包括：\n1. REPORT声明\n2. TABLES声明（根据标准表）\n3. TYPES声明（如果使用自定义结构，必须先定义结构类型，包含所有显示字段）\n4. DATA声明（内表和工作区，包括ALV相关的结构：FIELDCATALOG、LAYOUT等）\n5. SELECT-OPTIONS（查询条件）\n6. SELECT语句（数据查询，包含表关联）\n7. LOOP处理（数据循环，填充ALV内表）\n8. ALV显示（使用REUSE_ALV_GRID_DISPLAY，支持Excel导出）\n9. 必要的注释说明\n\n重要要求：\n1. 必须使用ALV方式显示，不要使用WRITE语句。需要定义FIELDCATALOG来指定显示字段的属性（字段名、描述、对齐方式等）。\n2. 如果代码中使用了自定义结构（如TYPE TABLE OF zcoois_output），必须在使用之前使用TYPES语句定义该结构，包含所有需要的字段。结构定义应该在DATA声明之前。\n3. 确保生成的代码可以直接运行，所有使用的结构都必须有定义。"
        
        logger.info(f"开始流式生成ABAP代码，查询：{query}")
        
        # 使用httpx异步流式请求
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    'POST',
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
                        "max_tokens": 3000,
                        "stream": True  # 启用流式响应
                    }
                ) as response:
                    response.raise_for_status()
                    logger.info(f"LLM流式请求已建立，状态码: {response.status_code}")
                    
                    accumulated_code = ""
                    chunk_count = 0
                    buffer = ""
                    
                    # 异步流式读取数据
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            # 将字节解码为字符串
                            buffer += chunk.decode('utf-8', errors='ignore')
                            
                            # 按行分割处理
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                
                                if not line:
                                    continue
                                
                                try:
                                    if line.startswith('data: '):
                                        data_str = line[6:]  # 去掉 'data: ' 前缀
                                        if data_str.strip() == '[DONE]':
                                            logger.info("收到流结束标记 [DONE]")
                                            break
                                        
                                        data = json.loads(data_str)
                                        delta = data.get('choices', [{}])[0].get('delta', {})
                                        content = delta.get('content', '')
                                        
                                        if content:
                                            chunk_count += 1
                                            accumulated_code += content
                                            
                                            # 每10个chunk记录一次日志
                                            if chunk_count % 10 == 0:
                                                logger.info(f"已接收 {chunk_count} 个数据块，累计长度: {len(accumulated_code)}")
                                            
                                            # 立即发送SSE格式的数据
                                            sse_data = f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                                            yield sse_data
                                except json.JSONDecodeError as e:
                                    logger.warning(f"解析JSON失败，跳过该行: {e}, 行内容: {line[:100]}")
                                    continue
                                except Exception as e:
                                    logger.error(f"处理流式数据时出错: {e}", exc_info=True)
                                    continue
                    
                    logger.info(f"流式数据接收完成，共 {chunk_count} 个数据块，总长度: {len(accumulated_code)}")
            
        except httpx.HTTPError as e:
            logger.error(f"LLM API请求失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': f'LLM API请求失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            return
        except Exception as e:
            logger.error(f"流式生成过程中出错: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': f'流式生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            return
        
        # 清理代码（去掉markdown代码块标记）
        if accumulated_code:
            # 去掉开头的 ```abap 或 ```
            accumulated_code = re.sub(r'^```(?:abap)?\s*\n?', '', accumulated_code, flags=re.IGNORECASE)
            # 去掉结尾的 ```
            accumulated_code = re.sub(r'\n?```\s*$', '', accumulated_code)
            accumulated_code = accumulated_code.strip()
            
            # 发送最终结果
            yield f"data: {json.dumps({'done': True, 'full_code': accumulated_code}, ensure_ascii=False)}\n\n"
            logger.info(f"ABAP代码流式生成成功，长度: {len(accumulated_code)}")
        else:
            yield f"data: {json.dumps({'error': 'LLM返回空代码'}, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        logger.error(f"流式生成ABAP代码失败: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': f'ABAP代码生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"

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
6. 根据需求生成ABAP代码

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
            page_current = payload.get("current", 1)
            page_size = payload.get("size", 20)  # 默认每页20条
            
            params = {
                "current": page_current,
                "size": page_size
            }
            matnr = extracted.get("matnr") or _extract_material_number(query)
            if matnr:
                params["matnr"] = matnr
            
            result = await pp_service.get_order_list(params)
            
            # 获取分页数据
            page_data = result.get("data", {}) if isinstance(result, dict) else {}
            if page_data is None:
                page_data = {}
            
            total = page_data.get("total", 0) if isinstance(page_data, dict) else 0
            records = page_data.get("records", []) if isinstance(page_data, dict) else []
            
            # 计算总页数
            pages = (total + page_size - 1) // page_size if total > 0 else 0
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_list",
                    "orders": records,
                    "total": total,
                    "current": page_current,
                    "size": page_size,
                    "pages": pages
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
            # 检查是否是统计查询（包含"统计"、"有多少个"、"数量"等关键词）
            query_lower = query.lower()
            is_statistics_query = any(keyword in query_lower for keyword in [
                "统计", "有多少", "多少个", "数量", "几条", "多少条", 
                "count", "总数", "合计", "共计"
            ])
            
            # 提取查询参数
            # 对于统计查询，需要先获取总数，然后获取第一页数据用于显示
            page_size = payload.get("size", 10)
            page_current = payload.get("current", 1)
            
            params = {
                "current": page_current,
                "size": page_size  # 统计查询也使用正常分页，先显示第一页
            }
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            if aufnr:
                params["aufnr"] = aufnr
            matnr = extracted.get("matnr") or _extract_material_number(query)
            if matnr:
                # 后端接口使用plnbez作为物料号参数
                params["plnbez"] = matnr
            vornr = extracted.get("vornr") or _extract_process_number(query)
            if vornr:
                params["vornr"] = vornr
            
            result = await pp_service.get_unreported_work_list(params)
            
            # 检查result是否为None或不是字典
            if result is None:
                logger.warning("未报工情况查询返回None")
                if is_statistics_query:
                    return {
                        "success": False,
                        "intent": intent,
                        "message": "统计未报工订单失败：后端返回空数据",
                        "data": {
                            "type": "statistics_with_list",
                            "count": 0,
                            "description": "未报工的订单数量为 0 个。未报工是指已确认数量为0的生产订单工序。",
                            "items": [],
                            "total": 0,
                            "current": 1,
                            "size": 10,
                            "pages": 0
                        }
                    }
                else:
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
            
            # 调试：打印完整的响应结构
            logger.info(f"未报工查询原始响应：{json.dumps(result, ensure_ascii=False, indent=2, default=str)[:2000]}")
            
            # IPage对象包含records字段，需要转换为items
            # Java后端返回格式：{"code": 200, "data": {"records": [...], "total": xxx, ...}, "msg": "success"}
            page_data = result.get("data") if isinstance(result, dict) else {}
            if page_data is None:
                page_data = {}
            
            # 检查page_data的实际类型和内容
            logger.info(f"page_data类型：{type(page_data)}, page_data keys：{page_data.keys() if isinstance(page_data, dict) else 'not a dict'}")
            
            # MyBatis Plus的IPage对象直接包含total和records字段
            total = page_data.get("total", 0) if isinstance(page_data, dict) else 0
            records = page_data.get("records", []) if isinstance(page_data, dict) else []
            
            # 如果records为空但total>0，尝试其他可能的数据结构
            if not records and total > 0:
                # 检查是否是直接返回的IPage对象（可能在某些情况下）
                if isinstance(result, dict) and "records" in result:
                    records = result.get("records", [])
                    total = result.get("total", total)
                    logger.info(f"从result根级别获取records，数量：{len(records)}")
            
            # 调试日志
            logger.info(f"未报工查询结果：total={total}, records数量={len(records)}, page_data类型={type(page_data)}")
            if records and len(records) > 0:
                logger.info(f"第一条记录示例：{records[0] if isinstance(records, list) else 'not a list'}")
            else:
                logger.warning(f"records为空或不是列表，page_data完整内容：{json.dumps(page_data, ensure_ascii=False, default=str)[:1000] if isinstance(page_data, dict) else str(page_data)[:500]}")
            
            # 如果是统计查询，返回统计结果和列表
            if is_statistics_query:
                # 计算总页数
                pages = (total + page_size - 1) // page_size if total > 0 else 0
                
                # 获取默认列配置（与 work_report_list 保持一致）
                default_columns = [
                    {"field": "aufnr", "label": "生产订单号", "visible": True, "width": 160},
                    {"field": "plnbez", "label": "物料号", "visible": True, "width": 120},
                    {"field": "maktx", "label": "物料描述", "visible": True, "width": 200},
                    {"field": "auart", "label": "订单类型", "visible": True, "width": 100},
                    {"field": "werks", "label": "工厂", "visible": True, "width": 100},
                    {"field": "vornr", "label": "工序", "visible": True, "width": 100},
                    {"field": "ltxa1", "label": "工序描述", "visible": True, "width": 150},
                    {"field": "steus", "label": "工序控制码", "visible": False, "width": 120},
                    {"field": "arbid", "label": "工作中心", "visible": False, "width": 120},
                    {"field": "workReportStartDate", "label": "报工开始日期", "visible": False, "width": 150},
                    {"field": "workReportEndDate", "label": "报工结束日期", "visible": False, "width": 150},
                    {"field": "systemStatusText", "label": "系统状态", "visible": False, "width": 120},
                    {"field": "workReportRestTime", "label": "报工休息时间", "visible": False, "width": 120},
                    {"field": "workReportActualPeriod", "label": "报工实际期间", "visible": False, "width": 120},
                    {"field": "mgvrg", "label": "目标数量", "visible": True, "width": 120},
                    {"field": "lmnga", "label": "已确认数量", "visible": True, "width": 120},
                    {"field": "xmnga", "label": "报废数量", "visible": True, "width": 120},
                    {"field": "diff_qty", "label": "差异数量", "visible": True, "width": 120},
                    {"field": "gmein", "label": "基本计量单位", "visible": True, "width": 120}
                ]
                
                # 确保每条记录都包含steus字段
                for record in records:
                    if 'steus' not in record:
                        record['steus'] = record.get('steus', '')
                
                logger.info(f"未报工统计查询：总数={total}, 当前页={page_current}, 每页={page_size}, 记录数={len(records)}")
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "statistics_with_list",
                        "count": total,
                        "description": f"未报工的订单数量为 {total} 个。未报工是指已确认数量为0的生产订单工序。",
                        "items": records,
                        "total": total,
                        "current": page_current,
                        "size": page_size,
                        "pages": pages,
                        "column_config": default_columns
                    },
                    "message": f"统计完成：共有 {total} 个未报工的订单"
                }
            
            # 否则返回列表数据
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "work_report_list",
                    "items": records,
                    "total": total,
                    "column_config": page_data.get("column_config") if isinstance(page_data, dict) else None
                },
                "message": "查询未报工情况成功"
            }
        
        elif intent == "QUERY_WORK_REPORT":
            # 检查报工状态类型
            query_lower = query.lower()
            
            # 检查是否是统计查询
            is_statistics_query = any(keyword in query_lower for keyword in [
                "统计", "有多少", "多少个", "数量", "几条", "多少条", 
                "count", "总数", "合计", "共计"
            ])
            
            # 检查报工状态：未报工、已报工、部分报工
            is_unreported_query = any(keyword in query_lower for keyword in [
                "未报工", "待报工", "未完成报工"
            ])
            is_reported_query = any(keyword in query_lower for keyword in [
                "已报工", "报工完成", "已完成报工", "已完成的报工",
                "展示已报工", "显示已报工", "查询已报工", "已报工的", "已报工列表"
            ])
            is_partial_reported_query = any(keyword in query_lower for keyword in [
                "部分报工", "已部分报工", "部分完成", "已部分完成"
            ])
            
            # 提取分页参数
            params = {
                "current": payload.get("current", 1),
                "size": payload.get("size", 10) if is_statistics_query else payload.get("size", 10)
            }
            aufnr = extracted.get("aufnr") or _extract_order_number(query)
            if aufnr:
                params["aufnr"] = aufnr
            matnr = extracted.get("matnr") or _extract_material_number(query)
            if matnr:
                # 后端接口使用plnbez作为物料号参数
                params["plnbez"] = matnr
            vornr = extracted.get("vornr") or _extract_process_number(query)
            if vornr:
                params["vornr"] = vornr
            
            # 如果查询已报工，直接调用已报工接口（在后端SQL中过滤，效率更高）
            if is_reported_query:
                result = await pp_service.get_reported_work_list(params)
            else:
                # 未报工和部分报工仍然需要在前端过滤，因为需要复杂的逻辑
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
            
            # 获取记录列表，确保包含steus字段（工序控制码）
            # 注意：steus字段应该从afvc表的steus字段获取，需要Java后端在SQL查询中包含该字段
            records = page_data.get("records", []) if isinstance(page_data, dict) else []
            
            # 根据查询类型过滤记录
            # 注意：已报工和未报工查询已经在后端SQL中完成过滤，不需要前端过滤
            filter_description = ""
            if is_reported_query:
                # 已报工查询已经在后端SQL中过滤（selectReportedWorkPage），不需要再次过滤
                filter_description = "已报工是指已确认数量等于目标数量的生产订单工序。"
            elif is_unreported_query:
                # 未报工查询已经在后端SQL中过滤（selectUnreportedWorkPage），不需要再次过滤
                filter_description = "未报工是指已确认数量为0的生产订单工序。"
            elif is_partial_reported_query:
                # 部分报工：已确认数量>0 且 < 目标数量
                filtered_records = []
                for record in records:
                    lmnga = record.get('lmnga', 0) or 0
                    mgvrg = record.get('mgvrg', 0) or 0
                    try:
                        lmnga_num = float(lmnga) if lmnga != '' and lmnga is not None else 0
                        mgvrg_num = float(mgvrg) if mgvrg != '' and mgvrg is not None else 0
                        if lmnga_num > 0.001 and lmnga_num < mgvrg_num - 0.001:
                            filtered_records.append(record)
                    except (ValueError, TypeError):
                        continue
                records = filtered_records
                total = len(filtered_records)
                filter_description = "部分报工是指已确认数量大于0但小于目标数量的生产订单工序。"
            
            # 应用分页（如果需要过滤，已经过滤过了；已报工和未报工查询在后端已完成分页）
            if is_partial_reported_query:
                page_size = payload.get("size", 10)
                page_current = payload.get("current", 1)
                start_idx = (page_current - 1) * page_size
                end_idx = start_idx + page_size
                paginated_records = records[start_idx:end_idx]
                records = paginated_records
                size = page_size
                current = page_current
                pages = (total + size - 1) // size if total > 0 else 0
            
            # 确保每条记录都包含steus字段
            for record in records:
                if 'steus' not in record:
                    record['steus'] = record.get('steus', '')
            
            # 计算报工状态总结（无论是否为统计查询都计算）
            def calculate_work_report_summary(records_list):
                """计算报工状态总结"""
                total_count = len(records_list)
                reported_count = 0  # 已报工：lmnga == mgvrg
                unreported_count = 0  # 未报工：lmnga == 0
                partial_reported_count = 0  # 部分报工：lmnga > 0 && lmnga < mgvrg
                total_mgvrg = 0.0  # 总目标数量
                total_lmnga = 0.0  # 总确认数量
                total_xmnga = 0.0  # 总报废数量
                total_diff_qty = 0.0  # 总差异数量
                
                for record in records_list:
                    try:
                        mgvrg = float(record.get('mgvrg', 0) or 0)
                        lmnga = float(record.get('lmnga', 0) or 0)
                        xmnga = float(record.get('xmnga', 0) or 0)
                        diff_qty = float(record.get('diff_qty', 0) or 0)
                        
                        total_mgvrg += mgvrg
                        total_lmnga += lmnga
                        total_xmnga += xmnga
                        total_diff_qty += diff_qty
                        
                        # 判断报工状态（使用0.001作为浮点数比较的容差）
                        if abs(lmnga - mgvrg) < 0.001 and mgvrg > 0.001:
                            reported_count += 1
                        elif abs(lmnga) < 0.001:
                            unreported_count += 1
                        elif lmnga > 0.001 and lmnga < mgvrg - 0.001:
                            partial_reported_count += 1
                    except (ValueError, TypeError):
                        continue
                
                # 计算完成率
                completion_rate = (total_lmnga / total_mgvrg * 100) if total_mgvrg > 0.001 else 0.0
                
                return {
                    "total_count": total_count,
                    "reported_count": reported_count,
                    "unreported_count": unreported_count,
                    "partial_reported_count": partial_reported_count,
                    "total_mgvrg": round(total_mgvrg, 3),
                    "total_lmnga": round(total_lmnga, 3),
                    "total_xmnga": round(total_xmnga, 3),
                    "total_diff_qty": round(total_diff_qty, 3),
                    "completion_rate": round(completion_rate, 2)
                }
            
            # 为了计算准确的统计信息，需要获取全部数据（不带分页）
            # 但为了性能，我们可以基于当前查询条件获取一个较大的数据集来计算统计
            # 或者基于当前页数据计算（如果数据量不大）
            
            # 如果查询条件包含物料号，需要基于全部数据计算统计
            # 否则基于当前页数据计算
            all_records_for_summary = records
            if matnr or aufnr or vornr:
                # 有查询条件时，获取全部数据来计算统计（使用较大的size）
                summary_params = params.copy()
                summary_params["size"] = 10000  # 获取足够多的数据来计算统计
                summary_params["current"] = 1
                
                try:
                    if is_reported_query:
                        summary_result = await pp_service.get_reported_work_list(summary_params)
                    else:
                        summary_result = await pp_service.get_work_report_list(summary_params)
                    
                    if summary_result and isinstance(summary_result, dict):
                        summary_page_data = summary_result.get("data", {})
                        if isinstance(summary_page_data, dict):
                            all_records_for_summary = summary_page_data.get("records", [])
                            
                            # 如果是部分报工查询，需要过滤
                            if is_partial_reported_query:
                                filtered_all_records = []
                                for record in all_records_for_summary:
                                    lmnga = record.get('lmnga', 0) or 0
                                    mgvrg = record.get('mgvrg', 0) or 0
                                    try:
                                        lmnga_num = float(lmnga) if lmnga != '' and lmnga is not None else 0
                                        mgvrg_num = float(mgvrg) if mgvrg != '' and mgvrg is not None else 0
                                        if lmnga_num > 0.001 and lmnga_num < mgvrg_num - 0.001:
                                            filtered_all_records.append(record)
                                    except (ValueError, TypeError):
                                        continue
                                all_records_for_summary = filtered_all_records
                except Exception as e:
                    logger.warning(f"获取全部数据计算统计失败，使用当前页数据: {e}")
                    all_records_for_summary = records
            
            # 计算总结（基于全部数据或当前页数据）
            summary = calculate_work_report_summary(all_records_for_summary)
            
            # 如果是统计查询，返回统计结果和列表
            if is_statistics_query:
                status_text = ""
                if is_unreported_query:
                    status_text = "未报工"
                elif is_reported_query:
                    status_text = "已报工"
                elif is_partial_reported_query:
                    status_text = "部分报工"
                else:
                    status_text = "报工"
                
                # 获取默认列配置（确保表格有列可显示）
                default_columns = [
                    {"field": "aufnr", "label": "生产订单号", "visible": True, "width": 160},
                    {"field": "plnbez", "label": "物料号", "visible": True, "width": 120},
                    {"field": "maktx", "label": "物料描述", "visible": True, "width": 200},
                    {"field": "auart", "label": "订单类型", "visible": True, "width": 100},
                    {"field": "werks", "label": "工厂", "visible": True, "width": 100},
                    {"field": "vornr", "label": "工序", "visible": True, "width": 100},
                    {"field": "ltxa1", "label": "工序描述", "visible": True, "width": 150},
                    {"field": "steus", "label": "工序控制码", "visible": False, "width": 120},
                    {"field": "arbid", "label": "工作中心", "visible": False, "width": 120},
                    {"field": "workReportStartDate", "label": "报工开始日期", "visible": False, "width": 150},
                    {"field": "workReportEndDate", "label": "报工结束日期", "visible": False, "width": 150},
                    {"field": "systemStatusText", "label": "系统状态", "visible": False, "width": 120},
                    {"field": "workReportRestTime", "label": "报工休息时间", "visible": False, "width": 120},
                    {"field": "workReportActualPeriod", "label": "报工实际期间", "visible": False, "width": 120},
                    {"field": "mgvrg", "label": "目标数量", "visible": True, "width": 120},
                    {"field": "lmnga", "label": "已确认数量", "visible": True, "width": 120},
                    {"field": "xmnga", "label": "报废数量", "visible": True, "width": 120},
                    {"field": "diff_qty", "label": "差异数量", "visible": True, "width": 120},
                    {"field": "gmein", "label": "基本计量单位", "visible": True, "width": 120}
                ]
                
                # 生成总结描述
                summary_text = f"共 {summary['total_count']} 条记录，其中：已报工 {summary['reported_count']} 条，未报工 {summary['unreported_count']} 条，部分报工 {summary['partial_reported_count']} 条。"
                summary_text += f"总目标数量：{summary['total_mgvrg']}，总确认数量：{summary['total_lmnga']}，总报废数量：{summary['total_xmnga']}，完成率：{summary['completion_rate']}%。"
                
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "statistics_with_list",
                        "count": total,
                        "description": f"{status_text}的订单数量为 {total} 个。{filter_description}",
                        "summary": summary,
                        "summary_text": summary_text,
                        "items": records,
                        "total": total,
                        "current": current,
                        "size": size,
                        "pages": pages,
                        "column_config": page_data.get("column_config") if isinstance(page_data, dict) and page_data.get("column_config") else default_columns
                    },
                    "message": f"统计完成：共有 {total} 个{status_text}的订单"
                }
            
            # 否则返回列表数据（也包含总结）
            # 生成消息，包含已报工和未报工的条数统计
            if matnr or aufnr or vornr:
                # 有查询条件时，在消息中显示统计信息
                message = f"共找到 {total} 条记录，其中：已报工 {summary['reported_count']} 条，未报工 {summary['unreported_count']} 条"
                if summary['partial_reported_count'] > 0:
                    message += f"，部分报工 {summary['partial_reported_count']} 条"
                message += "。"
            else:
                message = "查询报工一览表成功"
                if is_unreported_query:
                    message = "查询未报工列表成功"
                elif is_reported_query:
                    message = "查询已报工列表成功"
                elif is_partial_reported_query:
                    message = "查询部分报工列表成功"
            
            # 生成总结描述
            summary_text = f"共 {summary['total_count']} 条记录，其中：已报工 {summary['reported_count']} 条，未报工 {summary['unreported_count']} 条，部分报工 {summary['partial_reported_count']} 条。"
            summary_text += f"总目标数量：{summary['total_mgvrg']}，总确认数量：{summary['total_lmnga']}，总报废数量：{summary['total_xmnga']}，完成率：{summary['completion_rate']}%。"
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "work_report_list",
                    "summary": summary,
                    "summary_text": summary_text,
                    "items": records,
                    "total": total,
                    "current": current,
                    "size": size,
                    "pages": pages,
                    "column_config": page_data.get("column_config") if isinstance(page_data, dict) else None
                },
                "message": message
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
            query_lower = query.lower()
            
            # 检查是否是"只显示"模式（只显示指定字段，隐藏其他所有字段）
            is_show_only = any(kw in query_lower for kw in [
                "只显示", "只需要", "只需要展示", "只展示", "仅显示", "仅展示",
                "只要", "只要显示", "只保留", "仅保留"
            ])
            
            # 检查是否是"隐藏"模式
            is_remove = any(kw in query_lower for kw in ["移除", "隐藏", "不要显示", "去掉", "删除", "不显示"])
            
            # 检查是否是"添加"模式
            is_add = any(kw in query_lower for kw in ["增加", "添加", "新增", "显示", "展示", "包含", "后面", "后方", "之后"])
            
            # 确定action
            if is_show_only:
                action = "show_only"  # 只显示指定字段，隐藏其他
            elif is_remove:
                action = "remove"  # 移除/隐藏指定字段
            elif is_add:
                action = "add"  # 添加/显示指定字段
            else:
                action = "reset"  # 重置为默认
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "column_adjustment",
                    "action": action,
                    "user_message": query
                },
                "message": "字段调整指令已识别"
            }
        
        elif intent == "GENERATE_ABAP_CODE":
            # ABAP代码生成
            # 检查是否使用流式响应（默认使用流式，除非明确指定为False）
            use_stream = payload.get("stream", True)  # 默认使用流式响应
            
            # 从查询中提取表、条件、字段信息（如果用户提供了）
            tables = []
            conditions = []
            fields = []
            
            # 尝试从查询中提取信息
            query_lower = query.lower()
            
            # 提取表名（常见SAP表）
            sap_tables = ["AUFK", "JEST", "AFVC", "MAKT", "AFKO", "AFPO", "AFVV", "EKKO", "EKPO", "EKBE", "EKKN", "MARA", "AGR_HIER", "AGR_DEFINE", "AGR_USERS", "USER_ADDRS"]
            for table in sap_tables:
                if table.lower() in query_lower:
                    tables.append(table)
            
            # 提取查询条件关键词
            condition_keywords = ["工厂", "生产订单号", "预留单号", "需求日期", "移动类型", "物料号", "用户名", "事务码", "角色", "研发内部订单号", "采购订单号"]
            for keyword in condition_keywords:
                if keyword in query:
                    conditions.append(keyword)
            
            # 提取显示字段关键词
            field_keywords = ["生产订单号", "物料号", "物料描述", "订单类型", "工厂", "工序", "目标数量", "已确认数量", "报废数量", "差异数量", "基本计量单位", "用户名", "用户中文名", "角色名", "角色描述", "报表类型", "事务码", "事务码描述"]
            for keyword in field_keywords:
                if keyword in query:
                    fields.append(keyword)
            
            # 如果使用流式响应
            if use_stream:
                return StreamingResponse(
                    _generate_abap_code_stream(
                        query,
                        tables if tables else None,
                        conditions if conditions else None,
                        fields if fields else None
                    ),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # 禁用nginx缓冲
                        "X-Content-Type-Options": "nosniff"
                    }
                )
            
            # 非流式响应（原有逻辑）
            result = await _generate_abap_code(query, tables if tables else None, conditions if conditions else None, fields if fields else None)
            
            if result.get("success"):
                return {
                    "success": True,
                    "intent": intent,
                    "data": {
                        "type": "abap_code",
                        "code": result.get("abap_code", ""),
                        "query": query
                    },
                    "message": result.get("message", "ABAP代码生成成功")
                }
            else:
                return {
                    "success": False,
                    "intent": intent,
                    "message": result.get("message", "ABAP代码生成失败")
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
            {"field": "arbid", "label": "工作中心", "visible": False, "width": 120},
            {"field": "workReportStartDate", "label": "报工开始日期", "visible": False, "width": 150},
            {"field": "workReportEndDate", "label": "报工结束日期", "visible": False, "width": 150},
            {"field": "systemStatusText", "label": "系统状态", "visible": False, "width": 120},
            {"field": "workReportRestTime", "label": "报工休息时间", "visible": False, "width": 120},
            {"field": "workReportActualPeriod", "label": "报工实际期间", "visible": False, "width": 120},
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
            "steus": "steus",
            "STEUS": "steus",
            "工作中心": "arbid",
            "报工开始日期": "workReportStartDate",
            "开始日期": "workReportStartDate",
            "报工结束日期": "workReportEndDate",
            "结束日期": "workReportEndDate",
            "系统状态": "systemStatusText",
            "状态": "systemStatusText",
            "报工休息时间": "workReportRestTime",
            "休息时间": "workReportRestTime",
            "报工实际期间": "workReportActualPeriod",
            "实际期间": "workReportActualPeriod",
            "报工工时": "workReportActualPeriod"
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
            
            # 检查用户消息中是否提到了特定字段，并自动添加
            user_message_lower = user_message.lower()
            
            # 定义需要特殊处理的字段及其关键词
            special_fields = [
                {
                    "field": "steus",
                    "label": "工序控制码",
                    "keywords": ["工序控制码", "控制码", "steus", "STEUS"],
                    "insert_after": "ltxa1"
                },
                {
                    "field": "arbid",
                    "label": "工作中心",
                    "keywords": ["工作中心", "arbid"],
                    "insert_after": "steus"
                },
                {
                    "field": "workReportStartDate",
                    "label": "报工开始日期",
                    "keywords": ["报工开始日期", "开始日期"],
                    "insert_after": "arbid"
                },
                {
                    "field": "workReportEndDate",
                    "label": "报工结束日期",
                    "keywords": ["报工结束日期", "结束日期"],
                    "insert_after": "workReportStartDate"
                },
                {
                    "field": "systemStatusText",
                    "label": "系统状态",
                    "keywords": ["系统状态", "状态"],
                    "insert_after": "workReportEndDate"
                },
                {
                    "field": "workReportRestTime",
                    "label": "报工休息时间",
                    "keywords": ["报工休息时间", "休息时间"],
                    "insert_after": "systemStatusText"
                },
                {
                    "field": "workReportActualPeriod",
                    "label": "报工实际期间",
                    "keywords": ["报工实际期间", "实际期间", "报工工时", "工时"],
                    "insert_after": "workReportRestTime"
                }
            ]
            
            # 检查每个特殊字段
            for field_config in special_fields:
                field_name = field_config["field"]
                field_label = field_config["label"]
                keywords = field_config["keywords"]
                insert_after = field_config["insert_after"]
                
                # 检查用户消息中是否包含该字段的关键词
                if any(kw in user_message or kw.lower() in user_message_lower for kw in keywords):
                    existing_field = next((col for col in result_columns if col.get("field") == field_name), None)
                    insert_after_index = next((i for i, col in enumerate(result_columns) if col.get("field") == insert_after), -1)
                    
                    if not existing_field:
                        # 如果字段不存在，在指定位置插入
                        default_col = next((col for col in default_columns if col.get("field") == field_name), None)
                        if default_col:
                            if insert_after_index >= 0:
                                result_columns.insert(insert_after_index + 1, {**default_col, "visible": True})
                            else:
                                result_columns.append({**default_col, "visible": True})
                            fields_to_add.append(field_label)
                    else:
                        # 如果字段已存在，确保它可见
                        if not existing_field.get("visible", False):
                            existing_field["visible"] = True
                            fields_to_add.append(field_label)
            
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
        
        elif action == "show_only":
            # 只显示指定字段，隐藏其他所有字段
            # 首先，将所有字段设为不可见
            for col in result_columns:
                col["visible"] = False
            
            # 然后，将用户指定的字段设为可见
            fields_to_show = []
            for field in fields:
                for col in result_columns:
                    if col.get("field") == field:
                        col["visible"] = True
                        fields_to_show.append(col.get("label", field))
                        break
            
            # 如果用户消息中提到了字段但没有在fields中找到，尝试从消息中提取
            # 检查所有特殊字段
            special_fields_for_show = [
                {"field": "steus", "label": "工序控制码", "keywords": ["工序控制码", "控制码", "steus"]},
                {"field": "arbid", "label": "工作中心", "keywords": ["工作中心", "arbid"]},
                {"field": "workReportStartDate", "label": "报工开始日期", "keywords": ["报工开始日期", "开始日期"]},
                {"field": "workReportEndDate", "label": "报工结束日期", "keywords": ["报工结束日期", "结束日期"]},
                {"field": "systemStatusText", "label": "系统状态", "keywords": ["系统状态", "状态"]},
                {"field": "workReportRestTime", "label": "报工休息时间", "keywords": ["报工休息时间", "休息时间"]},
                {"field": "workReportActualPeriod", "label": "报工实际期间", "keywords": ["报工实际期间", "实际期间", "报工工时", "工时"]}
            ]
            
            user_message_lower_show = user_message.lower()
            for field_config in special_fields_for_show:
                field_name = field_config["field"]
                field_label = field_config["label"]
                keywords = field_config["keywords"]
                
                if any(kw in user_message or kw.lower() in user_message_lower_show for kw in keywords):
                    for col in result_columns:
                        if col.get("field") == field_name:
                            col["visible"] = True
                            if field_label not in fields_to_show:
                                fields_to_show.append(field_label)
                            break
            
            if fields_to_show:
                message = f"已设置为只显示字段：{', '.join(fields_to_show)}"
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
