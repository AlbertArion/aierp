#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复生产订单状态
将 loekz 从 'X' 改为 NULL，使订单可以被查询到
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

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


def get_postgres_connection():
    """获取PostgreSQL数据库连接"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        logger.info(f"成功连接到PostgreSQL数据库: {POSTGRES_CONFIG['database']}")
        return conn
    except Exception as e:
        logger.error(f"连接PostgreSQL数据库失败: {e}")
        return None


def fix_production_order(aufnr: str, mandt: str = '600'):
    """修复生产订单状态"""
    conn = get_postgres_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. 先查询当前状态
        logger.info(f"\n{'='*80}")
        logger.info(f"查询订单当前状态: aufnr={aufnr}, mandt={mandt}")
        logger.info(f"{'='*80}")
        
        query_current = """
            SELECT 
                afko.mandt,
                afko.aufnr,
                afko.rsnum,
                aufk.loekz,
                aufk.is_deleted as aufk_is_deleted,
                afko.is_deleted as afko_is_deleted
            FROM pp_afko afko
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            WHERE afko.aufnr = %s AND afko.mandt = %s
        """
        
        cursor.execute(query_current, [aufnr, mandt])
        current = cursor.fetchone()
        
        if not current:
            logger.error(f"未找到订单: aufnr={aufnr}, mandt={mandt}")
            return False
        
        logger.info(f"当前状态:")
        logger.info(f"  loekz: {current['loekz']}")
        logger.info(f"  aufk_is_deleted: {current['aufk_is_deleted']}")
        logger.info(f"  afko_is_deleted: {current['afko_is_deleted']}")
        logger.info(f"  rsnum: {current['rsnum']}")
        
        # 2. 修复 pp_aufk 表的 loekz 字段
        if current['loekz'] == 'X':
            logger.info(f"\n{'='*80}")
            logger.info(f"修复 pp_aufk 表的 loekz 字段")
            logger.info(f"{'='*80}")
            
            update_aufk = """
                UPDATE pp_aufk
                SET loekz = NULL
                WHERE aufnr = %s AND mandt = %s
            """
            
            cursor.execute(update_aufk, [aufnr, mandt])
            affected_rows = cursor.rowcount
            
            if affected_rows > 0:
                logger.info(f"✓ 成功更新 pp_aufk 表，影响行数: {affected_rows}")
            else:
                logger.warning(f"⚠ 未更新任何行，可能订单在 pp_aufk 表中不存在")
        
        # 3. 确保 is_deleted 字段为 0 或 NULL
        if current['aufk_is_deleted'] == 1:
            logger.info(f"\n{'='*80}")
            logger.info(f"修复 pp_aufk 表的 is_deleted 字段")
            logger.info(f"{'='*80}")
            
            update_aufk_deleted = """
                UPDATE pp_aufk
                SET is_deleted = 0
                WHERE aufnr = %s AND mandt = %s
            """
            
            cursor.execute(update_aufk_deleted, [aufnr, mandt])
            affected_rows = cursor.rowcount
            logger.info(f"✓ 成功更新 pp_aufk.is_deleted，影响行数: {affected_rows}")
        
        if current['afko_is_deleted'] == 1:
            logger.info(f"\n{'='*80}")
            logger.info(f"修复 pp_afko 表的 is_deleted 字段")
            logger.info(f"{'='*80}")
            
            update_afko_deleted = """
                UPDATE pp_afko
                SET is_deleted = 0
                WHERE aufnr = %s AND mandt = %s
            """
            
            cursor.execute(update_afko_deleted, [aufnr, mandt])
            affected_rows = cursor.rowcount
            logger.info(f"✓ 成功更新 pp_afko.is_deleted，影响行数: {affected_rows}")
        
        # 4. 验证修复结果
        logger.info(f"\n{'='*80}")
        logger.info(f"验证修复结果")
        logger.info(f"{'='*80}")
        
        cursor.execute(query_current, [aufnr, mandt])
        after = cursor.fetchone()
        
        if after:
            logger.info(f"修复后状态:")
            logger.info(f"  loekz: {after['loekz']} (应该是 NULL)")
            logger.info(f"  aufk_is_deleted: {after['aufk_is_deleted']} (应该是 0 或 NULL)")
            logger.info(f"  afko_is_deleted: {after['afko_is_deleted']} (应该是 0 或 NULL)")
            logger.info(f"  rsnum: {after['rsnum']}")
            
            # 检查是否符合查询条件
            can_query = (
                (after['loekz'] is None or after['loekz'] != 'X') and
                (after['aufk_is_deleted'] is None or after['aufk_is_deleted'] == 0) and
                (after['afko_is_deleted'] is None or after['afko_is_deleted'] == 0)
            )
            
            if can_query:
                logger.info(f"\n✓ 订单现在可以被查询到了！")
            else:
                logger.warning(f"\n⚠ 订单可能仍然无法被查询，请检查状态")
        else:
            logger.error(f"验证失败：无法查询到订单")
            return False
        
        # 5. 测试查询（模拟后端 SQL）
        logger.info(f"\n{'='*80}")
        logger.info(f"测试后端 SQL 查询（模拟 listV2 接口）")
        logger.info(f"{'='*80}")
        
        test_query = """
            SELECT 
                afko.mandt,
                afko.aufnr,
                afko.rsnum,
                afko.gamng,
                afko.gmein,
                aufk.werks,
                aufk.auart,
                aufk.loekz,
                afpo.matnr
            FROM pp_afko afko
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            LEFT JOIN pp_afpo afpo ON afko.mandt = afpo.mandt AND afko.aufnr = afpo.aufnr
            WHERE afko.aufnr LIKE %s
            AND afko.mandt = %s
            AND (afko.is_deleted IS NULL OR afko.is_deleted = 0)
            AND (aufk.loekz IS NULL OR aufk.loekz != 'X')
            AND (aufk.is_deleted IS NULL OR aufk.is_deleted = 0)
        """
        
        cursor.execute(test_query, [f'%{aufnr}%', mandt])
        test_results = cursor.fetchall()
        
        if test_results:
            logger.info(f"✓ 测试查询成功！找到 {len(test_results)} 条记录")
            for row in test_results:
                logger.info(f"  订单号: {row['aufnr']}, 物料: {row['matnr']}, 数量: {row['gamng']} {row['gmein']}")
        else:
            logger.warning(f"⚠ 测试查询未找到记录，可能还有其他问题")
        
        # 提交事务
        conn.commit()
        logger.info(f"\n✓ 所有修改已提交到数据库")
        
        cursor.close()
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    # 从命令行参数获取订单号，如果没有则使用默认值
    aufnr = sys.argv[1] if len(sys.argv) > 1 else '800000000042'
    mandt = sys.argv[2] if len(sys.argv) > 2 else '600'
    
    logger.info(f"开始修复生产订单: aufnr={aufnr}, mandt={mandt}")
    success = fix_production_order(aufnr, mandt)
    
    if success:
        logger.info("\n✓ 修复完成！")
    else:
        logger.error("\n✗ 修复失败！")

