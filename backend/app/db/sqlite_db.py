#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SQLite数据库管理器
提供本地数据库支持，替代MongoDB
"""

import sqlite3
import json
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, date
import os

logger = logging.getLogger(__name__)

class SQLiteDatabase:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str = "aierp.db"):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库和表结构"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            
            # 创建表结构
            self._create_tables()
            logger.info(f"SQLite数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            logger.error(f"SQLite数据库初始化失败: {e}")
            raise
    
    def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()
        
        # 员工表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                employee_no TEXT UNIQUE,
                name TEXT NOT NULL,
                pinyin TEXT,
                phone TEXT,
                email TEXT,
                position TEXT,
                department_id TEXT,
                status TEXT,
                hire_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 项目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                project_code TEXT UNIQUE,
                project_name TEXT NOT NULL,
                project_type TEXT,
                status TEXT,
                manager_id TEXT,
                start_date DATE,
                end_date DATE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 部门表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                department_code TEXT UNIQUE,
                department_name TEXT NOT NULL,
                parent_id TEXT,
                manager_id TEXT,
                status TEXT,
                level INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 报工记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_reports (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                report_date DATE NOT NULL,
                work_hours REAL NOT NULL,
                work_content TEXT,
                work_location TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees (id),
                FOREIGN KEY (project_id) REFERENCES projects (id),
                FOREIGN KEY (department_id) REFERENCES departments (id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_employee ON work_reports(employee_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_project ON work_reports(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_date ON work_reports(report_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_status ON work_reports(status)')
        
        self.conn.commit()

        # 兼容旧库：若缺列则动态补齐
        self._ensure_column_exists('employees', 'status', 'TEXT')
        self._ensure_column_exists('projects', 'status', 'TEXT')
        self._ensure_column_exists('departments', 'status', 'TEXT')

    def _ensure_column_exists(self, table: str, column: str, col_type: str) -> None:
        """确保表存在指定列，不存在则添加"""
        try:
            cur = self.conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            cols = [row[1] for row in cur.fetchall()]
            if column not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                self.conn.commit()
        except Exception as e:
            logger.warning(f"检查/添加列失败 {table}.{column}: {e}")
    
    def get_collection(self, collection_name: str):
        """获取集合对象（模拟MongoDB接口）"""
        return SQLiteCollection(self.conn, collection_name)
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

class SQLiteCollection:
    """SQLite集合模拟器（模拟MongoDB Collection接口）"""
    
    def __init__(self, conn, table_name: str):
        self.conn = conn
        self.table_name = table_name
        self.cursor = conn.cursor()
    
    def find_one(self, filter_dict: Dict = None):
        """查找单条记录"""
        if not filter_dict:
            sql = f"SELECT * FROM {self.table_name} LIMIT 1"
            params = []
        else:
            where_clause, params = self._build_where_clause(filter_dict)
            sql = f"SELECT * FROM {self.table_name} WHERE {where_clause} LIMIT 1"
        
        self.cursor.execute(sql, params)
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def find(self, filter_dict: Dict = None):
        """查找多条记录"""
        if not filter_dict:
            sql = f"SELECT * FROM {self.table_name}"
            params = []
        else:
            where_clause, params = self._build_where_clause(filter_dict)
            sql = f"SELECT * FROM {self.table_name} WHERE {where_clause}"
        
        self.cursor.execute(sql, params)
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def insert_one(self, document: Dict):
        """插入单条记录"""
        # 处理日期类型
        processed_doc = self._process_document(document)
        
        columns = list(processed_doc.keys())
        placeholders = ['?' for _ in columns]
        values = list(processed_doc.values())
        
        sql = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        self.cursor.execute(sql, values)
        self.conn.commit()
        
        # 返回插入结果对象
        return type('Result', (), {'inserted_id': processed_doc.get('id', 'unknown')})()
    
    def insert_many(self, documents: List[Dict]):
        """插入多条记录"""
        if not documents:
            return type('Result', (), {'inserted_ids': []})()
        
        # 处理日期类型
        processed_docs = [self._process_document(doc) for doc in documents]
        
        columns = list(processed_docs[0].keys())
        placeholders = ['?' for _ in columns]
        
        sql = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        
        values_list = [list(doc.values()) for doc in processed_docs]
        self.cursor.executemany(sql, values_list)
        self.conn.commit()
        
        inserted_ids = [doc.get('id', 'unknown') for doc in processed_docs]
        return type('Result', (), {'inserted_ids': inserted_ids})()
    
    def update_one(self, filter_dict: Dict, update_dict: Dict):
        """更新单条记录"""
        where_clause, where_params = self._build_where_clause(filter_dict)
        
        set_clause = ', '.join([f"{key} = ?" for key in update_dict.keys()])
        params = list(update_dict.values()) + where_params
        
        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"
        self.cursor.execute(sql, params)
        self.conn.commit()
        
        return type('Result', (), {'modified_count': self.cursor.rowcount})()
    
    def delete_one(self, filter_dict: Dict):
        """删除单条记录"""
        where_clause, params = self._build_where_clause(filter_dict)
        sql = f"DELETE FROM {self.table_name} WHERE {where_clause}"
        self.cursor.execute(sql, params)
        self.conn.commit()
        
        return type('Result', (), {'deleted_count': self.cursor.rowcount})()
    
    def count_documents(self, filter_dict: Dict = None):
        """统计文档数量"""
        if not filter_dict:
            sql = f"SELECT COUNT(*) FROM {self.table_name}"
            params = []
        else:
            where_clause, params = self._build_where_clause(filter_dict)
            sql = f"SELECT COUNT(*) FROM {self.table_name} WHERE {where_clause}"
        
        self.cursor.execute(sql, params)
        return self.cursor.fetchone()[0]
    
    def aggregate(self, pipeline: List[Dict]):
        """聚合查询（简化实现）"""
        # 这里实现基本的聚合功能
        if not pipeline:
            return []
        
        # 简单实现 $group 聚合
        for stage in pipeline:
            if '$group' in stage:
                group = stage['$group']
                if group.get('_id') is None:  # 全局聚合
                    # 计算总数和总和
                    sql = f"SELECT COUNT(*) as total_reports, SUM(work_hours) as total_hours, AVG(work_hours) as avg_hours FROM {self.table_name}"
                    self.cursor.execute(sql)
                    result = self.cursor.fetchone()
                    
                    return [{
                        'total_reports': result[0] or 0,
                        'total_hours': result[1] or 0,
                        'avg_hours': result[2] or 0
                    }]
        
        return []
    
    def _build_where_clause(self, filter_dict: Dict):
        """构建WHERE子句"""
        if not filter_dict:
            return "1=1", []
        
        conditions = []
        params = []
        
        for key, value in filter_dict.items():
            if key == '$or':
                # 处理 $or 查询
                or_conditions = []
                for or_condition in value:
                    or_where, or_params = self._build_where_clause(or_condition)
                    or_conditions.append(f"({or_where})")
                    params.extend(or_params)
                conditions.append(f"({' OR '.join(or_conditions)})")
            elif isinstance(value, dict):
                # 处理复杂查询条件
                for op, op_value in value.items():
                    if op == '$regex':
                        conditions.append(f"{key} LIKE ?")
                        params.append(f"%{op_value}%")
                    elif op == '$gte':
                        conditions.append(f"{key} >= ?")
                        params.append(op_value)
                    elif op == '$lte':
                        conditions.append(f"{key} <= ?")
                        params.append(op_value)
                    elif op == '$options':
                        continue  # 忽略选项
                    else:
                        conditions.append(f"{key} = ?")
                        params.append(op_value)
            else:
                conditions.append(f"{key} = ?")
                params.append(value)
        
        return " AND ".join(conditions), params
    
    def _process_document(self, document: Dict):
        """处理文档数据，转换日期等特殊类型"""
        processed = document.copy()
        
        # 转换特殊类型
        for key, value in processed.items():
            if isinstance(value, (datetime, date)):
                processed[key] = value.isoformat()
            elif isinstance(value, list):
                # 将列表转换为JSON字符串
                processed[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, dict):
                # 将字典转换为JSON字符串
                processed[key] = json.dumps(value, ensure_ascii=False)
            elif hasattr(value, 'value') and hasattr(value, '__class__'):  # Enum类型
                processed[key] = value.value
        
        return processed

# 全局数据库实例
_sqlite_db_instance = None

def get_sqlite_db():
    """获取SQLite数据库实例"""
    global _sqlite_db_instance
    if _sqlite_db_instance is None:
        # 数据库文件现在位于app/db目录下
        db_path = os.path.join(os.path.dirname(__file__), "aierp.db")
        _sqlite_db_instance = SQLiteDatabase(db_path)
    return _sqlite_db_instance
