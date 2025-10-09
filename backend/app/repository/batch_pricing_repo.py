#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量核价 Repository
负责批量任务与结果的持久化访问
"""

from typing import Dict, List, Optional, Tuple
import json
import sqlite3
from datetime import datetime

from app.db.sqlite_db import get_sqlite_db


class BatchPricingRepository:
    def __init__(self) -> None:
        self.db = get_sqlite_db().conn

    def create_task(self, trace_id: str, task_name: Optional[str], source_file_name: str, total_rows: int, normalized_columns: List[str], source_file_path: Optional[str]) -> None:
        cur = self.db.cursor()
        cur.execute(
            """
            INSERT INTO pricing_batch_tasks(trace_id, task_name, source_file_name, total_rows, normalized_columns, status, source_file_path)
            VALUES(?, ?, ?, ?, ?, 'uploaded', ?)
            """,
            (trace_id, task_name, source_file_name, total_rows, json.dumps(normalized_columns, ensure_ascii=False), source_file_path)
        )
        self.db.commit()

    def update_task_status(self, trace_id: str, status: str, stats: Optional[Dict] = None) -> None:
        cur = self.db.cursor()
        cur.execute(
            """
            UPDATE pricing_batch_tasks SET status = ?, stats_json = ?, updated_at = CURRENT_TIMESTAMP WHERE trace_id = ?
            """,
            (status, json.dumps(stats, ensure_ascii=False) if stats else None, trace_id)
        )
        self.db.commit()

    def approve_task(self, trace_id: str, approver: str, approve: bool) -> None:
        cur = self.db.cursor()
        cur.execute(
            """
            UPDATE pricing_batch_tasks SET status = ?, approved_at = CURRENT_TIMESTAMP, approver = ? WHERE trace_id = ?
            """,
            ('approved' if approve else 'rejected', approver, trace_id)
        )
        self.db.commit()

    def get_task(self, trace_id: str) -> Optional[Dict]:
        cur = self.db.cursor()
        cur.execute("SELECT * FROM pricing_batch_tasks WHERE trace_id = ?", (trace_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def insert_results(self, trace_id: str, rows: List[Dict]) -> None:
        if not rows:
            return
        cur = self.db.cursor()
        sql = (
            """
            INSERT INTO pricing_batch_results(
                trace_id, row_index, material_code, material_name, specification, process_requirements,
                quantity, uom, estimated_price, currency, status, reason_or_notes, rule_version, extra_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        values = [
            (
                trace_id,
                r.get('row_index'),
                r.get('material_code'),
                r.get('material_name'),
                r.get('specification'),
                r.get('process_requirements'),
                r.get('quantity'),
                r.get('uom'),
                r.get('estimated_price'),
                r.get('currency'),
                r.get('status'),
                r.get('reason_or_notes'),
                r.get('rule_version'),
                json.dumps(r.get('extra_json'), ensure_ascii=False) if isinstance(r.get('extra_json'), (dict, list)) else r.get('extra_json')
            ) for r in rows
        ]
        cur.executemany(sql, values)
        self.db.commit()

    def list_results(self, trace_id: str, status: Optional[str], page: int, size: int) -> Dict:
        cur = self.db.cursor()
        params = [trace_id]
        where = "trace_id = ?"
        if status and status != 'all':
            where += " AND status = ?"
            params.append(status)
        cur.execute(f"SELECT COUNT(*) FROM pricing_batch_results WHERE {where}", params)
        total = cur.fetchone()[0]
        offset = (page - 1) * size
        cur.execute(
            f"SELECT * FROM pricing_batch_results WHERE {where} ORDER BY id LIMIT ? OFFSET ?",
            params + [size, offset]
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {"total": total, "rows": rows}


