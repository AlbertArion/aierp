"""
AI规则自迭代学习模块
基于历史数据和LLM实现规则的自动学习和优化
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import statistics
from collections import defaultdict

from ..llm.base_client import LLMClient
from .drools_engine import drools_engine

logger = logging.getLogger(__name__)

class AIRuleLearner:
    """AI规则自迭代学习器"""
    
    def __init__(self):
        self.llm_client = LLMClient(provider="deepseek")
        self.learning_history = []
        self.rule_performance = defaultdict(list)
        self.optimization_suggestions = []
    
    def analyze_rule_performance(self, rule_id: str, days: int = 30) -> Dict[str, Any]:
        """
        分析规则性能数据
        
        Args:
            rule_id: 规则ID
            days: 分析天数
        
        Returns:
            性能分析结果
        """
        try:
            # 模拟获取历史执行数据
            performance_data = self._get_rule_performance_data(rule_id, days)
            
            analysis = {
                "rule_id": rule_id,
                "period": f"最近{days}天",
                "total_executions": performance_data["total_executions"],
                "success_rate": performance_data["success_rate"],
                "average_execution_time": performance_data["avg_time"],
                "false_positive_rate": performance_data["false_positive_rate"],
                "false_negative_rate": performance_data["false_negative_rate"],
                "trend": performance_data["trend"],
                "recommendations": self._generate_performance_recommendations(performance_data)
            }
            
            logger.info(f"规则 {rule_id} 性能分析完成")
            return {"success": True, "analysis": analysis}
            
        except Exception as e:
            logger.error(f"规则性能分析失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_rule_performance_data(self, rule_id: str, days: int) -> Dict[str, Any]:
        """获取规则性能数据（模拟）"""
        # 模拟性能数据
        return {
            "total_executions": 450,
            "success_rate": 0.87,
            "avg_time": 0.23,
            "false_positive_rate": 0.12,
            "false_negative_rate": 0.08,
            "trend": "declining",  # improving, stable, declining
            "execution_times": [0.15, 0.22, 0.31, 0.18, 0.25],
            "success_rates": [0.89, 0.87, 0.85, 0.88, 0.86],
            "trigger_patterns": {
                "time_patterns": ["09:00-11:00", "14:00-16:00"],
                "value_ranges": {"min": 25, "max": 85, "avg": 52}
            }
        }
    
    def _generate_performance_recommendations(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """生成性能优化建议"""
        recommendations = []
        
        if data["false_positive_rate"] > 0.1:
            recommendations.append({
                "type": "condition_tuning",
                "description": "误报率较高，建议调整触发条件",
                "priority": "high"
            })
        
        if data["success_rate"] < 0.9:
            recommendations.append({
                "type": "rule_optimization",
                "description": "成功率偏低，建议优化规则逻辑",
                "priority": "medium"
            })
        
        if data["avg_time"] > 0.5:
            recommendations.append({
                "type": "performance_optimization",
                "description": "执行时间较长，建议优化规则复杂度",
                "priority": "medium"
            })
        
        return recommendations
    
    def learn_from_feedback(self, rule_id: str, feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从用户反馈中学习规则优化
        
        Args:
            rule_id: 规则ID
            feedback_data: 反馈数据列表
        
        Returns:
            学习结果
        """
        try:
            # 分析反馈模式
            feedback_analysis = self._analyze_feedback_patterns(feedback_data)
            
            # 使用LLM生成优化建议
            optimization_suggestions = self._generate_ai_optimization_suggestions(
                rule_id, feedback_analysis
            )
            
            # 记录学习历史
            learning_record = {
                "rule_id": rule_id,
                "timestamp": datetime.now().isoformat(),
                "feedback_count": len(feedback_data),
                "analysis": feedback_analysis,
                "suggestions": optimization_suggestions
            }
            self.learning_history.append(learning_record)
            
            logger.info(f"规则 {rule_id} 反馈学习完成")
            return {"success": True, "learning": learning_record}
            
        except Exception as e:
            logger.error(f"反馈学习失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _analyze_feedback_patterns(self, feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析反馈模式"""
        patterns = {
            "common_issues": [],
            "improvement_areas": [],
            "user_satisfaction": 0.0,
            "frequent_complaints": []
        }
        
        # 模拟反馈分析
        complaint_counts = defaultdict(int)
        satisfaction_scores = []
        
        for feedback in feedback_data:
            if feedback.get("type") == "complaint":
                complaint_counts[feedback.get("issue", "unknown")] += 1
            if "satisfaction" in feedback:
                satisfaction_scores.append(feedback["satisfaction"])
        
        patterns["common_issues"] = list(complaint_counts.keys())[:3]
        patterns["frequent_complaints"] = [
            {"issue": k, "count": v} for k, v in complaint_counts.items()
        ]
        patterns["user_satisfaction"] = (
            statistics.mean(satisfaction_scores) if satisfaction_scores else 0.7
        )
        
        return patterns
    
    def _generate_ai_optimization_suggestions(self, rule_id: str, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """使用AI生成优化建议"""
        try:
            prompt = f"""
            基于以下规则性能分析数据，为规则 {rule_id} 生成具体的优化建议：
            
            分析数据：
            - 常见问题: {analysis.get('common_issues', [])}
            - 用户满意度: {analysis.get('user_satisfaction', 0)}
            - 频繁投诉: {analysis.get('frequent_complaints', [])}
            
            请提供3-5个具体的优化建议，包括：
            1. 条件调整建议
            2. 性能优化建议  
            3. 用户体验改进建议
            
            返回JSON格式，包含suggestions数组。
            """
            
            response = self.llm_client.chat(prompt)
            
            # 解析AI响应（模拟）
            suggestions = [
                {
                    "type": "condition_adjustment",
                    "title": "调整触发阈值",
                    "description": "根据历史数据，建议将触发阈值从30调整为25分钟",
                    "impact": "减少15%的误报率"
                },
                {
                    "type": "performance_optimization", 
                    "title": "优化规则逻辑",
                    "description": "简化条件判断，提升执行效率",
                    "impact": "执行时间减少20%"
                },
                {
                    "type": "user_experience",
                    "title": "改进告警消息",
                    "description": "提供更详细的解决方案和操作指导",
                    "impact": "用户满意度提升10%"
                }
            ]
            
            return suggestions
            
        except Exception as e:
            logger.error(f"AI优化建议生成失败: {e}")
            return []
    
    def auto_optimize_rule(self, rule_id: str) -> Dict[str, Any]:
        """
        自动优化规则
        
        Args:
            rule_id: 规则ID
        
        Returns:
            优化结果
        """
        try:
            # 获取当前规则性能
            performance = self.analyze_rule_performance(rule_id)
            if not performance["success"]:
                return performance
            
            # 获取优化建议
            feedback_data = self._get_recent_feedback(rule_id)
            if feedback_data:
                learning_result = self.learn_from_feedback(rule_id, feedback_data)
                if not learning_result["success"]:
                    return learning_result
            
            # 生成优化后的规则
            optimized_rule = self._generate_optimized_rule(rule_id, performance["analysis"])
            
            # 应用优化
            optimization_result = drools_engine.create_rule(
                f"{rule_id}_optimized", 
                optimized_rule["content"]
            )
            
            if optimization_result["success"]:
                # 记录优化历史
                optimization_record = {
                    "rule_id": rule_id,
                    "timestamp": datetime.now().isoformat(),
                    "optimization": optimized_rule,
                    "performance_before": performance["analysis"],
                    "status": "applied"
                }
                self.optimization_suggestions.append(optimization_record)
                
                logger.info(f"规则 {rule_id} 自动优化完成")
                return {"success": True, "optimization": optimization_record}
            else:
                return optimization_result
                
        except Exception as e:
            logger.error(f"自动优化规则失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_recent_feedback(self, rule_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """获取最近的反馈数据（模拟）"""
        return [
            {
                "type": "complaint",
                "issue": "false_positive",
                "timestamp": datetime.now().isoformat(),
                "details": "规则误报频繁"
            },
            {
                "type": "suggestion", 
                "issue": "threshold_adjustment",
                "timestamp": datetime.now().isoformat(),
                "details": "建议调整触发阈值"
            }
        ]
    
    def _generate_optimized_rule(self, rule_id: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成优化后的规则"""
        # 基于分析结果生成优化建议
        optimizations = []
        
        if analysis["false_positive_rate"] > 0.1:
            optimizations.append("增加更严格的触发条件")
        
        if analysis["success_rate"] < 0.9:
            optimizations.append("优化规则逻辑结构")
        
        # 模拟生成优化后的DRL规则
        optimized_content = f"""
package com.aierp.rules.{rule_id}

import java.util.Map;

rule "{rule_id}_optimized"
    when
        $fact: Map() from entry-point "events"
        eval($fact.get("delay_minutes") != null && $fact.get("delay_minutes") > 25)
        eval($fact.get("priority") != null && $fact.get("priority").equals("high"))
    then
        // 优化后的动作：更精确的条件判断和更快的响应
        System.out.println("优化规则触发: " + $fact.get("source"));
        // 发送分级告警
        // 执行自动修复动作
end
        """.strip()
        
        return {
            "content": optimized_content,
            "optimizations": optimizations,
            "expected_improvement": "25%"
        }
    
    def get_learning_insights(self, rule_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取学习洞察
        
        Args:
            rule_id: 特定规则ID，None表示全局洞察
        
        Returns:
            学习洞察结果
        """
        try:
            insights = {
                "total_optimizations": len(self.optimization_suggestions),
                "average_improvement": "18%",
                "learning_trends": {
                    "performance_improvement": "increasing",
                    "user_satisfaction": "stable", 
                    "optimization_frequency": "weekly"
                },
                "key_insights": [
                    "库存相关规则误报率较高，建议增加上下文判断",
                    "订单处理规则在高峰时段性能下降，需要优化",
                    "用户对告警消息的详细程度要求较高"
                ],
                "recommended_actions": [
                    {
                        "action": "批量优化库存规则",
                        "priority": "high",
                        "expected_impact": "减少30%误报"
                    },
                    {
                        "action": "增加规则执行监控",
                        "priority": "medium", 
                        "expected_impact": "提升15%性能"
                    }
                ]
            }
            
            return {"success": True, "insights": insights}
            
        except Exception as e:
            logger.error(f"获取学习洞察失败: {e}")
            return {"success": False, "error": str(e)}

# 全局AI学习器实例
ai_rule_learner = AIRuleLearner()
