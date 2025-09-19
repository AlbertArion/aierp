import os
import time
from app.db.mongo import get_db

# 说明：简单种子数据脚本，插入订单与流程报警示例


def main() -> None:
    db = get_db()
    # 订单示例
    if db.orders.count_documents({}) == 0:
        db.orders.insert_many([
            {"id": "A1001", "customer": "华南-深圳A公司", "amount": 120000, "status": "pending"},
            {"id": "A1002", "customer": "华东-上海B公司", "amount": 98000, "status": "pending"},
        ])
        print("Inserted orders seed")

    # 告警示例
    if db.process_alerts.count_documents({}) == 0:
        now = time.time()
        db.process_alerts.insert_many([
            {"level": "warning", "message": "库存对账延迟", "solution": "自动重试同步", "created_at": now},
            {"level": "error", "message": "供应商数据缺失", "solution": "触发补数流程", "created_at": now},
        ])
        print("Inserted alerts seed")


if __name__ == "__main__":
    main()


