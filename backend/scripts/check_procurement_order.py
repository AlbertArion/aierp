#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断采购订单查询问题
检查订单号 0000000041 为什么查不到
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


def check_procurement_order(ebeln: str, mandt: str = None):
    """诊断采购订单查询问题"""
    conn = get_postgres_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 查询1: 检查订单是否存在（不限制 mandt）
        logger.info(f"\n{'='*80}")
        logger.info(f"查询1: 检查订单 {ebeln} 是否存在（所有 mandt）")
        logger.info(f"{'='*80}")
        
        query1 = """
            SELECT 
                mandt,
                ebeln,
                bsart,
                loekz,
                CASE 
                    WHEN loekz = 'X' THEN '已删除'
                    WHEN loekz IS NULL OR loekz = '' THEN '未删除'
                    ELSE '其他状态'
                END AS delete_status,
                bedat AS order_date,
                lifnr AS supplier,
                ekorg AS purchasing_org
            FROM mm_ekko
            WHERE ebeln = %s
            ORDER BY mandt
        """
        
        cursor.execute(query1, [ebeln])
        results1 = cursor.fetchall()
        
        if results1:
            logger.info(f"找到 {len(results1)} 条记录:")
            for i, row in enumerate(results1, 1):
                logger.info(f"\n记录 {i}:")
                for key, value in row.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("❌ 未找到任何记录 - 订单可能不存在")
        
        # 查询2: 检查订单在不同 mandt 下的情况
        logger.info(f"\n{'='*80}")
        logger.info(f"查询2: 按 mandt 分组统计订单 {ebeln}")
        logger.info(f"{'='*80}")
        
        query2 = """
            SELECT 
                mandt,
                COUNT(*) AS order_count,
                SUM(CASE WHEN loekz = 'X' THEN 1 ELSE 0 END) AS deleted_count,
                SUM(CASE WHEN loekz IS NULL OR loekz != 'X' THEN 1 ELSE 0 END) AS active_count
            FROM mm_ekko
            WHERE ebeln = %s
            GROUP BY mandt
        """
        
        cursor.execute(query2, [ebeln])
        results2 = cursor.fetchall()
        
        if results2:
            logger.info("统计结果:")
            for row in results2:
                logger.info(f"  mandt: {row['mandt']}, 总数: {row['order_count']}, "
                          f"已删除: {row['deleted_count']}, 活跃: {row['active_count']}")
        else:
            logger.warning("未找到统计结果")
        
        # 查询3: 检查订单在指定 mandt 下的详细情况
        target_mandt = mandt or '600'
        logger.info(f"\n{'='*80}")
        logger.info(f"查询3: 检查订单在 mandt={target_mandt} 下的详细情况")
        logger.info(f"{'='*80}")
        
        query3 = """
            SELECT 
                ekko.mandt,
                ekko.ebeln,
                ekko.bsart,
                ekko.loekz AS ekko_loekz,
                ekko.bedat,
                ekko.lifnr,
                ekko.ekorg,
                CASE 
                    WHEN ekko.loekz = 'X' THEN '订单已删除'
                    WHEN ekko.loekz IS NULL OR ekko.loekz = '' THEN '订单未删除'
                    ELSE '订单状态异常'
                END AS order_status,
                COUNT(ekpo.ebelp) AS line_item_count
            FROM mm_ekko ekko
            LEFT JOIN mm_ekpo ekpo ON ekpo.mandt = ekko.mandt AND ekpo.ebeln = ekko.ebeln
            WHERE ekko.ebeln = %s 
              AND ekko.mandt = %s
            GROUP BY ekko.mandt, ekko.ebeln, ekko.bsart, ekko.loekz, ekko.bedat, ekko.lifnr, ekko.ekorg
        """
        
        cursor.execute(query3, [ebeln, target_mandt])
        results3 = cursor.fetchall()
        
        if results3:
            logger.info(f"找到 {len(results3)} 条记录:")
            for i, row in enumerate(results3, 1):
                logger.info(f"\n记录 {i}:")
                for key, value in row.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning(f"❌ 在 mandt={target_mandt} 下未找到订单")
        
        # 查询4: 检查行项目情况
        logger.info(f"\n{'='*80}")
        logger.info(f"查询4: 检查订单 {ebeln} 的行项目情况")
        logger.info(f"{'='*80}")
        
        query4 = """
            SELECT 
                ekpo.mandt,
                ekpo.ebeln,
                ekpo.ebelp,
                ekpo.matnr,
                ekpo.loekz AS ekpo_loekz,
                ekpo.menge,
                CASE 
                    WHEN ekpo.loekz = 'X' THEN '行项目已删除'
                    WHEN ekpo.loekz IS NULL OR ekpo.loekz = '' THEN '行项目未删除'
                    ELSE '行项目状态异常'
                END AS line_item_status
            FROM mm_ekpo ekpo
            WHERE ekpo.ebeln = %s
            ORDER BY ekpo.mandt, ekpo.ebelp
        """
        
        cursor.execute(query4, [ebeln])
        results4 = cursor.fetchall()
        
        if results4:
            logger.info(f"找到 {len(results4)} 个行项目:")
            for i, row in enumerate(results4, 1):
                logger.info(f"\n行项目 {i}:")
                for key, value in row.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("❌ 未找到任何行项目")
        
        # 查询5: 模拟后端查询条件（检查为什么查不到）
        logger.info(f"\n{'='*80}")
        logger.info(f"查询5: 模拟后端查询条件（mandt={target_mandt}, ebeln={ebeln}, loekz != 'X'）")
        logger.info(f"{'='*80}")
        
        query5 = """
            SELECT 
                ekko.mandt,
                ekko.ebeln,
                ekko.loekz,
                CASE 
                    WHEN ekko.mandt = %s 
                         AND ekko.ebeln = %s 
                         AND (ekko.loekz IS NULL OR ekko.loekz != 'X') 
                    THEN '✅ 可以查到'
                    WHEN ekko.mandt != %s 
                    THEN CONCAT('❌ mandt不匹配，订单的mandt是: ', ekko.mandt)
                    WHEN ekko.loekz = 'X' 
                    THEN '❌ 订单已删除（loekz = X）'
                    ELSE '❌ 其他原因'
                END AS query_result
            FROM mm_ekko ekko
            WHERE ekko.ebeln = %s
        """
        
        cursor.execute(query5, [target_mandt, ebeln, target_mandt, ebeln])
        results5 = cursor.fetchall()
        
        if results5:
            logger.info("查询结果分析:")
            for row in results5:
                logger.info(f"\n  mandt: {row['mandt']}")
                logger.info(f"  ebeln: {row['ebeln']}")
                logger.info(f"  loekz: {row['loekz']}")
                logger.info(f"  结果: {row['query_result']}")
        else:
            logger.warning("❌ 未找到任何记录")
        
        # 查询6: 检查是否有类似的订单号
        logger.info(f"\n{'='*80}")
        logger.info(f"查询6: 查找类似的订单号（包含 {ebeln} 的数字部分）")
        logger.info(f"{'='*80}")
        
        # 提取数字部分
        numeric_part = ''.join(filter(str.isdigit, ebeln))
        if numeric_part:
            query6 = """
                SELECT 
                    mandt,
                    ebeln,
                    bsart,
                    loekz,
                    bedat,
                    lifnr
                FROM mm_ekko
                WHERE ebeln LIKE %s
                ORDER BY ebeln
                LIMIT 10
            """
            
            cursor.execute(query6, [f'%{numeric_part}%'])
            results6 = cursor.fetchall()
            
            if results6:
                logger.info(f"找到 {len(results6)} 条类似的订单:")
                for i, row in enumerate(results6, 1):
                    logger.info(f"\n订单 {i}:")
                    for key, value in row.items():
                        logger.info(f"  {key}: {value}")
            else:
                logger.warning("未找到类似的订单")
        
        # 总结诊断结果
        logger.info(f"\n{'='*80}")
        logger.info("诊断总结")
        logger.info(f"{'='*80}")
        
        if not results1:
            logger.error("❌ 问题：订单不存在于数据库中")
            logger.info("   解决方案：检查订单号是否正确，或订单是否已被物理删除")
        elif results3:
            # 检查是否被删除
            if results3[0]['ekko_loekz'] == 'X':
                logger.error(f"❌ 问题：订单在 mandt={target_mandt} 下已被逻辑删除（loekz = 'X'）")
                logger.info("   解决方案：如果需要恢复，可以将 loekz 设置为 NULL 或空字符串")
            else:
                logger.info(f"✅ 订单在 mandt={target_mandt} 下存在且未被删除")
                logger.warning("   如果前端仍然查不到，请检查：")
                logger.warning("   1. 前端传递的 mandt 是否正确")
                logger.warning("   2. 后端 AuthUtil.getMandt() 返回的值是否正确")
        else:
            # 订单存在但不在目标 mandt 下
            if results1:
                actual_mandt = results1[0]['mandt']
                logger.error(f"❌ 问题：订单存在，但 mandt 不匹配")
                logger.error(f"   期望的 mandt: {target_mandt}")
                logger.error(f"   实际的 mandt: {actual_mandt}")
                logger.info(f"   解决方案：使用正确的 mandt={actual_mandt} 查询，或检查前端传递的 mandt 参数")
        
        cursor.close()
        return {
            'all_mandt': results1,
            'mandt_statistics': results2,
            'target_mandt_detail': results3,
            'line_items': results4,
            'query_simulation': results5,
            'similar_orders': results6 if numeric_part else []
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
    ebeln = sys.argv[1] if len(sys.argv) > 1 else '0000000041'
    mandt = sys.argv[2] if len(sys.argv) > 2 else '600'
    
    logger.info(f"开始诊断采购订单: ebeln={ebeln}, mandt={mandt}")
    results = check_procurement_order(ebeln, mandt)
    
    if results:
        logger.info("\n✅ 诊断完成！")
    else:
        logger.error("❌ 诊断失败！")

