"""
Agent模式适配器
统一处理AI模式和规则模式的意图识别
"""
import logging
import os
import json
import re
import requests
from typing import Dict, Any, Optional
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)

class AgentModeAdapter:
    """Agent模式适配器"""
    
    def __init__(self):
        self.config_service = ConfigService()
    
    async def identify_intent(self, query: str, agent_name: str) -> Dict[str, Any]:
        """
        统一意图识别入口
        
        Args:
            query: 用户查询
            agent_name: Agent名称（fi, mm, pp, sd, co等）
        
        Returns:
            {
                "intent": "意图类型",
                "confidence": 0.0-1.0,
                "extracted": {},
                "mode": "llm" | "rule",
                "unrecognized": False
            }
        """
        # 检查是否启用LLM
        if self.config_service.is_llm_enabled(agent_name):
            # AI模式
            result = await self._identify_with_llm(query, agent_name)
            if result and result.get("intent"):
                result["mode"] = "llm"
                return result
        
        # 规则模式
        result = self._identify_with_rules(query, agent_name)
        if result:
            result["mode"] = "rule"
            return result
        
        # 未识别
        return {
            "intent": None,
            "confidence": 0.0,
            "extracted": {},
            "mode": "rule",
            "unrecognized": True
        }
    
    async def _identify_with_llm(self, query: str, agent_name: str) -> Optional[Dict[str, Any]]:
        """使用LLM识别意图"""
        try:
            llm_config = self.config_service.get_llm_config(agent_name)
            
            if not llm_config.get("api_key") or not llm_config.get("base_url"):
                return None
            
            # 获取Agent特定的system prompt
            system_prompt = self._get_system_prompt(agent_name)
            
            user_prompt = f"用户查询：{query}\n\n请识别意图并提取关键信息。"
            
            resp = requests.post(
                f"{llm_config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {llm_config['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": llm_config['model'],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": llm_config['temperature'],
                    "max_tokens": 300
                },
                timeout=llm_config['timeout']
            )
            
            resp.raise_for_status()
            data = resp.json()
            completion = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 解析JSON响应
            result = self._parse_llm_response(completion)
            if result:
                logger.info(f"LLM识别意图成功 [{agent_name}]: {result}")
                return result
            
        except Exception as e:
            logger.warning(f"LLM意图识别失败 [{agent_name}]: {e}")
        
        return None
    
    def _identify_with_rules(self, query: str, agent_name: str) -> Optional[Dict[str, Any]]:
        """使用规则识别意图"""
        try:
            # 导入各Agent的规则识别函数
            if agent_name == "fi":
                from app.api.v1.fi_agent import _identify_intent, _extract_document_number, _extract_year_month, _extract_account_number
                intent = _identify_intent(query)
                extracted = {}
                extracted["belnr"] = _extract_document_number(query)
                period = _extract_year_month(query)
                if period:
                    extracted.update(period)
                account_code = _extract_account_number(query)
                if account_code:
                    extracted["saknr"] = account_code
                    extracted["account_code"] = account_code
            elif agent_name == "mm":
                from app.api.v1.mm_agent import _identify_intent, _extract_purchase_order_number, _extract_purchase_requisition_number
                intent = _identify_intent(query)
                extracted = {}
                extracted["ebeln"] = _extract_purchase_order_number(query)
                extracted["banfn"] = _extract_purchase_requisition_number(query)
            elif agent_name == "pp":
                from app.api.v1.pp_agent import _identify_intent
                intent = _identify_intent(query)
                extracted = {}
            elif agent_name == "sd":
                from app.api.v1.sd_agent import _identify_intent
                intent = _identify_intent(query)
                extracted = {}
            elif agent_name == "co":
                from app.api.v1.co_agent import _identify_intent
                intent = _identify_intent(query)
                extracted = {}
            else:
                return None
            
            if intent:
                return {
                    "intent": intent,
                    "confidence": 0.7,  # 规则匹配默认置信度
                    "extracted": extracted
                }
        except Exception as e:
            logger.warning(f"规则识别失败 [{agent_name}]: {e}")
        
        return None
    
    def _get_system_prompt(self, agent_name: str) -> str:
        """获取Agent的system prompt"""
        # 这里可以从各Agent文件中提取system prompt
        # 或者存储在配置中
        prompts = {
            "fi": """你是一个财务会计(FI)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_DOCUMENT_LIST - 查询会计凭证列表
2. QUERY_DOCUMENT_DETAIL - 查询会计凭证详情
3. CREATE_DOCUMENT - 创建会计凭证
4. UPDATE_DOCUMENT - 更新会计凭证
5. DELETE_DOCUMENT - 删除会计凭证
6. QUERY_ACCOUNT_LIST - 查询科目列表
7. QUERY_ACCOUNT_DETAIL - 查询科目详情
8. QUERY_ACCOUNT_BALANCE - 查询科目余额
9. QUERY_BALANCE_SHEET - 查询资产负债表
10. QUERY_PROFIT_LOSS - 查询利润表
11. QUERY_CASH_FLOW - 查询现金流量表
12. START_MONTH_END - 启动月结
13. QUERY_MONTH_END_STATUS - 查询月结状态
14. SMALLTALK - 闲聊

请以JSON格式返回结果，格式如下：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "extracted": {
        "belnr": "凭证号（如果提到）",
        "gjahr": "会计年度（如果提到）",
        "monat": "会计期间（如果提到）",
        "saknr": "科目编号（如果提到）"
    }
}""",
            "mm": """你是一个物料管理(MM)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. CREATE_PURCHASE_ORDER - 创建采购订单
2. QUERY_ORDER_LIST - 查询采购订单列表
3. QUERY_ORDER_DETAIL - 查询采购订单详情
4. QUERY_REQUISITION_LIST - 查询采购申请列表
5. QUERY_REQUISITION_DETAIL - 查询采购申请详情
6. SMALLTALK - 闲聊

请以JSON格式返回结果。""",
            "pp": """你是一个生产计划(PP)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_ORDER_DETAIL - 查询生产订单详情
2. QUERY_ORDER_LIST - 查询生产订单列表
3. CREATE_PRODUCTION_ORDER - 创建生产订单
4. CREATE_INTERNAL_ORDER - 创建内部订单
5. QUERY_WORK_REPORT - 查询报工情况
6. CHECK_PRODUCTION_ORDER_MATERIAL - 齐套性检查
7. SMALLTALK - 闲聊

请以JSON格式返回结果。""",
            "sd": """你是一个销售分销(SD)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_ORDER_LIST - 查询销售订单列表
2. QUERY_ORDER_DETAIL - 查询销售订单详情（仅当用户明确要「查看/详情/信息」且未提ATP、物料可用性时使用）
3. ATP_CHECK - 订单的ATP检查/物料可用性检查（用户提到「ATP检查」「物料可用性」「齐套性」「库存检查」「检查库存」等时必选此项，优先级高于查询详情）
4. CREATE_DELIVERY - 创建交货单（用户提到「创建交货单」「生成交货单」「交货」等时使用）
5. CREATE_SALES_ORDER - 创建销售订单
6. QUERY_DELIVERY_LIST - 查询交货单列表
7. QUERY_INVOICE_LIST - 查询发票列表
8. SMALLTALK - 闲聊

重要：若用户同时提到订单号和「ATP」「物料可用性」「可用性检查」「齐套性」「库存检查」等，必须返回 ATP_CHECK，不能返回 QUERY_ORDER_DETAIL。

请以JSON格式返回结果，extracted 中可包含 vbeln（销售订单号）。""",
            "co": """你是一个成本控制(CO)系统的智能助手。请分析用户的查询意图，并提取关键信息。

支持的意图类型：
1. QUERY_ORDER_LIST - 查询订单列表
2. QUERY_ORDER_DETAIL - 查询订单详情
3. QUERY_COST_CENTER - 查询成本中心
4. SMALLTALK - 闲聊

请以JSON格式返回结果。"""
        }
        return prompts.get(agent_name, "你是一个智能助手。请分析用户的查询意图。")
    
    def _parse_llm_response(self, completion: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应"""
        try:
            cleaned = completion.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
            if cleaned.endswith('```'):
                cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            cleaned = cleaned.strip()
            
            result = json.loads(cleaned)
            return result
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            try:
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
                                return result
            except Exception as e:
                logger.warning(f"解析LLM响应失败: {e}")
        except Exception as e:
            logger.warning(f"解析LLM响应失败: {e}")
        return None
