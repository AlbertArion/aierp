#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复采购订单的 bstyp（采购凭证类别）字段
根据 bsart（采购凭证类型）从 cd_t161 表中获取对应的 bstyp 并更新
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


def get_bstyp_mapping(conn, mandt: str = '600'):
    """
    获取采购凭证类型到凭证类别的映射关系
    
    Returns:
        dict: {bsart: bstyp} 的映射字典
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT DISTINCT bsart, bstyp
        FROM cd_t161
        WHERE mandt = %s
          AND (is_deleted = 0 OR is_deleted IS NULL)
          AND bsart IS NOT NULL
          AND bstyp IS NOT NULL
    """
    
    cursor.execute(query, [mandt])
    results = cursor.fetchall()
    
    mapping = {}
    for row in results:
        mapping[row['bsart']] = row['bstyp']
    
    cursor.close()
    return mapping


def fix_procurement_order_bstyp(mandt: str = '600', confirm: bool = False):
    """
    修复采购订单的 bstyp 字段
    
    Args:
        mandt: 客户端编号，默认为 '600'
        confirm: 是否确认执行，默认为 False（需要显式确认）
    """
    conn = get_postgres_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. 获取映射关系
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤1: 获取采购凭证类型到凭证类别的映射关系")
        logger.info(f"{'='*80}")
        
        mapping = get_bstyp_mapping(conn, mandt)
        
        if not mapping:
            logger.warning("未找到任何映射关系，将使用默认值 'F'")
            default_bstyp = 'F'
        else:
            logger.info(f"找到 {len(mapping)} 个映射关系:")
            for bsart, bstyp in sorted(mapping.items()):
                logger.info(f"  {bsart} -> {bstyp}")
            default_bstyp = 'F'
        
        # 2. 查找需要修复的订单
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤2: 查找需要修复的订单（mandt={mandt}, bstyp IS NULL）")
        logger.info(f"{'='*80}")
        
        find_query = """
            SELECT 
                ebeln,
                bsart,
                bstyp,
                bedat,
                lifnr
            FROM mm_ekko
            WHERE mandt = %s
              AND (bstyp IS NULL OR bstyp = '')
              AND (loekz IS NULL OR loekz != 'X')
            ORDER BY bedat DESC, ebeln DESC
        """
        
        cursor.execute(find_query, [mandt])
        orders_to_fix = cursor.fetchall()
        
        if not orders_to_fix:
            logger.info("✅ 没有需要修复的订单")
            return True
        
        logger.info(f"找到 {len(orders_to_fix)} 个需要修复的订单:")
        for order in orders_to_fix:
            bsart = order['bsart']
            expected_bstyp = mapping.get(bsart, default_bstyp) if bsart else default_bstyp
            logger.info(f"  订单: {order['ebeln']}, 类型: {bsart or 'NULL'}, "
                       f"当前类别: {order['bstyp'] or 'NULL'}, "
                       f"将设置为: {expected_bstyp}")
        
        # 3. 确认操作
        if not confirm:
            logger.warning(f"\n{'='*80}")
            logger.warning("⚠️  警告：此操作将更新采购订单的 bstyp 字段")
            logger.warning(f"   客户端: {mandt}")
            logger.warning(f"   需要修复的订单数: {len(orders_to_fix)}")
            logger.warning(f"{'='*80}")
            logger.warning("如需执行修复操作，请使用 --confirm 参数")
            return False
        
        # 4. 执行修复
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤3: 执行修复操作")
        logger.info(f"{'='*80}")
        
        updated_count = 0
        skipped_count = 0
        
        for order in orders_to_fix:
            ebeln = order['ebeln']
            bsart = order['bsart']
            
            # 确定要设置的 bstyp 值
            if bsart and bsart in mapping:
                target_bstyp = mapping[bsart]
            else:
                # 如果没有映射关系，使用默认值 'F'
                target_bstyp = default_bstyp
                if bsart:
                    logger.warning(f"  订单 {ebeln} 的类型 {bsart} 没有映射关系，使用默认值 {default_bstyp}")
            
            # 更新订单
            update_query = """
                UPDATE mm_ekko
                SET bstyp = %s
                WHERE mandt = %s
                  AND ebeln = %s
                  AND (bstyp IS NULL OR bstyp = '')
            """
            
            cursor.execute(update_query, [target_bstyp, mandt, ebeln])
            
            if cursor.rowcount > 0:
                updated_count += 1
                logger.info(f"  ✅ 订单 {ebeln}: {bsart or 'NULL'} -> {target_bstyp}")
            else:
                skipped_count += 1
                logger.warning(f"  ⚠️  订单 {ebeln}: 未更新（可能已被其他进程更新）")
        
        # 提交事务
        conn.commit()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"修复完成:")
        logger.info(f"   成功更新: {updated_count} 个订单")
        logger.info(f"   跳过: {skipped_count} 个订单")
        logger.info(f"{'='*80}")
        
        # 5. 验证修复结果
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤4: 验证修复结果")
        logger.info(f"{'='*80}")
        
        cursor.execute(find_query, [mandt])
        remaining = cursor.fetchall()
        
        if remaining:
            logger.warning(f"仍有 {len(remaining)} 个订单的 bstyp 为空:")
            for order in remaining[:5]:  # 只显示前5个
                logger.warning(f"  订单: {order['ebeln']}, 类型: {order['bsart']}")
            if len(remaining) > 5:
                logger.warning(f"  ... 还有 {len(remaining) - 5} 个订单")
        else:
            logger.info("✅ 所有订单的 bstyp 字段已修复")
        
        cursor.close()
        return True
        
    except Exception as e:
        logger.error(f"修复失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='修复采购订单的 bstyp（采购凭证类别）字段')
    parser.add_argument('--mandt', default='600', help='客户端编号，默认为 600')
    parser.add_argument('--confirm', action='store_true', help='确认执行修复操作')
    
    args = parser.parse_args()
    
    logger.info(f"开始修复采购订单的 bstyp 字段: mandt={args.mandt}")
    
    if not args.confirm:
        logger.warning("⚠️  未使用 --confirm 参数，将只进行检查，不会执行修复操作")
    
    success = fix_procurement_order_bstyp(args.mandt, args.confirm)
    
    if success:
        logger.info("\n✅ 操作完成！")
    else:
        logger.error("\n❌ 操作失败或已取消！")

