"""
规则分析模块
提供规则执行统计、效果评估和优化建议功能
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class RuleAnalytics:
    """规则分析器"""
    
    def __init__(self):
        self.execution_history = []
        self.performance_metrics = defaultdict(list)
        self.optimization_history = []
    
    def record_execution(self, rule_id: str, execution_data: Dict[str, Any]) -> None:
        """
        记录规则执行数据
        
        Args:
            rule_id: 规则ID
            execution_data: 执行数据
        """
        record = {
            "rule_id": rule_id,
            "timestamp": datetime.now(),
            "execution_time": execution_data.get("execution_time", 0),
            "success": execution_data.get("success", True),
            "matched": execution_data.get("matched", False),
            "facts_count": execution_data.get("facts_count", 0),
            "actions_count": execution_data.get("actions_count", 0),
            "alerts_generated": execution_data.get("alerts_generated", 0),
            "context": execution_data.get("context", {})
        }
        
        self.execution_history.append(record)
        self.performance_metrics[rule_id].append(record)
        
        # 保持最近1000条记录
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]
    
    def get_rule_performance_summary(self, rule_id: str, days: int = 30) -> Dict[str, Any]:
        """
        获取规则性能摘要
        
        Args:
            rule_id: 规则ID
            days: 分析天数
        
        Returns:
            性能摘要
        """
        try:
            # 获取指定时间范围内的执行记录
            cutoff_time = datetime.now() - timedelta(days=days)
            records = [
                r for r in self.performance_metrics.get(rule_id, [])
                if r["timestamp"] >= cutoff_time
            ]
            
            if not records:
                return {
                    "rule_id": rule_id,
                    "period": f"最近{days}天",
                    "total_executions": 0,
                    "message": "无执行记录"
                }
            
            # 计算基本统计
            total_executions = len(records)
            successful_executions = sum(1 for r in records if r["success"])
            matched_executions = sum(1 for r in records if r["matched"])
            
            execution_times = [r["execution_time"] for r in records if r["execution_time"] > 0]
            avg_execution_time = statistics.mean(execution_times) if execution_times else 0
            max_execution_time = max(execution_times) if execution_times else 0
            
            total_alerts = sum(r["alerts_generated"] for r in records)
            avg_alerts_per_execution = total_alerts / total_executions if total_executions > 0 else 0
            
            # 计算成功率
            success_rate = successful_executions / total_executions if total_executions > 0 else 0
            match_rate = matched_executions / total_executions if total_executions > 0 else 0
            
            # 分析趋势
            trend_analysis = self._analyze_trends(records)
            
            # 性能评级
            performance_grade = self._calculate_performance_grade(
                success_rate, avg_execution_time, match_rate
            )
            
            summary = {
                "rule_id": rule_id,
                "period": f"最近{days}天",
                "total_executions": total_executions,
                "success_rate": success_rate,
                "match_rate": match_rate,
                "average_execution_time": avg_execution_time,
                "max_execution_time": max_execution_time,
                "total_alerts_generated": total_alerts,
                "average_alerts_per_execution": avg_alerts_per_execution,
                "performance_grade": performance_grade,
                "trends": trend_analysis,
                "last_execution": records[-1]["timestamp"].isoformat() if records else None
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取规则性能摘要失败: {e}")
            return {"error": str(e)}
    
    def _analyze_trends(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析执行趋势"""
        if len(records) < 2:
            return {"trend": "insufficient_data"}
        
        # 按天分组分析趋势
        daily_stats = defaultdict(lambda: {"executions": 0, "success_rate": 0, "avg_time": 0})
        
        for record in records:
            date_key = record["timestamp"].date()
            daily_stats[date_key]["executions"] += 1
            daily_stats[date_key]["success_rate"] += 1 if record["success"] else 0
            daily_stats[date_key]["avg_time"] += record["execution_time"]
        
        # 计算趋势
        dates = sorted(daily_stats.keys())
        if len(dates) < 2:
            return {"trend": "stable"}
        
        recent_executions = [daily_stats[d]["executions"] for d in dates[-7:]]  # 最近7天
        recent_success_rates = [daily_stats[d]["success_rate"] / daily_stats[d]["executions"] 
                               if daily_stats[d]["executions"] > 0 else 0 
                               for d in dates[-7:]]
        
        # 计算趋势方向
        execution_trend = "increasing" if recent_executions[-1] > recent_executions[0] else "decreasing"
        success_trend = "improving" if recent_success_rates[-1] > recent_success_rates[0] else "declining"
        
        return {
            "execution_trend": execution_trend,
            "success_trend": success_trend,
            "daily_executions": recent_executions,
            "daily_success_rates": recent_success_rates
        }
    
    def _calculate_performance_grade(self, success_rate: float, avg_time: float, match_rate: float) -> str:
        """计算性能评级"""
        score = 0
        
        # 成功率权重40%
        if success_rate >= 0.95:
            score += 40
        elif success_rate >= 0.9:
            score += 30
        elif success_rate >= 0.8:
            score += 20
        else:
            score += 10
        
        # 执行时间权重30%（时间越短越好）
        if avg_time <= 0.1:
            score += 30
        elif avg_time <= 0.5:
            score += 25
        elif avg_time <= 1.0:
            score += 20
        else:
            score += 10
        
        # 匹配率权重30%
        if match_rate >= 0.8:
            score += 30
        elif match_rate >= 0.6:
            score += 20
        elif match_rate >= 0.4:
            score += 15
        else:
            score += 10
        
        # 转换为等级
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "D"
    
    def get_rule_comparison(self, rule_ids: List[str], days: int = 30) -> Dict[str, Any]:
        """
        比较多个规则的性能
        
        Args:
            rule_ids: 规则ID列表
            days: 比较天数
        
        Returns:
            比较结果
        """
        try:
            comparison = {
                "period": f"最近{days}天",
                "rules": [],
                "summary": {}
            }
            
            all_success_rates = []
            all_execution_times = []
            
            for rule_id in rule_ids:
                summary = self.get_rule_performance_summary(rule_id, days)
                if "error" not in summary:
                    comparison["rules"].append(summary)
                    all_success_rates.append(summary["success_rate"])
                    all_execution_times.append(summary["average_execution_time"])
            
            if comparison["rules"]:
                # 计算整体统计
                comparison["summary"] = {
                    "total_rules": len(comparison["rules"]),
                    "average_success_rate": statistics.mean(all_success_rates),
                    "average_execution_time": statistics.mean(all_execution_times),
                    "best_performing_rule": max(comparison["rules"], key=lambda x: x["success_rate"]),
                    "fastest_rule": min(comparison["rules"], key=lambda x: x["average_execution_time"]),
                    "most_active_rule": max(comparison["rules"], key=lambda x: x["total_executions"])
                }
            
            return comparison
            
        except Exception as e:
            logger.error(f"规则比较分析失败: {e}")
            return {"error": str(e)}
    
    def generate_optimization_recommendations(self, rule_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        生成优化建议
        
        Args:
            rule_id: 规则ID
            days: 分析天数
        
        Returns:
            优化建议列表
        """
        try:
            summary = self.get_rule_performance_summary(rule_id, days)
            if "error" in summary or summary.get("total_executions", 0) == 0:
                # 如果没有执行数据，返回通用建议
                return [
                    {
                        "type": "general",
                        "priority": "low",
                        "title": "规则初始化建议",
                        "description": "规则刚创建，建议先进行测试运行",
                        "suggestions": [
                            "添加测试数据验证规则逻辑",
                            "监控规则执行性能",
                            "根据实际使用情况调整规则"
                        ]
                    }
                ]
            
            recommendations = []
            
            # 基于成功率的建议
            if summary["success_rate"] < 0.9:
                recommendations.append({
                    "type": "reliability",
                    "priority": "high",
                    "title": "提升规则可靠性",
                    "description": f"当前成功率{summary['success_rate']:.1%}偏低，建议检查规则逻辑",
                    "suggestions": [
                        "检查条件表达式的准确性",
                        "增加异常处理机制",
                        "优化规则执行顺序"
                    ]
                })
            
            # 基于执行时间的建议
            if summary["average_execution_time"] > 1.0:
                recommendations.append({
                    "type": "performance",
                    "priority": "medium",
                    "title": "优化执行性能",
                    "description": f"平均执行时间{summary['average_execution_time']:.2f}s较长",
                    "suggestions": [
                        "简化规则条件判断",
                        "优化数据访问模式",
                        "考虑并行处理"
                    ]
                })
            
            # 基于匹配率的建议
            if summary["match_rate"] < 0.5:
                recommendations.append({
                    "type": "efficiency",
                    "priority": "medium",
                    "title": "提高规则匹配效率",
                    "description": f"匹配率{summary['match_rate']:.1%}较低，可能触发条件过于严格",
                    "suggestions": [
                        "放宽触发条件",
                        "增加更多匹配场景",
                        "优化条件组合逻辑"
                    ]
                })
            
            # 基于趋势的建议
            if summary.get("trends", {}).get("success_trend") == "declining":
                recommendations.append({
                    "type": "trend",
                    "priority": "high",
                    "title": "关注性能下降趋势",
                    "description": "规则性能呈下降趋势，需要及时干预",
                    "suggestions": [
                        "分析性能下降原因",
                        "考虑规则重构",
                        "增加监控告警"
                    ]
                })
            
            # 基于告警频率的建议
            if summary["average_alerts_per_execution"] > 5:
                recommendations.append({
                    "type": "alerting",
                    "priority": "low",
                    "title": "优化告警频率",
                    "description": "每次执行生成告警较多，可能影响用户体验",
                    "suggestions": [
                        "合并相似告警",
                        "设置告警阈值",
                        "优化告警内容"
                    ]
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            return []
    
    def get_system_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        获取系统级分析
        
        Args:
            days: 分析天数
        
        Returns:
            系统分析结果
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            recent_records = [r for r in self.execution_history if r["timestamp"] >= cutoff_time]
            
            if not recent_records:
                return {"message": "无分析数据"}
            
            # 按规则分组统计
            rule_stats = defaultdict(lambda: {
                "executions": 0,
                "successes": 0,
                "matches": 0,
                "total_time": 0,
                "alerts": 0
            })
            
            for record in recent_records:
                rule_id = record["rule_id"]
                rule_stats[rule_id]["executions"] += 1
                rule_stats[rule_id]["successes"] += 1 if record["success"] else 0
                rule_stats[rule_id]["matches"] += 1 if record["matched"] else 0
                rule_stats[rule_id]["total_time"] += record["execution_time"]
                rule_stats[rule_id]["alerts"] += record["alerts_generated"]
            
            # 计算系统级指标
            total_executions = len(recent_records)
            total_successes = sum(1 for r in recent_records if r["success"])
            total_matches = sum(1 for r in recent_records if r["matched"])
            total_alerts = sum(r["alerts_generated"] for r in recent_records)
            
            system_metrics = {
                "period": f"最近{days}天",
                "total_executions": total_executions,
                "total_rules": len(rule_stats),
                "system_success_rate": total_successes / total_executions if total_executions > 0 else 0,
                "system_match_rate": total_matches / total_executions if total_executions > 0 else 0,
                "total_alerts_generated": total_alerts,
                "average_execution_time": statistics.mean([r["execution_time"] for r in recent_records]),
                "most_active_rules": sorted(
                    [(rule_id, stats["executions"]) for rule_id, stats in rule_stats.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:5],
                "most_reliable_rules": sorted(
                    [(rule_id, stats["successes"] / stats["executions"] if stats["executions"] > 0 else 0) 
                     for rule_id, stats in rule_stats.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            }
            
            return system_metrics
            
        except Exception as e:
            logger.error(f"获取系统分析失败: {e}")
            return {"error": str(e)}
    
    def export_analytics_data(self, rule_id: str = None, days: int = 30) -> Dict[str, Any]:
        """
        导出分析数据
        
        Args:
            rule_id: 特定规则ID，None表示所有规则
            days: 导出天数
        
        Returns:
            导出数据
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            if rule_id:
                # 导出特定规则数据
                records = [
                    r for r in self.performance_metrics.get(rule_id, [])
                    if r["timestamp"] >= cutoff_time
                ]
                summary = self.get_rule_performance_summary(rule_id, days)
                recommendations = self.generate_optimization_recommendations(rule_id, days)
            else:
                # 导出所有规则数据
                records = [r for r in self.execution_history if r["timestamp"] >= cutoff_time]
                summary = self.get_system_analytics(days)
                recommendations = []
            
            export_data = {
                "export_time": datetime.now().isoformat(),
                "period": f"最近{days}天",
                "rule_id": rule_id,
                "summary": summary,
                "execution_records": [
                    {
                        "timestamp": r["timestamp"].isoformat(),
                        "rule_id": r["rule_id"],
                        "execution_time": r["execution_time"],
                        "success": r["success"],
                        "matched": r["matched"],
                        "alerts_generated": r["alerts_generated"]
                    }
                    for r in records
                ],
                "recommendations": recommendations
            }
            
            return {"success": True, "data": export_data}
            
        except Exception as e:
            logger.error(f"导出分析数据失败: {e}")
            return {"success": False, "error": str(e)}

# 全局规则分析器实例
rule_analytics = RuleAnalytics()
