"""
分级报警系统模块
实现完整的告警分级、解决方案输出和自动处理机制
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """告警级别枚举"""
    INFO = "info"           # 信息级别
    WARNING = "warning"     # 警告级别  
    ERROR = "error"         # 错误级别
    CRITICAL = "critical"   # 严重级别
    EMERGENCY = "emergency" # 紧急级别

class AlertCategory(Enum):
    """告警分类枚举"""
    SYSTEM = "system"           # 系统告警
    BUSINESS = "business"       # 业务告警
    PERFORMANCE = "performance" # 性能告警
    SECURITY = "security"       # 安全告警
    DATA = "data"              # 数据告警

class AlertClassifier:
    """分级报警分类器"""
    
    def __init__(self):
        self.alert_rules = self._initialize_alert_rules()
        self.escalation_policies = self._initialize_escalation_policies()
        self.auto_resolution_rules = self._initialize_auto_resolution_rules()
        self.notification_channels = self._initialize_notification_channels()
    
    def _initialize_alert_rules(self) -> Dict[str, Any]:
        """初始化告警规则"""
        return {
            "system": {
                "cpu_usage": {
                    "levels": {
                        "warning": {"threshold": 70, "message": "CPU使用率偏高"},
                        "error": {"threshold": 85, "message": "CPU使用率过高"},
                        "critical": {"threshold": 95, "message": "CPU使用率严重过高"}
                    }
                },
                "memory_usage": {
                    "levels": {
                        "warning": {"threshold": 75, "message": "内存使用率偏高"},
                        "error": {"threshold": 90, "message": "内存使用率过高"},
                        "critical": {"threshold": 95, "message": "内存使用率严重过高"}
                    }
                }
            },
            "business": {
                "order_delay": {
                    "levels": {
                        "info": {"threshold": 15, "message": "订单处理略有延迟"},
                        "warning": {"threshold": 30, "message": "订单处理延迟"},
                        "error": {"threshold": 60, "message": "订单处理严重延迟"},
                        "critical": {"threshold": 120, "message": "订单处理超时"}
                    }
                },
                "inventory_low": {
                    "levels": {
                        "warning": {"threshold": 10, "message": "库存不足"},
                        "error": {"threshold": 5, "message": "库存严重不足"},
                        "critical": {"threshold": 1, "message": "库存告急"}
                    }
                }
            },
            "performance": {
                "response_time": {
                    "levels": {
                        "warning": {"threshold": 2000, "message": "响应时间较慢"},
                        "error": {"threshold": 5000, "message": "响应时间过慢"},
                        "critical": {"threshold": 10000, "message": "响应时间严重超时"}
                    }
                }
            }
        }
    
    def _initialize_escalation_policies(self) -> Dict[str, Any]:
        """初始化升级策略"""
        return {
            "default": {
                "levels": {
                    "info": {"notify": ["system"], "escalate_after": 3600},
                    "warning": {"notify": ["system", "admin"], "escalate_after": 1800},
                    "error": {"notify": ["system", "admin", "manager"], "escalate_after": 900},
                    "critical": {"notify": ["all"], "escalate_after": 300},
                    "emergency": {"notify": ["all"], "escalate_immediately": True}
                }
            },
            "business_critical": {
                "levels": {
                    "warning": {"notify": ["admin", "manager"], "escalate_after": 600},
                    "error": {"notify": ["all"], "escalate_after": 300},
                    "critical": {"notify": ["all"], "escalate_immediately": True}
                }
            }
        }
    
    def _initialize_auto_resolution_rules(self) -> Dict[str, Any]:
        """初始化自动解决规则"""
        return {
            "order_retry": {
                "conditions": ["order_delay", "error"],
                "actions": ["retry_processing", "notify_admin"],
                "max_retries": 3,
                "retry_interval": 60
            },
            "inventory_alert": {
                "conditions": ["inventory_low", "warning"],
                "actions": ["auto_reorder", "notify_purchasing"],
                "auto_reorder_threshold": 5
            },
            "system_restart": {
                "conditions": ["system_error", "critical"],
                "actions": ["restart_service", "notify_devops"],
                "restart_delay": 30
            }
        }
    
    def _initialize_notification_channels(self) -> Dict[str, Any]:
        """初始化通知渠道"""
        return {
            "email": {
                "enabled": True,
                "templates": {
                    "alert": "templates/alert_email.html",
                    "escalation": "templates/escalation_email.html"
                }
            },
            "sms": {
                "enabled": True,
                "levels": ["critical", "emergency"]
            },
            "webhook": {
                "enabled": True,
                "urls": {
                    "slack": "https://hooks.slack.com/...",
                    "teams": "https://outlook.office.com/webhook/..."
                }
            },
            "dashboard": {
                "enabled": True,
                "real_time": True
            }
        }
    
    def classify_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分类告警
        
        Args:
            alert_data: 告警数据
        
        Returns:
            分类结果
        """
        try:
            # 提取关键信息
            source = alert_data.get("source", "unknown")
            metric = alert_data.get("metric", "unknown")
            value = alert_data.get("value", 0)
            
            # 确定告警级别
            level, message = self._determine_alert_level(source, metric, value)
            
            # 确定告警分类
            category = self._determine_alert_category(source, metric)
            
            # 生成解决方案
            solutions = self._generate_solutions(source, metric, level, value)
            
            # 确定通知策略
            notification_strategy = self._get_notification_strategy(category, level)
            
            # 确定自动处理策略
            auto_resolution = self._get_auto_resolution_strategy(source, metric, level)
            
            classification = {
                "alert_id": self._generate_alert_id(),
                "level": level,
                "category": category,
                "message": message,
                "solutions": solutions,
                "notification_strategy": notification_strategy,
                "auto_resolution": auto_resolution,
                "priority": self._calculate_priority(level, category),
                "estimated_resolution_time": self._estimate_resolution_time(level, category),
                "created_at": datetime.now().isoformat()
            }
            
            logger.info(f"告警分类完成: {classification['alert_id']}")
            return {"success": True, "classification": classification}
            
        except Exception as e:
            logger.error(f"告警分类失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _determine_alert_level(self, source: str, metric: str, value: float) -> Tuple[str, str]:
        """确定告警级别"""
        # 查找匹配的规则
        rule_path = f"{source}.{metric}" if source in self.alert_rules else None
        if not rule_path:
            # 默认规则
            if value > 100:
                return "critical", f"{metric}值严重超标"
            elif value > 80:
                return "error", f"{metric}值超标"
            elif value > 60:
                return "warning", f"{metric}值偏高"
            else:
                return "info", f"{metric}值正常"
        
        # 根据规则确定级别
        rules = self.alert_rules.get(source, {}).get(metric, {})
        levels = rules.get("levels", {})
        
        for level in ["critical", "error", "warning", "info"]:
            if level in levels:
                threshold = levels[level].get("threshold", 0)
                if value >= threshold:
                    return level, levels[level].get("message", f"{metric}触发{level}告警")
        
        return "info", f"{metric}值正常"
    
    def _determine_alert_category(self, source: str, metric: str) -> str:
        """确定告警分类"""
        category_mapping = {
            "system": AlertCategory.SYSTEM,
            "performance": AlertCategory.PERFORMANCE,
            "business": AlertCategory.BUSINESS,
            "security": AlertCategory.SECURITY,
            "data": AlertCategory.DATA
        }
        
        # 根据来源和指标确定分类
        if "cpu" in metric or "memory" in metric or "disk" in metric:
            return AlertCategory.SYSTEM.value
        elif "response" in metric or "latency" in metric:
            return AlertCategory.PERFORMANCE.value
        elif "order" in metric or "inventory" in metric:
            return AlertCategory.BUSINESS.value
        elif source in category_mapping:
            return category_mapping[source].value
        else:
            return AlertCategory.SYSTEM.value
    
    def _generate_solutions(self, source: str, metric: str, level: str, value: float) -> List[Dict[str, str]]:
        """生成解决方案"""
        solutions = []
        
        # 基础解决方案模板
        solution_templates = {
            "cpu_usage": [
                {
                    "type": "immediate",
                    "title": "检查系统负载",
                    "description": "查看当前运行的进程和系统负载情况",
                    "command": "top -p $(pgrep -f 'python')"
                },
                {
                    "type": "short_term",
                    "title": "重启相关服务",
                    "description": "重启占用CPU较高的服务",
                    "command": "systemctl restart aierp-backend"
                },
                {
                    "type": "long_term",
                    "title": "扩容服务器资源",
                    "description": "考虑增加CPU核心数或升级服务器",
                    "action": "contact_devops"
                }
            ],
            "order_delay": [
                {
                    "type": "immediate",
                    "title": "检查订单处理队列",
                    "description": "查看是否有订单处理阻塞",
                    "command": "kubectl logs -f order-processor"
                },
                {
                    "type": "immediate",
                    "title": "手动重试失败订单",
                    "description": "重试处理失败的订单",
                    "action": "retry_failed_orders"
                },
                {
                    "type": "short_term",
                    "title": "增加处理实例",
                    "description": "临时增加订单处理实例数量",
                    "action": "scale_order_processor"
                }
            ],
            "inventory_low": [
                {
                    "type": "immediate",
                    "title": "检查库存数据",
                    "description": "验证库存数据的准确性",
                    "action": "verify_inventory_data"
                },
                {
                    "type": "immediate",
                    "title": "自动补货",
                    "description": "触发自动补货流程",
                    "action": "auto_reorder"
                },
                {
                    "type": "short_term",
                    "title": "联系供应商",
                    "description": "紧急联系供应商安排补货",
                    "action": "contact_supplier"
                }
            ]
        }
        
        # 获取对应的解决方案
        key = metric if metric in solution_templates else source
        if key in solution_templates:
            solutions = solution_templates[key]
        
        # 根据级别过滤解决方案
        if level in ["info", "warning"]:
            solutions = [s for s in solutions if s["type"] != "immediate"]
        
        return solutions[:3]  # 最多返回3个解决方案
    
    def _get_notification_strategy(self, category: str, level: str) -> Dict[str, Any]:
        """获取通知策略"""
        policy = self.escalation_policies.get("default", {})
        if category == "business":
            policy = self.escalation_policies.get("business_critical", policy)
        
        level_config = policy.get("levels", {}).get(level, {})
        
        return {
            "channels": level_config.get("notify", ["system"]),
            "escalate_after": level_config.get("escalate_after", 3600),
            "immediate": level_config.get("escalate_immediately", False),
            "repeat_interval": self._get_repeat_interval(level)
        }
    
    def _get_auto_resolution_strategy(self, source: str, metric: str, level: str) -> Dict[str, Any]:
        """获取自动解决策略"""
        # 查找匹配的自动解决规则
        for rule_name, rule_config in self.auto_resolution_rules.items():
            conditions = rule_config.get("conditions", [])
            if (source in conditions or metric in conditions) and level in conditions:
                return {
                    "enabled": True,
                    "rule_name": rule_name,
                    "actions": rule_config.get("actions", []),
                    "max_retries": rule_config.get("max_retries", 1),
                    "retry_interval": rule_config.get("retry_interval", 60)
                }
        
        # 默认策略
        return {
            "enabled": False,
            "reason": "无匹配的自动解决规则"
        }
    
    def _calculate_priority(self, level: str, category: str) -> int:
        """计算优先级（1-10，10最高）"""
        level_priority = {
            "info": 2,
            "warning": 4,
            "error": 6,
            "critical": 8,
            "emergency": 10
        }
        
        category_priority = {
            "system": 1,
            "performance": 2,
            "business": 3,
            "security": 4,
            "data": 2
        }
        
        base_priority = level_priority.get(level, 1)
        category_boost = category_priority.get(category, 1)
        
        return min(10, base_priority + category_boost - 1)
    
    def _estimate_resolution_time(self, level: str, category: str) -> int:
        """估算解决时间（分钟）"""
        time_estimates = {
            "info": {"system": 30, "business": 60, "performance": 45, "security": 20, "data": 90},
            "warning": {"system": 60, "business": 120, "performance": 90, "security": 30, "data": 180},
            "error": {"system": 120, "business": 240, "performance": 180, "security": 60, "data": 360},
            "critical": {"system": 240, "business": 480, "performance": 360, "security": 120, "data": 720},
            "emergency": {"system": 480, "business": 960, "performance": 720, "security": 240, "data": 1440}
        }
        
        return time_estimates.get(level, {}).get(category, 120)
    
    def _get_repeat_interval(self, level: str) -> int:
        """获取重复通知间隔（秒）"""
        intervals = {
            "info": 3600,      # 1小时
            "warning": 1800,   # 30分钟
            "error": 900,      # 15分钟
            "critical": 300,   # 5分钟
            "emergency": 60    # 1分钟
        }
        return intervals.get(level, 1800)
    
    def _generate_alert_id(self) -> str:
        """生成告警ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"ALERT_{timestamp}_{hash(timestamp) % 10000:04d}"
    
    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        获取告警统计信息
        
        Args:
            days: 统计天数
        
        Returns:
            统计结果
        """
        try:
            # 模拟统计数据
            stats = {
                "period": f"最近{days}天",
                "total_alerts": 156,
                "by_level": {
                    "info": 45,
                    "warning": 67,
                    "error": 32,
                    "critical": 10,
                    "emergency": 2
                },
                "by_category": {
                    "system": 78,
                    "business": 45,
                    "performance": 23,
                    "security": 8,
                    "data": 2
                },
                "resolution_time": {
                    "average": 125,  # 分钟
                    "by_level": {
                        "info": 45,
                        "warning": 89,
                        "error": 156,
                        "critical": 287,
                        "emergency": 445
                    }
                },
                "auto_resolution_rate": 0.68,
                "escalation_count": 23,
                "trends": {
                    "alert_frequency": "increasing",
                    "resolution_efficiency": "improving",
                    "auto_resolution_usage": "stable"
                }
            }
            
            return {"success": True, "statistics": stats}
            
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {"success": False, "error": str(e)}

# 全局告警分类器实例
alert_classifier = AlertClassifier()
