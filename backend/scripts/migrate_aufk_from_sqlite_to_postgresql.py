#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将SQLite数据库中的aufk表数据迁移到PostgreSQL的pp_aufk表
"""

import sys
import os
import sqlite3
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

# SQLite数据库路径
SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', 'aierp.db')


def get_sqlite_connection():
    """获取SQLite数据库连接"""
    try:
        if not os.path.exists(SQLITE_DB_PATH):
            logger.error(f"SQLite数据库文件不存在: {SQLITE_DB_PATH}")
            return None
        
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
        logger.info(f"成功连接到SQLite数据库: {SQLITE_DB_PATH}")
        return conn
    except Exception as e:
        logger.error(f"连接SQLite数据库失败: {e}")
        return None


def get_postgres_connection():
    """获取PostgreSQL数据库连接"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        logger.info(f"成功连接到PostgreSQL数据库: {POSTGRES_CONFIG['database']}")
        return conn
    except Exception as e:
        logger.error(f"连接PostgreSQL数据库失败: {e}")
        return None


def get_postgresql_columns(conn, table_name: str) -> List[str]:
    """获取PostgreSQL表中已存在的列名"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return columns


def read_sqlite_aufk_data(sqlite_conn, batch_size: int = 1000) -> List[Dict[str, Any]]:
    """从SQLite读取aufk表数据"""
    try:
        cursor = sqlite_conn.cursor()
        
        # 先获取总数
        cursor.execute("SELECT COUNT(*) FROM aufk")
        total_count = cursor.fetchone()[0]
        logger.info(f"SQLite aufk表中总共有 {total_count} 条记录")
        
        # 读取所有数据
        cursor.execute("SELECT * FROM aufk")
        rows = cursor.fetchall()
        
        # 转换为字典列表
        records = []
        for row in rows:
            record = dict(row)
            # 处理日期字段：SQLite中的DATE类型需要转换为字符串
            for key, value in record.items():
                if isinstance(value, datetime):
                    # 如果是日期时间，转换为YYYYMMDD格式
                    record[key] = value.strftime('%Y%m%d') if hasattr(value, 'strftime') else str(value)
                elif value is None:
                    record[key] = None
                else:
                    record[key] = value
            
            records.append(record)
        
        logger.info(f"成功读取 {len(records)} 条记录")
        return records
        
    except Exception as e:
        logger.error(f"读取SQLite数据失败: {e}")
        raise


def convert_to_postgresql_format(record: Dict[str, Any], pg_columns: List[str]) -> Dict[str, Any]:
    """
    将SQLite记录转换为PostgreSQL格式
    
    Args:
        record: SQLite记录（字典）
        pg_columns: PostgreSQL表的列名列表
        
    Returns:
        转换后的记录（只包含PostgreSQL表中存在的列）
    """
    converted = {}
    
    # SQLite列名映射到PostgreSQL列名（通常只是大小写不同）
    column_mapping = {
        'id': 'id',  # SQLite可能有id字段，PostgreSQL可能不需要
        'mandt': 'mandt',
        'aufnr': 'aufnr',
        'auart': 'auart',
        'autyp': 'autyp',
        'refnr': 'refnr',
        'ernam': 'ernam',
        'erdat': 'erdat',
        'aenam': 'aenam',
        'aedat': 'aedat',
        'ktext': 'ktext',
        'ltext': 'ltext',
        'bukrs': 'bukrs',
        'werks': 'werks',
        'gsber': 'gsber',
        'kokrs': 'kokrs',
        'cckey': 'cckey',
        'kostv': 'kostv',
        'stort': 'stort',
        'sowrk': 'sowrk',
        'astkz': 'astkz',
        'waers': 'waers',
        'astnr': 'astnr',
        'stdat': 'stdat',
        'estnr': 'estnr',
        'phas0': 'phas0',
        'phas1': 'phas1',
        'phas2': 'phas2',
        'phas3': 'phas3',
        'pdat1': 'pdat1',
        'pdat2': 'pdat2',
        'pdat3': 'pdat3',
        'idat1': 'idat1',
        'idat2': 'idat2',
        'idat3': 'idat3',
        'objid': 'objid',
        'vogrp': 'vogrp',
        'loekz': 'loekz',
        'plgkz': 'plgkz',
        'kvewe': 'kvewe',
        'kappl': 'kappl',
        'kalsm': 'kalsm',
        'zschl': 'zschl',
        'abkrs': 'abkrs',
        'kstar': 'kstar',
        'kostl': 'kostl',
        'saknr': 'saknr',
        'setnm': 'setnm',
        'cycle': 'cycle',
        'sdate': 'sdate',
        'seqnr': 'seqnr',
        'user0': 'user0',
        'user1': 'user1',
        'user2': 'user2',
        'user3': 'user3',
        'user4': 'user4',
        'user5': 'user5',
        'user6': 'user6',
        'user7': 'user7',
        'user8': 'user8',
        'user9': 'user9',
        'objnr': 'objnr',
        'prctr': 'prctr',
        'pspel': 'pspel',
        'awsls': 'awsls',
        'abgsl': 'abgsl',
        'txjcd': 'txjcd',
        'func_area': 'funcArea',
        'scope': 'scope',
        'plint': 'plint',
        'kdauf': 'kdauf',
        'kdpos': 'kdpos',
        'aufex': 'aufex',
        'ivpro': 'ivpro',
        'logsystem': 'logsystem',
        'flg_mltps': 'flgMltps',
        'abukr': 'abukr',
        'akstl': 'akstl',
        'sizecl': 'sizecl',
        'izwek': 'izwek',
        'umwkz': 'umwkz',
        'kstempf': 'kstempf',
        'zschm': 'zschm',
        'pkosa': 'pkosa',
        'anfaufnr': 'anfaufnr',
        'procnr': 'procnr',
        'proty': 'proty',
        'rsord': 'rsord',
        'bemot': 'bemot',
        'adrnra': 'adrnra',
        'erfzeit': 'erfzeit',
        'aezeit': 'aezeit',
        'cstg_vrnt': 'cstgVrnt',
        'costestnr': 'costestnr',
        'veraa_user': 'veraaUser',
        'zbukrs': 'zbukrs',
        'zzcpkg': 'zzcpkg',
        'zzkhyq': 'zzkhyq',
        'zztuhao': 'zztuhao',
        'zzjsfa': 'zzjsfa',
        'zzxqbm': 'zzxqbm',
        'zzyfxmh': 'zzyfxmh',
        'zzwxy': 'zzwxy',
        'zzjy': 'zzjy',
        'zzjyjg': 'zzjyjg',
        'zzgzfx': 'zzgzfx',
        'zzbf': 'zzbf',
        'zzsernr': 'zzsernr',
        'zzwtms': 'zzwtms',
        'zzgzdm': 'zzgzdm',
        'zggyq': 'zggyq',
        'zxpl': 'zxpl',
        'zgg': 'zgg',
        'zfg': 'zfg',
        'vname': 'vname',
        'recid': 'recid',
        'etype': 'etype',
        'otype': 'otype',
        'jv_jibcl': 'jvJibcl',
        'jv_jibsa': 'jvJibsa',
        'jv_oco': 'jvOco',
        'cum_indcu': 'cumIndcu',
        'cum_cmnum': 'cumCmnum',
        'cum_auest': 'cumAuest',
        'cum_desnum': 'cumDesnum',
        'vaplz': 'vaplz',
        'wawrk': 'wawrk',
        'ferc_ind': 'fercInd',
        'aufk_status': 'claimControl',  # 可能需要调整
        'claim_control': 'updateNeeded',  # 可能需要调整
        'update_needed': 'updateControl',  # 可能需要调整
        'update_control': 'updateControl',  # 可能需要调整
    }
    
    # 只保留PostgreSQL表中存在的列
    for sqlite_col, value in record.items():
        # 先尝试直接映射（小写列名）
        pg_col = column_mapping.get(sqlite_col.lower(), sqlite_col.lower())
        
        # 如果PostgreSQL表中存在该列，则添加
        if pg_col in pg_columns:
            # 处理日期格式：如果是日期字符串，转换为YYYYMMDD格式
            if pg_col in ['erdat', 'aedat', 'stdat', 'pdat1', 'pdat2', 'pdat3', 'idat1', 'idat2', 'idat3', 'sdate']:
                if value and isinstance(value, str):
                    # 尝试转换为YYYYMMDD格式
                    try:
                        # 如果是YYYY-MM-DD格式，转换为YYYYMMDD
                        if len(value) == 10 and '-' in value:
                            value = value.replace('-', '')
                        # 如果是日期时间对象
                        elif isinstance(value, datetime):
                            value = value.strftime('%Y%m%d')
                    except:
                        pass
                elif value is None:
                    value = None
            elif value is None:
                value = None
            
            converted[pg_col] = value
    
    return converted


def migrate_via_api(records: List[Dict[str, Any]]) -> int:
    """
    通过Java项目的API接口迁移数据
    
    Args:
        records: SQLite记录列表
        
    Returns:
        成功迁移的记录数
    """
    if not JAVA_API_BASE_URL:
        logger.error("未配置Java API地址，无法通过API迁移")
        return 0
    
    logger.info(f"开始通过API迁移数据到PostgreSQL，共 {len(records)} 条记录")
    
    # 准备请求头
    headers = {
        'Content-Type': 'application/json',
        'Blade-Requested-With': 'BladeHttpRequest'
    }
    
    if JAVA_API_TOKEN:
        headers['Blade-Auth'] = f'bearer {JAVA_API_TOKEN}'
    
    # 批量插入（每次100条）
    batch_size = 100
    total_success = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        
        try:
            # 调用Java项目的批量保存接口（通过Feign Client定义，但需要确认Controller是否实现）
            # 如果没有实现，可以使用submit接口（saveOrUpdate）循环调用
            url = f"{JAVA_API_BASE_URL}/sinocst-module-pp/sinocst-aufk/aufk/saveBatch"
            
            # 准备请求体（确保数据格式正确）
            payload = []
            for record in batch:
                # 确保mandt字段存在
                if 'mandt' not in record or not record.get('mandt'):
                    record['mandt'] = '000'  # 默认值
                # 确保aufnr字段存在
                if 'aufnr' not in record or not record.get('aufnr'):
                    logger.warning(f"跳过没有aufnr的记录: {record}")
                    continue
                payload.append(record)
            
            if not payload:
                logger.warning(f"批量中没有有效记录，跳过")
                continue
            
            logger.info(f"正在迁移第 {i+1}-{min(i+batch_size, len(records))} 条记录...")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 or result.get('success'):
                    total_success += len(batch)
                    logger.info(f"成功迁移 {len(batch)} 条记录（累计: {total_success}/{len(records)}）")
                else:
                    logger.error(f"API返回错误: {result.get('msg', '未知错误')}")
            else:
                logger.error(f"API请求失败: HTTP {response.status_code}, {response.text}")
                
        except Exception as e:
            logger.error(f"批量迁移失败（第 {i+1}-{min(i+batch_size, len(records))} 条）: {e}")
            continue
    
    logger.info(f"通过API迁移完成，成功迁移 {total_success}/{len(records)} 条记录")
    return total_success


def migrate_via_direct_insert(records: List[Dict[str, Any]], pg_conn) -> int:
    """
    直接插入PostgreSQL数据库（备用方案）
    
    Args:
        records: SQLite记录列表
        pg_conn: PostgreSQL数据库连接
        
    Returns:
        成功迁移的记录数
    """
    logger.info(f"开始直接插入数据到PostgreSQL，共 {len(records)} 条记录")
    
    # 获取PostgreSQL表的列
    pg_columns = get_postgresql_columns(pg_conn, 'pp_aufk')
    logger.info(f"PostgreSQL pp_aufk表共有 {len(pg_columns)} 列")
    
    if not pg_columns:
        logger.error("无法获取PostgreSQL表的列信息，跳过直接插入")
        return 0
    
    # 转换数据格式
    converted_records = []
    for record in records:
        converted = convert_to_postgresql_format(record, pg_columns)
        if converted.get('aufnr'):  # 确保有订单号
            converted_records.append(converted)
    
    if not converted_records:
        logger.warning("转换后没有有效记录")
        return 0
    
    logger.info(f"转换完成，有效记录 {len(converted_records)} 条")
    
    # 准备插入语句（使用UPSERT）
    available_columns = [col for col in pg_columns if col in converted_records[0].keys()]
    if not available_columns:
        logger.error("没有可用的列用于插入")
        return 0
    
    # 构建INSERT ... ON CONFLICT语句
    insert_sql = sql.SQL("""
        INSERT INTO pp_aufk ({})
        VALUES %s
        ON CONFLICT (aufnr) DO UPDATE SET {}
    """).format(
        sql.SQL(', ').join([sql.Identifier(col) for col in available_columns]),
        sql.SQL(', ').join([
            sql.SQL('{} = EXCLUDED.{}').format(
                sql.Identifier(col), sql.Identifier(col)
            ) for col in available_columns if col != 'aufnr'
        ])
    )
    
    # 准备数据
    values = []
    for record in converted_records:
        row_values = tuple(record.get(col) for col in available_columns)
        values.append(row_values)
    
    # 批量插入
    cursor = pg_conn.cursor()
    batch_size = 500
    total_inserted = 0
    
    try:
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            execute_values(cursor, insert_sql, batch)
            total_inserted += len(batch)
            logger.info(f"已插入 {total_inserted}/{len(values)} 条记录")
        
        pg_conn.commit()
        logger.info(f"成功插入 {total_inserted} 条记录到PostgreSQL")
        return total_inserted
        
    except Exception as e:
        pg_conn.rollback()
        logger.error(f"插入数据失败: {e}")
        raise
    finally:
        cursor.close()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("🚀 开始迁移SQLite aufk表数据到PostgreSQL pp_aufk表")
    logger.info("=" * 60)
    
    # 连接SQLite数据库
    sqlite_conn = get_sqlite_connection()
    if not sqlite_conn:
        logger.error("无法连接SQLite数据库，退出")
        return
    
    # 连接PostgreSQL数据库
    pg_conn = get_postgres_connection()
    if not pg_conn:
        logger.error("无法连接PostgreSQL数据库，退出")
        sqlite_conn.close()
        return
    
    try:
        # 读取SQLite数据
        logger.info("📖 正在读取SQLite aufk表数据...")
        records = read_sqlite_aufk_data(sqlite_conn)
        
        if not records:
            logger.warning("SQLite中没有数据需要迁移")
            return
        
        logger.info(f"✅ 成功读取 {len(records)} 条记录")
        
        # 方式1：尝试通过Java API迁移（推荐）
        if JAVA_API_BASE_URL:
            logger.info("方式1: 通过Java项目API迁移数据...")
            success_count = migrate_via_api(records)
            
            if success_count == len(records):
                logger.info("✅ 所有数据已成功通过API迁移")
                return
            else:
                logger.warning(f"⚠️ API迁移未完全成功 ({success_count}/{len(records)})，尝试直接插入...")
        
        # 方式2：直接插入PostgreSQL（备用方案）
        logger.info("方式2: 直接插入PostgreSQL数据库...")
        success_count = migrate_via_direct_insert(records, pg_conn)
        
        logger.info("=" * 60)
        logger.info(f"✅ 迁移完成！成功迁移 {success_count}/{len(records)} 条记录")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 迁移失败: {e}", exc_info=True)
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

