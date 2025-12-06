#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询生产订单信息
检查订单号是否存在，以及订单状态
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


def query_production_order(aufnr: str, mandt: str = None):
    """查询生产订单信息"""
    conn = get_postgres_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 查询1: 在 pp_afko 表中查找订单
        logger.info(f"\n{'='*80}")
        logger.info(f"查询1: 在 pp_afko 表中查找订单号: {aufnr}")
        logger.info(f"{'='*80}")
        
        query1 = """
            SELECT 
                afko.mandt,
                afko.aufnr,
                afko.rsnum,
                afko.gamng,
                afko.gmein,
                afko.is_deleted as afko_is_deleted,
                aufk.werks,
                aufk.auart,
                aufk.loekz,
                aufk.is_deleted as aufk_is_deleted,
                aufk.ktext,
                afpo.matnr,
                afpo.psmng,
                afpo.wemng
            FROM pp_afko afko
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            LEFT JOIN pp_afpo afpo ON afko.mandt = afpo.mandt AND afko.aufnr = afpo.aufnr
            WHERE afko.aufnr LIKE %s
        """
        
        params = [f'%{aufnr}%']
        if mandt:
            query1 += " AND afko.mandt = %s"
            params.append(mandt)
        
        cursor.execute(query1, params)
        results1 = cursor.fetchall()
        
        if results1:
            logger.info(f"找到 {len(results1)} 条记录:")
            for i, row in enumerate(results1, 1):
                logger.info(f"\n记录 {i}:")
                for key, value in row.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("未找到任何记录")
        
        # 查询2: 精确匹配订单号（不带LIKE）
        logger.info(f"\n{'='*80}")
        logger.info(f"查询2: 精确匹配订单号: {aufnr}")
        logger.info(f"{'='*80}")
        
        query2 = """
            SELECT 
                afko.mandt,
                afko.aufnr,
                afko.rsnum,
                afko.gamng,
                afko.gmein,
                afko.is_deleted as afko_is_deleted,
                aufk.werks,
                aufk.auart,
                aufk.loekz,
                aufk.is_deleted as aufk_is_deleted,
                aufk.ktext,
                afpo.matnr,
                afpo.psmng,
                afpo.wemng
            FROM pp_afko afko
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            LEFT JOIN pp_afpo afpo ON afko.mandt = afpo.mandt AND afko.aufnr = afpo.aufnr
            WHERE afko.aufnr = %s
        """
        
        params2 = [aufnr]
        if mandt:
            query2 += " AND afko.mandt = %s"
            params2.append(mandt)
        
        cursor.execute(query2, params2)
        results2 = cursor.fetchall()
        
        if results2:
            logger.info(f"找到 {len(results2)} 条精确匹配记录:")
            for i, row in enumerate(results2, 1):
                logger.info(f"\n记录 {i}:")
                for key, value in row.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("未找到精确匹配的记录")
        
        # 查询3: 检查所有 mandt 下的订单
        logger.info(f"\n{'='*80}")
        logger.info(f"查询3: 在所有 mandt 下查找订单号: {aufnr}")
        logger.info(f"{'='*80}")
        
        query3 = """
            SELECT 
                afko.mandt,
                afko.aufnr,
                afko.rsnum,
                afko.gamng,
                afko.gmein,
                afko.is_deleted as afko_is_deleted,
                aufk.werks,
                aufk.auart,
                aufk.loekz,
                aufk.is_deleted as aufk_is_deleted,
                aufk.ktext,
                afpo.matnr,
                afpo.psmng,
                afpo.wemng
            FROM pp_afko afko
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            LEFT JOIN pp_afpo afpo ON afko.mandt = afpo.mandt AND afko.aufnr = afpo.aufnr
            WHERE afko.aufnr = %s
            ORDER BY afko.mandt
        """
        
        cursor.execute(query3, [aufnr])
        results3 = cursor.fetchall()
        
        if results3:
            logger.info(f"找到 {len(results3)} 条记录（所有 mandt）:")
            for i, row in enumerate(results3, 1):
                logger.info(f"\n记录 {i}:")
                for key, value in row.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("在所有 mandt 下都未找到该订单")
        
        # 查询4: 检查是否有类似的订单号（可能格式不同）
        logger.info(f"\n{'='*80}")
        logger.info(f"查询4: 查找类似的订单号（包含 {aufnr} 的数字部分）")
        logger.info(f"{'='*80}")
        
        # 提取数字部分
        numeric_part = ''.join(filter(str.isdigit, aufnr))
        if numeric_part:
            query4 = """
                SELECT 
                    afko.mandt,
                    afko.aufnr,
                    afko.rsnum,
                    afko.gamng,
                    afko.gmein,
                    afko.is_deleted as afko_is_deleted,
                    aufk.werks,
                    aufk.auart,
                    aufk.loekz,
                    aufk.is_deleted as aufk_is_deleted,
                    aufk.ktext
                FROM pp_afko afko
                LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
                WHERE afko.aufnr LIKE %s
                ORDER BY afko.aufnr
                LIMIT 10
            """
            
            cursor.execute(query4, [f'%{numeric_part}%'])
            results4 = cursor.fetchall()
            
            if results4:
                logger.info(f"找到 {len(results4)} 条类似的订单:")
                for i, row in enumerate(results4, 1):
                    logger.info(f"\n记录 {i}:")
                    for key, value in row.items():
                        logger.info(f"  {key}: {value}")
            else:
                logger.warning("未找到类似的订单")
        
        # 查询5: 统计订单总数和 mandt 分布
        logger.info(f"\n{'='*80}")
        logger.info("查询5: 统计 pp_afko 表中的订单分布")
        logger.info(f"{'='*80}")
        
        query5 = """
            SELECT 
                mandt,
                COUNT(*) as total_count,
                COUNT(CASE WHEN is_deleted = 1 THEN 1 END) as deleted_count,
                COUNT(CASE WHEN is_deleted = 0 OR is_deleted IS NULL THEN 1 END) as active_count
            FROM pp_afko
            GROUP BY mandt
            ORDER BY mandt
        """
        
        cursor.execute(query5)
        results5 = cursor.fetchall()
        
        if results5:
            logger.info("订单统计:")
            for row in results5:
                logger.info(f"  mandt: {row['mandt']}, 总数: {row['total_count']}, "
                          f"已删除: {row['deleted_count']}, 活跃: {row['active_count']}")
        else:
            logger.warning("未找到任何订单统计")
        
        cursor.close()
        return {
            'like_match': results1,
            'exact_match': results2,
            'all_mandt': results3,
            'similar': results4 if numeric_part else [],
            'statistics': results5
        }
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()


if __name__ == '__main__':
    # 从命令行参数获取订单号，如果没有则使用默认值
    aufnr = sys.argv[1] if len(sys.argv) > 1 else '800000000042'
    mandt = sys.argv[2] if len(sys.argv) > 2 else '600'
    
    logger.info(f"开始查询生产订单: aufnr={aufnr}, mandt={mandt}")
    results = query_production_order(aufnr, mandt)
    
    if results:
        logger.info("\n查询完成！")
    else:
        logger.error("查询失败！")

