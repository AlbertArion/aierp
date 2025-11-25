#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入PP Agent所需数据到PostgreSQL数据库
从Excel文件读取数据并插入到对应的表中
"""

import sys
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import sql
import logging
from typing import Dict, List, Any
import numpy as np
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库连接配置
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'sinocst_erp'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

# Excel文件路径
EXCEL_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    'docs/需求文档/Agent/PP_Agent/PP Agent 所需数据.xlsx'
)

# 表名映射（Excel工作表名 -> 数据库表名）
# 注意：根据实际Java实体类，JEST使用cd_jest，MAKT使用md_makt
# 但需求文档要求使用pp_前缀，这里先使用pp_前缀，如果表不存在再尝试其他表名
TABLE_MAPPING = {
    'AFKO': 'pp_afko',
    'AFPO': 'pp_afpo',
    'AFVC': 'pp_afvc',
    'AFVV': 'pp_afvv',
    'AUFK': 'pp_aufk',
    'JEST': 'pp_jest',  # 如果不存在，可能需要使用cd_jest
    'MAKT': 'pp_makt'   # 如果不存在，可能需要使用md_makt
}


def get_db_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info(f"成功连接到PostgreSQL数据库: {DB_CONFIG['database']}")
        return conn
    except Exception as e:
        logger.error(f"连接数据库失败: {e}")
        raise


def check_table_exists(conn, table_name: str) -> bool:
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, (table_name,))
    exists = cursor.fetchone()[0]
    cursor.close()
    return exists


def create_table_if_not_exists(conn, table_name: str, df: pd.DataFrame):
    """如果表不存在则创建表"""
    if check_table_exists(conn, table_name):
        logger.info(f"表 {table_name} 已存在，跳过创建")
        return
    
    logger.info(f"创建表 {table_name}...")
    cursor = conn.cursor()
    
    # 根据DataFrame的列和数据类型生成CREATE TABLE语句
    columns = []
    for col in df.columns:
        col_lower = col.lower()
        # 根据数据类型推断SQL类型
        dtype = df[col].dtype
        
        if pd.api.types.is_integer_dtype(dtype):
            sql_type = "BIGINT"
        elif pd.api.types.is_float_dtype(dtype):
            sql_type = "NUMERIC(13,3)"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            sql_type = "DATE"
        elif pd.api.types.is_bool_dtype(dtype):
            sql_type = "BOOLEAN"
        else:
            # 字符串类型，根据最大长度设置
            max_len = df[col].astype(str).str.len().max()
            if pd.isna(max_len) or max_len == 0:
                max_len = 255
            else:
                max_len = min(int(max_len * 1.5), 4000)  # 增加一些缓冲
            sql_type = f"VARCHAR({max_len})"
        
        # 设置主键（根据表名和列名判断）
        # 注意：pp_afko 和 pp_aufk 使用复合主键 (mandt, aufnr)，不在列定义中设置 PRIMARY KEY
        if table_name == 'pp_afko' and col_lower == 'aufnr':
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_aufk' and col_lower == 'aufnr':
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_afko' and col_lower == 'mandt':
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_aufk' and col_lower == 'mandt':
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_afpo' and col_lower in ['aufnr', 'posnr']:
            if col_lower == 'aufnr':
                columns.append(f'"{col_lower}" {sql_type} NOT NULL')
            else:
                columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_afvc' and col_lower in ['aufpl', 'aplzl']:
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_afvv' and col_lower in ['aufpl', 'aplzl']:
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_jest' and col_lower in ['objnr', 'stat']:
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        elif table_name == 'pp_makt' and col_lower in ['matnr', 'spras']:
            columns.append(f'"{col_lower}" {sql_type} NOT NULL')
        else:
            columns.append(f'"{col_lower}" {sql_type}')
    
    # 为复合主键添加约束（根据实际数据库表的主键定义）
    if table_name == 'pp_afko':
        columns.append('PRIMARY KEY ("aufnr")')
    elif table_name == 'pp_aufk':
        columns.append('PRIMARY KEY ("aufnr")')
    elif table_name == 'pp_afpo':
        columns.append('PRIMARY KEY ("mandt", "aufnr", "posnr")')
    elif table_name == 'pp_afvc':
        columns.append('PRIMARY KEY ("mandt", "aufpl", "aplzl")')
    elif table_name == 'pp_afvv':
        columns.append('PRIMARY KEY ("mandt", "aufpl", "aplzl")')
    elif table_name == 'pp_jest':
        columns.append('PRIMARY KEY ("objnr", "stat")')
    elif table_name == 'pp_makt':
        columns.append('PRIMARY KEY ("matnr", "spras")')
    
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})'
    
    try:
        cursor.execute(create_sql)
        conn.commit()
        logger.info(f"表 {table_name} 创建成功")
    except Exception as e:
        conn.rollback()
        logger.error(f"创建表 {table_name} 失败: {e}")
        raise
    finally:
        cursor.close()


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """清理数据：处理NaN值、日期格式等"""
    df = df.copy()
    
    # 处理日期列：将NaT和无效日期转换为None
    # 注意：不要将Timestamp转换为None，保留它们以便后续转换为YYYYMMDD格式
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            # 日期时间类型：只将NaT转换为None，保留有效日期
            df[col] = df[col].where(pd.notna(df[col]), None)
        elif df[col].dtype == 'object':
            # 尝试转换日期格式（仅对看起来像日期的列）
            try:
                # 只对包含日期格式的列进行转换
                sample = df[col].dropna().head(5)
                if len(sample) > 0 and any(str(s).replace('-', '').replace('/', '').isdigit() and len(str(s)) >= 8 for s in sample):
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].where(pd.notna(df[col]), None)
            except:
                pass
    
    # 将NaN替换为None（PostgreSQL的NULL），但保留有效字符串
    # 只替换真正的NaN值，不替换字符串
    for col in df.columns:
        if df[col].dtype == 'object':
            # 只替换真正的NaN/NaT，不替换字符串
            df[col] = df[col].where(pd.notna(df[col]), None)
        else:
            df[col] = df[col].replace({np.nan: None, pd.NA: None})
    
    # 处理特殊值：将字符串'nan'、'NaN'、'None'、'NaT'转换为None（但保留其他有效字符串）
    for col in df.columns:
        if df[col].dtype == 'object':
            # 只替换特定的无效字符串，保留其他值
            df[col] = df[col].replace({'nan': None, 'NaN': None, 'None': None, 'NaT': None})
            # 空字符串转换为None
            df[col] = df[col].replace({'': None})
    
    return df


def get_table_columns(conn, table_name: str) -> List[str]:
    """获取表中已存在的列名"""
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


def get_table_primary_key(conn, table_name: str) -> List[str]:
    """获取表的主键列"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = 'public'
            AND tc.table_name = %s
            AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position;
    """, (table_name,))
    pk_columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return pk_columns


def get_table_column_info(conn, table_name: str) -> Dict[str, Dict]:
    """获取表的列信息（包括类型、长度、是否可空等）"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    column_info = {}
    for row in cursor.fetchall():
        column_info[row[0]] = {
            'data_type': row[1],
            'max_length': row[2],
            'numeric_precision': row[3],
            'numeric_scale': row[4],
            'nullable': row[5] == 'YES',
            'default': row[6]
        }
    cursor.close()
    return column_info


def add_missing_columns(conn, table_name: str, df: pd.DataFrame, existing_columns: List[str]):
    """添加Excel中存在但数据库表中不存在的列"""
    excel_columns = [col.lower() for col in df.columns]
    missing_columns = [col for col in excel_columns if col not in existing_columns]
    
    if not missing_columns:
        return
    
    logger.info(f"表 {table_name} 缺少 {len(missing_columns)} 个列，开始添加...")
    cursor = conn.cursor()
    
    for col in missing_columns:
        try:
            # 获取该列的数据类型和示例值
            col_upper = col.upper()
            if col_upper not in df.columns:
                continue
            
            sample_data = df[col_upper].dropna().head(10)
            if len(sample_data) == 0:
                # 如果所有值都是NaN，使用VARCHAR(255)
                sql_type = "VARCHAR(255)"
            else:
                # 根据数据类型推断SQL类型
                dtype = df[col_upper].dtype
                max_length = df[col_upper].astype(str).str.len().max() if df[col_upper].dtype == 'object' else None
                
                if pd.api.types.is_integer_dtype(dtype):
                    sql_type = "BIGINT"
                elif pd.api.types.is_float_dtype(dtype):
                    sql_type = "NUMERIC(13,3)"
                elif pd.api.types.is_datetime64_any_dtype(dtype):
                    # 检查是否是日期时间还是日期
                    if max_length and max_length > 10:
                        sql_type = "TIMESTAMP"
                    else:
                        sql_type = "VARCHAR(8)"  # YYYYMMDD格式
                else:
                    # 字符串类型
                    if max_length:
                        # 根据最大长度设置合适的VARCHAR长度，至少255
                        varchar_len = max(255, int(max_length * 1.2))  # 增加20%的缓冲
                        sql_type = f"VARCHAR({varchar_len})"
                    else:
                        sql_type = "VARCHAR(255)"
            
            # 添加列
            alter_sql = f'ALTER TABLE {table_name} ADD COLUMN "{col}" {sql_type}'
            cursor.execute(alter_sql)
            logger.info(f"  已添加列 {col} ({sql_type})")
        except Exception as e:
            logger.warning(f"  添加列 {col} 失败: {e}")
            continue
    
    conn.commit()
    cursor.close()
    logger.info(f"表 {table_name} 列添加完成")


def extend_column_length(conn, table_name: str, column_name: str, required_length: int):
    """扩展字段长度"""
    cursor = conn.cursor()
    try:
        # 获取当前字段类型
        cursor.execute("""
            SELECT data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = %s 
            AND column_name = %s;
        """, (table_name, column_name))
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"列 {column_name} 不存在，跳过扩展")
            return
        
        current_type = result[0]
        current_length = result[1]
        
        # 只处理VARCHAR类型
        if current_type == 'character varying' and current_length and required_length > current_length:
            # 计算新的长度（增加20%的缓冲）
            new_length = max(required_length, int(required_length * 1.2))
            alter_sql = f'ALTER TABLE {table_name} ALTER COLUMN "{column_name}" TYPE VARCHAR({new_length})'
            cursor.execute(alter_sql)
            conn.commit()
            logger.info(f"  已扩展列 {column_name} 长度: {current_length} -> {new_length}")
    except Exception as e:
        logger.warning(f"  扩展列 {column_name} 长度失败: {e}")
        conn.rollback()
    finally:
        cursor.close()


def insert_data(conn, table_name: str, df: pd.DataFrame, batch_size: int = 1000):
    """插入数据到数据库"""
    if df.empty:
        logger.warning(f"表 {table_name} 没有数据需要插入")
        return 0
    
    # 清理数据
    df = clean_data(df)
    
    # 转换为小写列名
    df.columns = df.columns.str.lower()
    
    # 检查表是否存在，不存在则创建
    if not check_table_exists(conn, table_name):
        create_table_if_not_exists(conn, table_name, df)
    
    # 获取表中已存在的列
    existing_columns = get_table_columns(conn, table_name)
    if not existing_columns:
        logger.warning(f"表 {table_name} 没有列，跳过插入")
        return 0
    
    # 添加缺失的列
    add_missing_columns(conn, table_name, df, existing_columns)
    
    # 重新获取列（可能已经添加了新列）
    existing_columns = get_table_columns(conn, table_name)
    
    # 只保留表中存在的列
    available_columns = [col for col in df.columns if col in existing_columns]
    if not available_columns:
        logger.warning(f"表 {table_name} 中没有匹配的列，跳过插入")
        return 0
    
    # 记录缺失的列（如果还有）
    missing_columns = [col for col in df.columns if col not in existing_columns]
    if missing_columns:
        logger.warning(f"表 {table_name} 仍有以下列无法添加（将跳过）: {', '.join(missing_columns[:10])}{'...' if len(missing_columns) > 10 else ''}")
    
    # 获取表的列信息（在数据处理之前）
    column_info = get_table_column_info(conn, table_name)
    
    # 检查并扩展字段长度（在数据处理之前）
    # 注意：df的列名已经转换为小写了（第380行）
    for col in available_columns:
        if col in column_info and column_info[col]['max_length']:
            if col in df.columns:
                # 对于所有类型，都转换为字符串检查长度
                max_data_length = df[col].astype(str).str.len().max()
                # 如果数据长度等于或超过字段长度，都需要扩展（留出缓冲）
                if not pd.isna(max_data_length) and max_data_length >= column_info[col]['max_length']:
                    # 计算新长度：至少增加20%缓冲，或至少增加3个字符
                    new_length = max(int(max_data_length * 1.2), max_data_length + 3)
                    logger.info(f"列 {col} 数据最大长度 {max_data_length} 达到或超过字段长度 {column_info[col]['max_length']}，开始扩展到 {new_length}...")
                    extend_column_length(conn, table_name, col, int(new_length))
                    # 更新column_info
                    column_info = get_table_column_info(conn, table_name)
    
    # 过滤DataFrame，只保留存在的列（在字段扩展之后）
    df_filtered = df[available_columns].copy()
    
    # 处理数据：截断超长字符串，过滤NULL值违反约束的行
    for col in available_columns:
        if col in column_info:
            max_len = column_info[col]['max_length']
            nullable = column_info[col]['nullable']
            
            # 截断超长字符串（对所有有长度限制的字段都处理）
            if max_len:
                import re
                from datetime import datetime
                
                # 特殊处理：如果是日期格式（YYYY-MM-DD或YYYY.MM.DD），转换为YYYYMMDD格式
                if max_len == 8:
                    def convert_date(val):
                        if pd.isna(val) or val is None:
                            return None
                        # 处理Timestamp对象（优先处理）
                        if isinstance(val, pd.Timestamp):
                            return val.strftime('%Y%m%d')
                        # 处理datetime对象
                        if isinstance(val, datetime):
                            return val.strftime('%Y%m%d')
                        val_str = str(val).strip()
                        # 如果已经是空字符串或无效值
                        if val_str == '' or val_str.lower() in ['nan', 'none', 'nat']:
                            return None
                        # 匹配日期格式 YYYY-MM-DD 或 YYYY.MM.DD 或 YYYY-MM-DD HH:MM:SS
                        date_pattern = r'^(\d{4})[-./](\d{2})[-./](\d{2})'
                        match = re.match(date_pattern, val_str)
                        if match:
                            # 转换为YYYYMMDD格式
                            return match.group(1) + match.group(2) + match.group(3)
                        # 如果已经是8位数字，直接返回
                        if len(val_str) == 8 and val_str.isdigit():
                            return val_str
                        # 如果超过8位，截断前8位
                        if len(val_str) > max_len:
                            return val_str[:max_len]
                        return val_str
                    
                    df_filtered[col] = df_filtered[col].apply(convert_date)
                else:
                    # 非日期字段，处理字符串长度（对所有类型都处理，确保转换为字符串）
                    def truncate_str(val, max_length):
                        if pd.isna(val) or val is None:
                            return None
                        val_str = str(val).strip()
                        # 处理特殊值
                        if val_str == '' or val_str.lower() in ['nan', 'none', 'nat']:
                            return None
                        # 截断超长字符串
                        if len(val_str) > max_length:
                            logger.warning(f"表 {table_name} 列 {col} 的值长度 {len(val_str)} 超过字段长度 {max_length}，已截断")
                            return val_str[:max_length]
                        return val_str
                    
                    # 应用截断函数（对所有类型都处理，确保转换为字符串）
                    df_filtered[col] = df_filtered[col].apply(lambda x: truncate_str(x, max_len))
            
            # 如果列不允许NULL，用默认值填充而不是过滤
            if not nullable:
                null_count = df_filtered[col].isna().sum() + (df_filtered[col] == '').sum()
                if null_count > 0:
                    # 对于主键列，必须过滤掉NULL值行
                    if col in ['objnr', 'stat', 'aufnr', 'aufpl', 'aplzl', 'posnr', 'vornr']:
                        before_count = len(df_filtered)
                        mask = pd.notna(df_filtered[col]) & (df_filtered[col] != '') & (df_filtered[col] != 'nan') & (df_filtered[col] != 'NaN') & (df_filtered[col] != 'None') & (df_filtered[col] != 'NaT')
                        df_filtered = df_filtered[mask]
                        after_count = len(df_filtered)
                        if before_count > after_count:
                            logger.warning(f"表 {table_name} 主键列 {col} 不允许NULL，已过滤 {before_count - after_count} 行")
                    else:
                        # 非主键列，用默认值填充
                        default_value = ''
                        if column_info[col]['data_type'] in ['integer', 'bigint', 'numeric']:
                            default_value = 0
                        elif column_info[col]['data_type'] == 'date':
                            default_value = None  # 日期类型不能填充空字符串
                        else:
                            default_value = ''
                        
                        if default_value is not None:
                            df_filtered[col] = df_filtered[col].fillna(default_value)
                            df_filtered[col] = df_filtered[col].replace({'': default_value, 'nan': default_value, 'NaN': default_value, 'None': default_value, 'NaT': default_value})
                            logger.info(f"表 {table_name} 列 {col} 不允许NULL，已用默认值填充 {null_count} 个NULL值")
                        else:
                            # 如果无法填充，过滤掉NULL值行
                            before_count = len(df_filtered)
                            mask = pd.notna(df_filtered[col]) & (df_filtered[col] != '') & (df_filtered[col] != 'nan') & (df_filtered[col] != 'NaN') & (df_filtered[col] != 'None') & (df_filtered[col] != 'NaT')
                            df_filtered = df_filtered[mask]
                            after_count = len(df_filtered)
                            if before_count > after_count:
                                logger.warning(f"表 {table_name} 列 {col} 不允许NULL且无法填充，已过滤 {before_count - after_count} 行")
    
    if df_filtered.empty:
        logger.warning(f"表 {table_name} 过滤后没有有效数据，跳过插入")
        return 0
    
    # 动态获取表的主键列（用于 ON CONFLICT）
    primary_key_columns = get_table_primary_key(conn, table_name)
    
    # 检查主键列是否都在 available_columns 中
    pk_available = all(pk_col in available_columns for pk_col in primary_key_columns) if primary_key_columns else False
    
    # 准备插入语句
    if pk_available and primary_key_columns:
        # 使用 UPSERT：如果主键冲突则更新，否则插入
        conflict_target = sql.SQL(', ').join([sql.Identifier(col) for col in primary_key_columns])
        # 获取需要更新的列（排除主键列）
        update_columns = [col for col in available_columns if col not in primary_key_columns]
        if update_columns:
            update_set = sql.SQL(', ').join([
                sql.SQL('{} = EXCLUDED.{}').format(
                    sql.Identifier(col), sql.Identifier(col)
                ) for col in update_columns
            ])
            insert_sql = sql.SQL("""
                INSERT INTO {} ({})
                VALUES %s
                ON CONFLICT ({}) DO UPDATE SET {}
            """).format(
                sql.Identifier(table_name),
                sql.SQL(', ').join([sql.Identifier(col) for col in available_columns]),
                conflict_target,
                update_set
            )
        else:
            # 如果没有可更新的列，使用 DO NOTHING
            insert_sql = sql.SQL("""
                INSERT INTO {} ({})
                VALUES %s
                ON CONFLICT ({}) DO NOTHING
            """).format(
                sql.Identifier(table_name),
                sql.SQL(', ').join([sql.Identifier(col) for col in available_columns]),
                conflict_target
            )
    else:
        # 如果没有主键信息，使用简单的 INSERT（可能会报错，但至少会尝试插入）
        logger.warning(f"表 {table_name} 无法确定主键，使用简单 INSERT（可能产生重复数据）")
        insert_sql = sql.SQL("""
            INSERT INTO {} ({})
            VALUES %s
        """).format(
            sql.Identifier(table_name),
            sql.SQL(', ').join([sql.Identifier(col) for col in available_columns])
        )
    
    # 转换数据为元组列表，处理None值
    values = []
    for row in df_filtered.values:
        row_tuple = tuple(None if pd.isna(val) else val for val in row)
        values.append(row_tuple)
    
    cursor = conn.cursor()
    try:
        # 批量插入
        total_inserted = 0
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            execute_values(cursor, insert_sql, batch)
            total_inserted += len(batch)
            logger.info(f"已插入 {total_inserted}/{len(values)} 条记录到 {table_name}")
        
        conn.commit()
        logger.info(f"成功插入 {total_inserted} 条记录到 {table_name}")
        return total_inserted
    except Exception as e:
        conn.rollback()
        logger.error(f"插入数据到 {table_name} 失败: {e}")
        raise
    finally:
        cursor.close()


def import_excel_data():
    """导入Excel数据到数据库"""
    logger.info("🚀 开始导入PP Agent数据...")
    
    # 检查Excel文件是否存在
    if not os.path.exists(EXCEL_FILE):
        logger.error(f"Excel文件不存在: {EXCEL_FILE}")
        return
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        # 读取Excel文件的所有工作表
        logger.info(f"正在读取Excel文件: {EXCEL_FILE}")
        excel_data = pd.read_excel(EXCEL_FILE, sheet_name=None)
        
        # 导入每个工作表的数据
        results = {}
        for sheet_name, df in excel_data.items():
            # 跳过示例数据表
            if sheet_name == '示例数据':
                logger.info(f"跳过工作表: {sheet_name}")
                continue
            
            # 获取对应的数据库表名
            table_name = TABLE_MAPPING.get(sheet_name)
            if not table_name:
                logger.warning(f"工作表 {sheet_name} 没有对应的数据库表，跳过")
                continue
            
            logger.info(f"正在处理工作表: {sheet_name} -> 表: {table_name}")
            logger.info(f"数据行数: {len(df)}, 列数: {len(df.columns)}")
            
            # 插入数据
            try:
                count = insert_data(conn, table_name, df)
                results[table_name] = count
                logger.info(f"✅ {table_name} 导入完成，共 {count} 条记录")
            except Exception as e:
                logger.error(f"❌ {table_name} 导入失败: {e}")
                results[table_name] = 0
        
        # 输出汇总
        logger.info("\n" + "="*50)
        logger.info("导入汇总:")
        for table_name, count in results.items():
            logger.info(f"  {table_name}: {count} 条记录")
        logger.info("="*50)
        logger.info("🎉 PP Agent数据导入完成！")
        
    except Exception as e:
        logger.error(f"导入数据失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        import_excel_data()
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

