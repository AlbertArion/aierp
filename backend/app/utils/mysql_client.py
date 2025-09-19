import os
from typing import Any, Iterable, Tuple, Optional
import pymysql

# 说明：MySQL最小客户端，用于写入订单变更日志


def get_conn():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "aierp"),
        charset="utf8mb4",
        autocommit=True,
    )


def execute(sql: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount


def executemany(sql: str, rows: Iterable[Tuple[Any, ...]]) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, list(rows))
            return cur.rowcount


