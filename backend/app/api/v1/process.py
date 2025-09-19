from fastapi import APIRouter
from typing import Any, Dict, List
from ...repository.process_repo import list_alerts, insert_alert
from ...repository.rule_repo import list_rules, create_rule, update_rule, delete_rule
from ...schemas.rule import ProcessRule
from ...schemas.process import ProcessAlert
import time

# 说明：流程监管模块接口，占位实现

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
    # 最小事件触发：遍历启用规则，匹配则写告警
    rules = list_rules()
    triggered: list[str] = []
    for r in rules:
        if not r.get("enabled", True):
            continue
        cond = r.get("condition", {})
        if _match_condition(event, cond):
            insert_alert({
                "level": cond.get("level", "warning"),
                "message": r.get("name", "rule triggered"),
                "solution": cond.get("solution"),
                "source": event.get("source", "event"),
                "created_at": time.time(),
                "extra": {"event": event, "rule": r},
            })
            triggered.append(r.get("name", "rule"))
    return {"triggered": triggered}


