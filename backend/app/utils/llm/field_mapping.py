from .base_client import LLMClient
from typing import Dict, Any, List, Optional, Tuple
import json
import re
import logging

logger = logging.getLogger(__name__)


class FieldMappingGenerator:
    """字段映射生成器"""
    
    def __init__(self):
        self.client = LLMClient(provider="qwen")
        self.field_semantics = {
            # 订单相关字段
            "order": ["order", "订单", "order_no", "order_id", "vbeln", "order_number"],
            "customer": ["customer", "客户", "kunnr", "customer_code", "customer_id"],
            "amount": ["amount", "金额", "netwr", "total_amount", "order_amount"],
            "currency": ["currency", "货币", "waerk", "curr", "currency_code"],
            "date": ["date", "日期", "erdat", "order_date", "create_date", "created_at"],
            
            # 财务相关字段
            "company": ["company", "公司", "bukrs", "company_code", "org_id"],
            "fiscal_year": ["fiscal_year", "会计年度", "gjahr", "fiscal_year", "year"],
            "document": ["document", "凭证", "belnr", "voucher_no", "doc_number"],
            "debit": ["debit", "借方", "dmbtr", "debit_amount", "dr_amount"],
            "credit": ["credit", "贷方", "credit_amount", "cr_amount"],
            
            # 库存相关字段
            "material": ["material", "物料", "matnr", "material_code", "item_code"],
            "quantity": ["quantity", "数量", "menge", "qty", "amount"],
            "unit": ["unit", "单位", "meins", "unit_of_measure", "uom"],
            "warehouse": ["warehouse", "仓库", "lgort", "wh_code", "storage_location"],
            
            # 通用字段
            "id": ["id", "标识", "key", "primary_key", "pk"],
            "name": ["name", "名称", "desc", "description", "text"],
            "status": ["status", "状态", "stat", "state", "flag"],
            "created": ["created", "创建", "create_time", "created_at", "insert_time"],
            "updated": ["updated", "更新", "update_time", "updated_at", "modify_time"]
        }
    
    def generate_field_mapping(self, source_fields: List[str], target_fields: List[str], 
                             source_system: str = "", target_system: str = "") -> Dict[str, Any]:
        """生成字段映射规则"""
        try:
            # 构建详细的提示词
            prompt = self._build_mapping_prompt(source_fields, target_fields, source_system, target_system)
            
            # 调用LLM
            result = self.client.chat(prompt, temperature=0.1)
            
            # 解析结果
            mapping_result = self._parse_mapping_result(result)
            
            # 添加置信度评分
            mapping_result["confidence_scores"] = self._calculate_confidence_scores(
                source_fields, target_fields, mapping_result["mappings"]
            )
            
            # 添加字段类型推断
            mapping_result["field_types"] = self._infer_field_types(source_fields + target_fields)
            
            return mapping_result
            
        except Exception as e:
            logger.error(f"生成字段映射失败: {e}")
            return {
                "error": str(e),
                "mappings": {},
                "confidence_scores": {},
                "field_types": {}
            }
    
    def _build_mapping_prompt(self, source_fields: List[str], target_fields: List[str],
                            source_system: str, target_system: str) -> str:
        """构建映射提示词"""
        prompt = f"""
你是一个专业的ERP系统集成专家。请分析以下字段并生成精确的映射关系。

源系统: {source_system}
目标系统: {target_system}

源字段列表:
{json.dumps(source_fields, ensure_ascii=False, indent=2)}

目标字段列表:
{json.dumps(target_fields, ensure_ascii=False, indent=2)}

请按照以下JSON格式返回结果:
{{
    "mappings": {{
        "源字段名": {{
            "target_field": "目标字段名",
            "confidence": 0.95,
            "reason": "映射原因",
            "transformation": "转换规则(如果需要)"
        }}
    }},
    "unmapped_source": ["未映射的源字段"],
    "unmapped_target": ["未映射的目标字段"],
    "suggestions": [
        {{
            "source_field": "源字段",
            "target_field": "目标字段",
            "confidence": 0.8,
            "reason": "建议原因"
        }}
    ],
    "field_analysis": {{
        "source_analysis": "源字段分析",
        "target_analysis": "目标字段分析",
        "mapping_strategy": "映射策略建议"
    }}
}}

注意事项:
1. 基于字段名称的语义相似性进行匹配
2. 考虑字段的业务含义和数据类型
3. 提供置信度评分(0-1)
4. 对于需要转换的字段，提供转换规则
5. 对于无法直接映射的字段，提供建议
"""
        return prompt
    
    def _parse_mapping_result(self, llm_result: str) -> Dict[str, Any]:
        """解析LLM返回的映射结果"""
        try:
            # 尝试直接解析JSON
            if isinstance(llm_result, dict):
                return llm_result
            
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', llm_result, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            
            # 如果无法解析JSON，返回基础结构
            return {
                "mappings": {},
                "unmapped_source": [],
                "unmapped_target": [],
                "suggestions": [],
                "field_analysis": {
                    "source_analysis": "无法解析LLM结果",
                    "target_analysis": "",
                    "mapping_strategy": ""
                }
            }
            
        except Exception as e:
            logger.error(f"解析映射结果失败: {e}")
            return {
                "mappings": {},
                "unmapped_source": [],
                "unmapped_target": [],
                "suggestions": [],
                "field_analysis": {
                    "source_analysis": f"解析错误: {str(e)}",
                    "target_analysis": "",
                    "mapping_strategy": ""
                }
            }
    
    def _calculate_confidence_scores(self, source_fields: List[str], target_fields: List[str],
                                   mappings: Dict[str, Any]) -> Dict[str, float]:
        """计算字段映射的置信度评分"""
        confidence_scores = {}
        
        for source_field, mapping in mappings.items():
            if isinstance(mapping, dict) and "target_field" in mapping:
                target_field = mapping["target_field"]
                
                # 基于语义相似性计算置信度
                semantic_score = self._calculate_semantic_similarity(source_field, target_field)
                
                # 基于字段长度相似性
                length_score = self._calculate_length_similarity(source_field, target_field)
                
                # 基于字符重叠度
                overlap_score = self._calculate_character_overlap(source_field, target_field)
                
                # 综合评分
                confidence = (semantic_score * 0.5 + length_score * 0.2 + overlap_score * 0.3)
                confidence_scores[source_field] = min(confidence, 1.0)
        
        return confidence_scores
    
    def _calculate_semantic_similarity(self, field1: str, field2: str) -> float:
        """计算字段语义相似性"""
        field1_lower = field1.lower()
        field2_lower = field2.lower()
        
        # 检查是否完全匹配
        if field1_lower == field2_lower:
            return 1.0
        
        # 检查语义词典匹配
        for semantic_group in self.field_semantics.values():
            if field1_lower in semantic_group and field2_lower in semantic_group:
                return 0.9
        
        # 检查部分匹配
        if field1_lower in field2_lower or field2_lower in field1_lower:
            return 0.7
        
        # 检查字符重叠
        common_chars = set(field1_lower) & set(field2_lower)
        if common_chars:
            return len(common_chars) / max(len(field1_lower), len(field2_lower))
        
        return 0.0
    
    def _calculate_length_similarity(self, field1: str, field2: str) -> float:
        """计算字段长度相似性"""
        len1, len2 = len(field1), len(field2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        return 1.0 - abs(len1 - len2) / max(len1, len2)
    
    def _calculate_character_overlap(self, field1: str, field2: str) -> float:
        """计算字符重叠度"""
        set1, set2 = set(field1.lower()), set(field2.lower())
        if not set1 or not set2:
            return 0.0
        
        intersection = set1 & set2
        union = set1 | set2
        
        return len(intersection) / len(union)
    
    def _infer_field_types(self, fields: List[str]) -> Dict[str, str]:
        """推断字段类型"""
        field_types = {}
        
        for field in fields:
            field_lower = field.lower()
            
            if any(keyword in field_lower for keyword in ["id", "key", "code", "no", "num"]):
                field_types[field] = "identifier"
            elif any(keyword in field_lower for keyword in ["amount", "price", "cost", "value", "money"]):
                field_types[field] = "numeric"
            elif any(keyword in field_lower for keyword in ["date", "time", "created", "updated"]):
                field_types[field] = "datetime"
            elif any(keyword in field_lower for keyword in ["name", "desc", "text", "title"]):
                field_types[field] = "string"
            elif any(keyword in field_lower for keyword in ["status", "flag", "type", "category"]):
                field_types[field] = "enum"
            elif any(keyword in field_lower for keyword in ["qty", "quantity", "count", "num"]):
                field_types[field] = "integer"
            else:
                field_types[field] = "unknown"
        
        return field_types
    
    def validate_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """验证映射规则"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        for source_field, mapping_info in mapping.get("mappings", {}).items():
            if not isinstance(mapping_info, dict):
                validation_result["errors"].append(f"字段 {source_field} 的映射信息格式错误")
                validation_result["valid"] = False
                continue
            
            if "target_field" not in mapping_info:
                validation_result["errors"].append(f"字段 {source_field} 缺少目标字段")
                validation_result["valid"] = False
            
            if "confidence" in mapping_info:
                confidence = mapping_info["confidence"]
                if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                    validation_result["warnings"].append(f"字段 {source_field} 的置信度值无效: {confidence}")
            
            if "transformation" in mapping_info and not mapping_info["transformation"]:
                validation_result["suggestions"].append(f"字段 {source_field} 可能需要转换规则")
        
        return validation_result


# 保持向后兼容的函数
def generate_field_mapping(source_fields: List[str], target_fields: List[str]) -> Dict[str, Any]:
    """生成字段映射规则（向后兼容）"""
    generator = FieldMappingGenerator()
    return generator.generate_field_mapping(source_fields, target_fields)


