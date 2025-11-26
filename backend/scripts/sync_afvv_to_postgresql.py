#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将Excel中的AFVV数据同步到PostgreSQL数据库
"""

import psycopg2
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from app.utils.parsers.sap_excel_parser import SAPExcelParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库连接配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'sinocst_erp'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}


def check_and_add_lmnag_column(conn):
    """检查并添加lmnag字段到AFVV表"""
    try:
        cursor = conn.cursor()
        
        # 检查lmnag字段是否存在
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'pp_afvv' 
            AND column_name IN ('lmnag', 'lmnga', 'rmnag');
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # 添加lmnag字段（如果不存在）
        if 'lmnag' not in existing_columns and 'lmnga' not in existing_columns:
            logger.info("正在添加lmnag字段到pp_afvv表...")
            cursor.execute("""
                ALTER TABLE pp_afvv 
                ADD COLUMN IF NOT EXISTS lmnag NUMERIC(13,3) DEFAULT 0;
            """)
            conn.commit()
            logger.info("✅ lmnag字段添加成功")
        else:
            logger.info("✅ lmnag字段已存在")
        
        # 同样检查xmnag和gmnag字段
        if 'xmnag' not in existing_columns:
            logger.info("正在添加xmnag字段到pp_afvv表...")
            cursor.execute("""
                ALTER TABLE pp_afvv 
                ADD COLUMN IF NOT EXISTS xmnag NUMERIC(13,3) DEFAULT 0;
            """)
            conn.commit()
            logger.info("✅ xmnag字段添加成功")
        
        if 'gmnag' not in existing_columns:
            logger.info("正在添加gmnag字段到pp_afvv表...")
            cursor.execute("""
                ALTER TABLE pp_afvv 
                ADD COLUMN IF NOT EXISTS gmnag NUMERIC(13,3) DEFAULT 0;
            """)
            conn.commit()
            logger.info("✅ gmnag字段添加成功")
        
        cursor.close()
        
    except Exception as e:
        logger.error(f"检查/添加字段失败: {e}")
        conn.rollback()
        raise


def sync_afvv_data(excel_file_path: str, clear_existing: bool = False):
    """同步AFVV数据到PostgreSQL数据库"""
    try:
        # 连接数据库
        logger.info("正在连接PostgreSQL数据库...")
        conn = psycopg2.connect(**DB_CONFIG)
        
        # 检查并添加lmnag字段
        check_and_add_lmnag_column(conn)
        
        # 解析Excel文件
        logger.info(f"正在解析Excel文件: {excel_file_path}")
        parser = SAPExcelParser(excel_file_path)
        sheets_data = parser.parse_all_sheets()
        
        if 'AFVV' not in sheets_data:
            logger.error("Excel文件中没有找到AFVV工作表")
            return
        
        afvv_records = sheets_data['AFVV']
        logger.info(f"解析到 {len(afvv_records)} 条AFVV记录")
        
        if not afvv_records:
            logger.warning("没有AFVV数据需要同步")
            return
        
        cursor = conn.cursor()
        
        # 如果需要，清空现有数据
        if clear_existing:
            logger.info("正在清空现有AFVV数据...")
            cursor.execute("DELETE FROM pp_afvv")
            conn.commit()
            logger.info("✅ 现有数据已清空")
        
        # 准备批量插入
        insert_count = 0
        update_count = 0
        error_count = 0
        
        for record in afvv_records:
            try:
                # 准备数据（确保NOT NULL字段有默认值）
                data = {
                    'mandt': record.get('mandt', '000'),
                    'aufpl': str(record.get('aufpl', '')),
                    'aplzl': str(record.get('aplzl', '')),
                    'meinh': record.get('meinh') or '',
                    'umren': record.get('umren') or '',
                    'umrez': record.get('umrez') or '',
                    'bmsch': record.get('bmsch') or '',
                    'zmerh': record.get('zmerh') or '',
                    'zeier': record.get('zeier') or '',  # NOT NULL字段，使用空字符串而不是None
                    'mgvrg': record.get('mgvrg') or 0,
                    'asvrg': record.get('asvrg') or 0,
                    'lmnag': record.get('lmnag') or 0,
                    'xmnag': record.get('xmnag') or 0,
                    'gmnag': record.get('gmnag') or 0,
                }
                
                # 检查是否已存在（用于统计）
                cursor.execute("""
                    SELECT 1 FROM pp_afvv 
                    WHERE aufpl = %s AND aplzl = %s AND mandt = %s
                """, (data['aufpl'], data['aplzl'], data['mandt']))
                
                existing = cursor.fetchone()
                
                if existing:
                    # 更新现有记录
                    sql = """
                        UPDATE pp_afvv SET
                            meinh = %(meinh)s,
                            umren = %(umren)s,
                            umrez = %(umrez)s,
                            bmsch = %(bmsch)s,
                            zmerh = %(zmerh)s,
                            zeier = %(zeier)s,
                            mgvrg = CAST(%(mgvrg)s AS NUMERIC),
                            asvrg = CAST(%(asvrg)s AS NUMERIC),
                            lmnag = CAST(%(lmnag)s AS NUMERIC),
                            xmnag = CAST(%(xmnag)s AS NUMERIC),
                            gmnag = CAST(%(gmnag)s AS NUMERIC)
                        WHERE aufpl = %(aufpl)s AND aplzl = %(aplzl)s AND mandt = %(mandt)s
                    """
                    cursor.execute(sql, data)
                    update_count += 1
                else:
                    # 插入新记录
                    sql = """
                        INSERT INTO pp_afvv (
                            mandt, aufpl, aplzl, meinh, umren, umrez, bmsch, zmerh, zeier,
                            mgvrg, asvrg, lmnag, xmnag, gmnag
                        ) VALUES (
                            %(mandt)s, %(aufpl)s, %(aplzl)s, %(meinh)s, %(umren)s, %(umrez)s,
                            %(bmsch)s, %(zmerh)s, %(zeier)s,
                            CAST(%(mgvrg)s AS NUMERIC), CAST(%(asvrg)s AS NUMERIC),
                            CAST(%(lmnag)s AS NUMERIC), CAST(%(xmnag)s AS NUMERIC), CAST(%(gmnag)s AS NUMERIC)
                        )
                    """
                    cursor.execute(sql, data)
                    insert_count += 1
                
                # 每100条提交一次
                if (insert_count + update_count) % 100 == 0:
                    conn.commit()
                    logger.info(f"已处理 {insert_count + update_count} 条记录...")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"处理记录失败: {record.get('aufpl')}-{record.get('aplzl')}, 错误: {e}")
                # 回滚当前事务，然后继续处理下一条记录
                conn.rollback()
                continue
        
        # 最终提交
        conn.commit()
        logger.info(f"✅ 数据同步完成！新增: {insert_count} 条, 更新: {update_count} 条, 错误: {error_count} 条")
        
        cursor.close()
        conn.close()
        
        return {
            'inserted': insert_count,
            'updated': update_count,
            'errors': error_count,
            'total': insert_count + update_count
        }
        
    except Exception as e:
        logger.error(f"同步数据失败: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python sync_afvv_to_postgresql.py <excel_file_path> [--clear]")
        print("示例: python sync_afvv_to_postgresql.py /path/to/data.xlsx --clear")
        sys.exit(1)
    
    excel_file_path = sys.argv[1]
    clear_existing = '--clear' in sys.argv
    
    if not os.path.exists(excel_file_path):
        print(f"错误: Excel文件不存在: {excel_file_path}")
        sys.exit(1)
    
    try:
        result = sync_afvv_data(excel_file_path, clear_existing=clear_existing)
        print(f"\n同步结果:")
        print(f"  新增: {result['inserted']} 条")
        print(f"  更新: {result['updated']} 条")
        print(f"  总计: {result['total']} 条")
    except Exception as e:
        print(f"同步失败: {e}")
        sys.exit(1)

