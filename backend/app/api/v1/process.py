from fastapi import APIRouter
from typing import Any, Dict, List
from ...repository.process_repo import list_alerts, insert_alert
from ...repository.rule_repo import list_rules, create_rule, update_rule, delete_rule
from ...schemas.rule import ProcessRule
from ...schemas.process import ProcessAlert
from ...utils.rules.drools_engine import drools_engine
from ...utils.rules.ai_rule_learning import ai_rule_learner
from ...utils.rules.alert_classifier import alert_classifier
from ...utils.rules.rule_analytics import rule_analytics
import time
import logging

logger = logging.getLogger(__name__)

# 说明：流程监管模块接口，集成Drools、AI学习和分级告警

router = APIRouter()


@router.get("/alerts")
async def get_alerts() -> Dict[str, Any]:
    alerts = list_alerts()
    return {"alerts": alerts}


@router.post("/alerts")
async def create_alert(alert: ProcessAlert) -> Dict[str, Any]:
    data = alert.dict()
    if not data.get("created_at"):
        data["created_at"] = time.time()
    inserted_id = insert_alert(data)
    return {"id": inserted_id}


@router.get("/rules")
async def get_rules() -> Dict[str, Any]:
    return {"items": list_rules()}


@router.post("/rules")
async def add_rule(rule: ProcessRule) -> Dict[str, Any]:
    rid = create_rule(rule.dict())
    return {"id": rid}


@router.put("/rules/{rule_id}")
async def edit_rule(rule_id: str, rule: ProcessRule) -> Dict[str, Any]:
    ok = update_rule(rule_id, rule.dict())
    return {"updated": ok}


@router.delete("/rules/{rule_id}")
async def remove_rule(rule_id: str) -> Dict[str, Any]:
    ok = delete_rule(rule_id)
    return {"deleted": ok}


def _match_condition(event: dict, cond: dict) -> bool:
    if cond.get("field") not in event:
        return False
    val = event.get(cond["field"])  # type: ignore[index]
    op = cond.get("op")
    ref = cond.get("value")
    try:
        if op == "gt":
            return val > ref
        if op == "gte":
            return val >= ref
        if op == "lt":
            return val < ref
        if op == "lte":
            return val <= ref
        if op == "eq":
            return val == ref
        if op == "neq":
            return val != ref
        if op == "contains":
            return str(ref) in str(val)
        return False
    except Exception:
        return False


@router.post("/events")
async def post_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """处理事件并触发规则执行"""
    triggered: list[str] = []
    classified_alerts = []
    
    # 1. 传统简单规则匹配
    rules = list_rules()
    for r in rules:
        if not r.get("enabled", True):
            continue
        cond = r.get("condition", {})
        if _match_condition(event, cond):
            # 使用分级告警系统处理
            classification = alert_classifier.classify_alert({
                "source": event.get("source", "event"),
                "metric": cond.get("field", "unknown"),
                "value": event.get(cond.get("field", ""), 0)
            })
            
            if classification["success"]:
                alert_data = classification["classification"]
                insert_alert({
                    "level": alert_data["level"],
                    "message": alert_data["message"],
                    "solution": alert_data["solutions"][0]["description"] if alert_data["solutions"] else cond.get("solution"),
                    "source": event.get("source", "event"),
                    "created_at": time.time(),
                    "extra": {
                        "event": event, 
                        "rule": r,
                        "classification": alert_data
                    },
                })
                classified_alerts.append(alert_data)
            triggered.append(r.get("name", "rule"))
    
    # 2. Drools规则引擎执行
    try:
        # 获取所有Drools规则并执行
        drools_rules = [r for r in rules if r.get("type") == "drools"]
        for rule in drools_rules:
            execution_result = drools_engine.execute_rule(rule["_id"], event)
            if execution_result["success"] and execution_result["result"]["matched"]:
                # 处理Drools规则结果
                for alert in execution_result["result"]["alerts"]:
                    classification = alert_classifier.classify_alert({
                        "source": event.get("source", "event"),
                        "metric": "drools_rule",
                        "value": 1,
                        "rule_id": rule["_id"]
                    })
                    
                    if classification["success"]:
                        alert_data = classification["classification"]
                        insert_alert({
                            "level": alert_data["level"],
                            "message": f"Drools规则触发: {alert['message']}",
                            "solution": alert["solution"],
                            "source": f"drools_{event.get('source', 'event')}",
                            "created_at": time.time(),
                            "extra": {
                                "event": event,
                                "rule": rule,
                                "drools_result": execution_result["result"],
                                "classification": alert_data
                            },
                        })
                        classified_alerts.append(alert_data)
                        triggered.append(f"Drools: {rule.get('name', 'rule')}")
    except Exception as e:
        logger.error(f"Drools规则执行失败: {e}")
    
    return {
        "triggered": triggered,
        "classified_alerts": classified_alerts,
        "total_alerts": len(classified_alerts)
    }


# Drools规则引擎相关接口
@router.post("/drools/rules")
async def create_drools_rule(rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建Drools规则"""
    try:
        result = drools_engine.create_rule(
            rule_data["id"],
            rule_data["content"],
            rule_data.get("type", "drl")
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/drools/rules/{rule_id}/execute")
async def execute_drools_rule(rule_id: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """执行Drools规则"""
    try:
        result = drools_engine.execute_rule(rule_id, facts)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/drools/rules/statistics")
async def get_drools_statistics(rule_id: str = None) -> Dict[str, Any]:
    """获取Drools规则统计"""
    try:
        result = drools_engine.get_rule_statistics(rule_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/drools/rules/{rule_id}/optimize")
async def optimize_drools_rule(rule_id: str) -> Dict[str, Any]:
    """优化Drools规则"""
    try:
        result = drools_engine.optimize_rules(rule_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# AI规则学习相关接口
@router.get("/ai/rules/{rule_id}/performance")
async def analyze_rule_performance(rule_id: str, days: int = 30) -> Dict[str, Any]:
    """分析规则性能"""
    try:
        result = ai_rule_learner.analyze_rule_performance(rule_id, days)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ai/rules/{rule_id}/learn")
async def learn_from_feedback(rule_id: str, feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从反馈中学习规则优化"""
    try:
        result = ai_rule_learner.learn_from_feedback(rule_id, feedback_data)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ai/rules/{rule_id}/auto-optimize")
async def auto_optimize_rule(rule_id: str) -> Dict[str, Any]:
    """自动优化规则"""
    try:
        result = ai_rule_learner.auto_optimize_rule(rule_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/ai/insights")
async def get_learning_insights(rule_id: str = None) -> Dict[str, Any]:
    """获取AI学习洞察"""
    try:
        result = ai_rule_learner.get_learning_insights(rule_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# 分级告警系统相关接口
@router.post("/alerts/classify")
async def classify_alert(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """分类告警"""
    try:
        result = alert_classifier.classify_alert(alert_data)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/alerts/statistics")
async def get_alert_statistics(days: int = 7) -> Dict[str, Any]:
    """获取告警统计"""
    try:
        result = alert_classifier.get_alert_statistics(days)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/alerts/levels")
async def get_alert_levels() -> Dict[str, Any]:
    """获取告警级别定义"""
    from ...utils.rules.alert_classifier import AlertLevel, AlertCategory
    
    return {
        "levels": [{"value": level.value, "name": level.name} for level in AlertLevel],
        "categories": [{"value": cat.value, "name": cat.name} for cat in AlertCategory]
    }


@router.get("/alerts/escalation-policies")
async def get_escalation_policies() -> Dict[str, Any]:
    """获取升级策略"""
    try:
        return {
            "success": True,
            "policies": alert_classifier.escalation_policies,
            "notification_channels": alert_classifier.notification_channels
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# 规则分析相关接口
@router.get("/analytics/rules/{rule_id}/performance")
async def get_rule_performance_analytics(rule_id: str, days: int = 30) -> Dict[str, Any]:
    """获取规则性能分析"""
    try:
        result = rule_analytics.get_rule_performance_summary(rule_id, days)
        return {"success": True, "analytics": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/rules/comparison")
async def compare_rules(rule_ids: str, days: int = 30) -> Dict[str, Any]:
    """比较多个规则性能"""
    try:
        rule_id_list = [rid.strip() for rid in rule_ids.split(',')]
        result = rule_analytics.get_rule_comparison(rule_id_list, days)
        return {"success": True, "comparison": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/rules/{rule_id}/recommendations")
async def get_rule_recommendations(rule_id: str, days: int = 30) -> Dict[str, Any]:
    """获取规则优化建议"""
    try:
        result = rule_analytics.generate_optimization_recommendations(rule_id, days)
        return {"success": True, "recommendations": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/system")
async def get_system_analytics(days: int = 30) -> Dict[str, Any]:
    """获取系统级分析"""
    try:
        result = rule_analytics.get_system_analytics(days)
        return {"success": True, "analytics": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/export")
async def export_analytics_data(rule_id: str = None, days: int = 30) -> Dict[str, Any]:
    """导出分析数据"""
    try:
        result = rule_analytics.export_analytics_data(rule_id, days)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analytics/rules/{rule_id}/record-execution")
async def record_rule_execution(rule_id: str, execution_data: Dict[str, Any]) -> Dict[str, Any]:
    """记录规则执行数据"""
    try:
        rule_analytics.record_execution(rule_id, execution_data)
        return {"success": True, "message": "执行数据记录成功"}
    except Exception as e:
        return {"success": False, "error": str(e)}


