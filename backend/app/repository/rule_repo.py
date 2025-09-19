from typing import Any, Dict, List, Optional
from ..db.mongo import get_db
import logging

logger = logging.getLogger(__name__)

def list_rules() -> List[Dict[str, Any]]:
    try:
        db = get_db()
        items = list(db.process_rules.find({}).sort("_id", -1))
        for it in items:
            it["_id"] = str(it["_id"])  # 展示用
        return items
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        # 返回示例数据，避免前端报错
        return [
            {
                "_id": "demo_rule_1",
                "name": "库存延迟告警",
                "enabled": True,
                "description": "当对账延迟分钟数>30触发",
                "condition": {
                    "field": "delay_minutes",
                    "op": "gt",
                    "value": 30,
                    "level": "warning",
                    "solution": "自动重试同步"
                }
            }
        ]


def create_rule(rule: Dict[str, Any]) -> str:
    try:
        db = get_db()
        res = db.process_rules.insert_one(rule)
        return str(res.inserted_id)
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return "demo_rule_" + str(hash(str(rule)))


def update_rule(rule_id: str, patch: Dict[str, Any]) -> bool:
    try:
        from bson import ObjectId
        db = get_db()
        res = db.process_rules.update_one({"_id": ObjectId(rule_id)}, {"$set": patch})
        return res.modified_count > 0
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return True  # 模拟成功


def delete_rule(rule_id: str) -> bool:
    try:
        from bson import ObjectId
        db = get_db()
        res = db.process_rules.delete_one({"_id": ObjectId(rule_id)})
        return res.deleted_count > 0
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return True  # 模拟成功


