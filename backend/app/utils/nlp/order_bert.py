from typing import Dict, Any

# 说明：BERT关键信息抽取占位。实际应加载微调模型提取订单号/字段/操作。


def extract_order_command(text: str) -> Dict[str, Any]:
    # 简单规则引擎占位：提取订单号与字段
    order_id = "12345" if "12345" in text else "unknown"
    field = "status" if "状态" in text else "unknown"
    value = "已发货" if "已发货" in text else "unknown"
    action = "update" if "修改" in text else "search"
    return {"order_id": order_id, "field": field, "value": value, "action": action}


