#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从Excel文件导入MAKT（物料描述）数据到PostgreSQL的md_makt表
"""

import sys
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, execute_batch
from psycopg2 import sql
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PostgreSQL数据库连接配置
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'sinocst_erp'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

# Java项目API配置
JAVA_API_BASE_URL = os.getenv('JAVA_API_BASE_URL', 'http://localhost:9015')
JAVA_API_TOKEN = os.getenv('JAVA_API_TOKEN', None)

# Excel文件路径（相对于项目根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EXCEL_FILE_PATH = os.path.join(BASE_DIR, 'docs/需求文档/Agent/PP_Agent/PP Agent 所需数据.xlsx')


def get_postgres_connection():
    """获取PostgreSQL数据库连接"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        logger.info(f"成功连接到PostgreSQL数据库: {POSTGRES_CONFIG['database']}")
        return conn
    except Exception as e:
        logger.error(f"连接PostgreSQL数据库失败: {e}")
        return None


def read_excel_makt_data(excel_file_path: str) -> List[Dict[str, Any]]:
    """从Excel文件读取MAKT表数据"""
    try:
        if not os.path.exists(excel_file_path):
            logger.error(f"Excel文件不存在: {excel_file_path}")
            return []
        
        logger.info(f"正在读取Excel文件: {excel_file_path}")
        df = pd.read_excel(excel_file_path, sheet_name='MAKT')
        logger.info(f"Excel文件中MAKT表共有 {len(df)} 条记录")
        
        # 转换为字典列表
        records = []
        for index, row in df.iterrows():
            # Excel中的mandt可能是500，需要统一转换为600（Java项目使用的mandt）
            record = {
                'mandt': '600',  # 统一使用600作为mandt（Java项目的默认mandt）
                'matnr': str(row['MATNR']).strip() if pd.notna(row['MATNR']) else '',
                'spras': str(row['SPRAS']).strip() if pd.notna(row['SPRAS']) else '1',
                'maktx': str(row['MAKTX']).strip() if pd.notna(row['MAKTX']) else '',
                'maktg': str(row['MAKTG']).strip() if pd.notna(row['MAKTG']) else ''
            }
            # 只添加有效的记录（必须有物料号）
            if record['matnr']:
                records.append(record)
        
        logger.info(f"成功读取 {len(records)} 条有效记录（mandt已统一为600）")
        return records
        
    except Exception as e:
        logger.error(f"读取Excel文件失败: {e}")
        return []


def check_existing_data(conn, mandt: str = '600') -> Dict[str, bool]:
    """检查数据库中已存在的数据"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT matnr, spras 
            FROM md_makt 
            WHERE mandt = %s
        """, (mandt,))
        
        existing = {}
        for row in cursor.fetchall():
            key = f"{row[0]}_{row[1]}"
            existing[key] = True
        
        cursor.close()
        logger.info(f"数据库中已有 {len(existing)} 条记录（mandt={mandt}）")
        return existing
        
    except Exception as e:
        logger.error(f"检查现有数据失败: {e}")
        return {}


def import_makt_via_api(records: List[Dict[str, Any]], batch_size: int = 50) -> bool:
    """通过Java项目API导入数据（使用submit接口逐个导入）"""
    try:
        if not JAVA_API_TOKEN:
            logger.warning("未设置JAVA_API_TOKEN，无法使用API方式导入")
            return False
        
        headers = {
            'Content-Type': 'application/json',
            'Blade-Requested-With': 'BladeHttpRequest',
            'Blade-Auth': f'bearer {JAVA_API_TOKEN}'
        }
        
        api_url = f"{JAVA_API_BASE_URL}/sinocst-master-data/sinocst-makt/makt/submit"
        
        total = len(records)
        success_count = 0
        error_count = 0
        
        # 逐个导入（因为可能没有批量接口）
        for i, record in enumerate(records):
            try:
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=record,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == 200 or result.get('success'):
                        success_count += 1
                        if (i + 1) % 50 == 0:
                            logger.info(f"API导入进度: {i + 1}/{total}")
                    else:
                        error_count += 1
                        logger.warning(f"API导入失败 (matnr={record.get('matnr')}): {result.get('msg', '未知错误')}")
                else:
                    error_count += 1
                    logger.warning(f"API请求失败 (matnr={record.get('matnr')}): {response.status_code}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"API导入失败 (matnr={record.get('matnr')}): {e}")
        
        logger.info(f"API导入完成: 成功 {success_count} 条，失败 {error_count} 条")
        return error_count == 0
        
    except Exception as e:
        logger.error(f"API导入失败: {e}")
        return False


def get_table_primary_key(conn, table_name: str) -> List[str]:
    """获取表的主键列"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass
            AND i.indisprimary
            ORDER BY a.attnum
        """, (table_name,))
        pk_columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return pk_columns
    except Exception as e:
        logger.warning(f"获取主键失败: {e}，将使用默认主键")
        return ['matnr']


def import_makt_directly_to_postgresql(conn, records: List[Dict[str, Any]], mandt: str = '600') -> int:
    """直接插入到PostgreSQL数据库"""
    try:
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'md_makt'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.error("表 md_makt 不存在，请先创建表")
            cursor.close()
            return 0
        
        # 获取主键信息
        pk_columns = get_table_primary_key(conn, 'md_makt')
        logger.info(f"表 md_makt 的主键列: {pk_columns}")
        
        # 统一mandt
        for record in records:
            record['mandt'] = mandt
        
        total_inserted = 0
        total_updated = 0
        
        # 准备UPSERT SQL
        # 根据主键决定冲突处理方式
        if len(pk_columns) == 1 and pk_columns[0] == 'matnr':
            # 单主键，使用matnr
            conflict_target = '(matnr)'
            update_clause = 'maktx = EXCLUDED.maktx, maktg = EXCLUDED.maktg, mandt = EXCLUDED.mandt, spras = EXCLUDED.spras'
        else:
            # 复合主键，使用(mandt, matnr, spras)
            conflict_target = '(mandt, matnr, spras)'
            update_clause = 'maktx = EXCLUDED.maktx, maktg = EXCLUDED.maktg'
        
        # 准备数据
        values = [
            (
                r['mandt'],
                r['matnr'],
                r['spras'],
                r['maktx'] or '',
                r['maktg'] or ''
            )
            for r in records
        ]
        
        # 使用逐个插入/更新的方式，更可靠
        for record in records:
            try:
                # 先检查记录是否存在（根据mandt, matnr, spras）
                cursor.execute("""
                    SELECT COUNT(*) FROM md_makt 
                    WHERE mandt = %s AND matnr = %s AND spras = %s
                """, (record['mandt'], record['matnr'], record['spras']))
                
                exists = cursor.fetchone()[0] > 0
                
                if exists:
                    # 更新现有记录
                    cursor.execute("""
                        UPDATE md_makt 
                        SET maktx = %s, maktg = %s
                        WHERE mandt = %s AND matnr = %s AND spras = %s
                    """, (
                        record['maktx'] or '',
                        record['maktg'] or '',
                        record['mandt'],
                        record['matnr'],
                        record['spras']
                    ))
                    total_updated += 1
                else:
                    # 插入新记录
                    cursor.execute("""
                        INSERT INTO md_makt (mandt, matnr, spras, maktx, maktg)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        record['mandt'],
                        record['matnr'],
                        record['spras'],
                        record['maktx'] or '',
                        record['maktg'] or ''
                    ))
                    total_inserted += 1
                    
            except Exception as e2:
                logger.error(f"处理记录失败 (matnr={record.get('matnr')}): {e2}")
        
        logger.info(f"成功插入 {total_inserted} 条，更新 {total_updated} 条")
        
        conn.commit()
        cursor.close()
        
        logger.info(f"✅ 导入完成: 处理 {total_inserted} 条记录")
        return total_inserted
        
    except Exception as e:
        logger.error(f"直接导入PostgreSQL失败: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return 0


def main():
    """主函数"""
    logger.info("🚀 开始导入MAKT（物料描述）数据...")
    
    # 读取Excel数据
    records = read_excel_makt_data(EXCEL_FILE_PATH)
    if not records:
        logger.error("❌ 没有读取到任何数据，退出")
        return
    
    # 连接PostgreSQL
    conn = get_postgres_connection()
    if not conn:
        logger.error("❌ 无法连接到PostgreSQL数据库，退出")
        return
    
    try:
        # 优先尝试API方式
        if JAVA_API_TOKEN:
            logger.info("尝试使用API方式导入...")
            if import_makt_via_api(records):
                logger.info("✅ API导入成功")
                return
        
        # 如果API方式失败或未配置，使用直接数据库插入
        logger.info("使用直接数据库插入方式...")
        count = import_makt_directly_to_postgresql(conn, records)
        
        if count > 0:
            logger.info(f"🎉 成功导入 {count} 条MAKT记录到PostgreSQL")
        else:
            logger.warning("⚠️ 没有导入任何数据")
            
    finally:
        conn.close()
        logger.info("数据库连接已关闭")


if __name__ == '__main__':
    main()

