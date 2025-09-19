import os
from typing import Any, List, Tuple, Optional
import snowflake.connector

# 说明：Snowflake最小客户端，提供查询与批量写入示例


def get_connection():
    ctx = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )
    return ctx


def execute_query(sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[tuple]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            try:
                rows = cur.fetchall()
            except Exception:
                rows = []
    return rows


def execute_many(sql: str, rows: List[Tuple[Any, ...]]) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
            return cur.rowcount or 0


