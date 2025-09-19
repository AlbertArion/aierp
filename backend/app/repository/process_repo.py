from typing import Any, Dict, List
from ..db.mongo import get_db
import logging

logger = logging.getLogger(__name__)

# 说明：流程监管规则与告警数据访问


def list_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        db = get_db()
        items = list(db.process_alerts.find({}).sort("created_at", -1).limit(limit))
        for it in items:
            it["_id"] = str(it["_id"])  # 转字符串
        return items
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        # 返回示例数据
        return [
            {
                "_id": "demo_alert_1",
                "rule_id": "demo_rule_1",
                "message": "库存延迟告警：延迟45分钟",
                "level": "warning",
                "solution": "自动重试同步",
                "created_at": "2025-01-27T10:30:00Z"
            }
        ]


def insert_alert(alert: Dict[str, Any]) -> str:
    try:
        db = get_db()
        res = db.process_alerts.insert_one(alert)
        return str(res.inserted_id)
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return "demo_alert_" + str(hash(str(alert)))


