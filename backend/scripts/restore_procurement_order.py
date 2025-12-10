#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
恢复被逻辑删除的采购订单
将订单的 loekz 字段从 'X' 设置为 NULL，使订单可以正常查询
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


def restore_procurement_order(ebeln: str, mandt: str = '600', confirm: bool = False):
    """
    恢复被逻辑删除的采购订单
    
    Args:
        ebeln: 采购订单编号
        mandt: 客户端编号，默认为 '600'
        confirm: 是否确认执行，默认为 False（需要显式确认）
    """
    conn = get_postgres_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. 检查订单是否存在
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤1: 检查订单 {ebeln} (mandt={mandt}) 是否存在")
        logger.info(f"{'='*80}")
        
        check_query = """
            SELECT 
                mandt,
                ebeln,
                bsart,
                loekz,
                bedat,
                lifnr,
                ekorg,
                CASE 
                    WHEN loekz = 'X' THEN '已删除'
                    WHEN loekz IS NULL OR loekz = '' THEN '未删除'
                    ELSE '其他状态'
                END AS delete_status
            FROM mm_ekko
            WHERE ebeln = %s AND mandt = %s
        """
        
        cursor.execute(check_query, [ebeln, mandt])
        order = cursor.fetchone()
        
        if not order:
            logger.error(f"❌ 订单 {ebeln} (mandt={mandt}) 不存在")
            return False
        
        logger.info("订单信息:")
        for key, value in order.items():
            logger.info(f"  {key}: {value}")
        
        # 2. 检查订单是否已被删除
        if order['loekz'] != 'X':
            logger.warning(f"⚠️  订单 {ebeln} 未被删除（loekz = {order['loekz']}），无需恢复")
            return True
        
        # 3. 检查行项目
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤2: 检查订单的行项目")
        logger.info(f"{'='*80}")
        
        line_item_query = """
            SELECT 
                ebelp,
                matnr,
                loekz,
                menge,
                meins
            FROM mm_ekpo
            WHERE ebeln = %s AND mandt = %s
            ORDER BY ebelp
        """
        
        cursor.execute(line_item_query, [ebeln, mandt])
        line_items = cursor.fetchall()
        
        logger.info(f"找到 {len(line_items)} 个行项目:")
        for item in line_items:
            logger.info(f"  行项目 {item['ebelp']}: 物料 {item['matnr']}, 数量 {item['menge']} {item['meins']}, "
                       f"删除状态: {'已删除' if item['loekz'] == 'X' else '未删除'}")
        
        # 4. 确认操作
        if not confirm:
            logger.warning(f"\n{'='*80}")
            logger.warning("⚠️  警告：此操作将恢复订单，使其可以正常查询")
            logger.warning(f"   订单编号: {ebeln}")
            logger.warning(f"   客户端: {mandt}")
            logger.warning(f"   订单类型: {order['bsart']}")
            logger.warning(f"   供应商: {order['lifnr']}")
            logger.warning(f"   行项目数: {len(line_items)}")
            logger.warning(f"{'='*80}")
            logger.warning("如需执行恢复操作，请使用 --confirm 参数")
            return False
        
        # 5. 执行恢复操作
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤3: 恢复订单 {ebeln}")
        logger.info(f"{'='*80}")
        
        # 恢复订单头表
        restore_ekko_query = """
            UPDATE mm_ekko
            SET loekz = NULL
            WHERE ebeln = %s AND mandt = %s AND loekz = 'X'
        """
        
        cursor.execute(restore_ekko_query, [ebeln, mandt])
        ekko_affected = cursor.rowcount
        
        # 恢复行项目（如果有被删除的）
        restore_ekpo_query = """
            UPDATE mm_ekpo
            SET loekz = NULL
            WHERE ebeln = %s AND mandt = %s AND loekz = 'X'
        """
        
        cursor.execute(restore_ekpo_query, [ebeln, mandt])
        ekpo_affected = cursor.rowcount
        
        # 提交事务
        conn.commit()
        
        logger.info(f"✅ 恢复完成:")
        logger.info(f"   订单头表: 恢复了 {ekko_affected} 条记录")
        logger.info(f"   行项目表: 恢复了 {ekpo_affected} 条记录")
        
        # 6. 验证恢复结果
        logger.info(f"\n{'='*80}")
        logger.info(f"步骤4: 验证恢复结果")
        logger.info(f"{'='*80}")
        
        cursor.execute(check_query, [ebeln, mandt])
        restored_order = cursor.fetchone()
        
        if restored_order and (restored_order['loekz'] is None or restored_order['loekz'] != 'X'):
            logger.info("✅ 验证成功：订单已恢复，可以正常查询")
            logger.info("订单当前状态:")
            for key, value in restored_order.items():
                logger.info(f"  {key}: {value}")
        else:
            logger.error("❌ 验证失败：订单恢复可能未成功")
            return False
        
        cursor.close()
        return True
        
    except Exception as e:
        logger.error(f"恢复订单失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='恢复被逻辑删除的采购订单')
    parser.add_argument('ebeln', help='采购订单编号')
    parser.add_argument('--mandt', default='600', help='客户端编号，默认为 600')
    parser.add_argument('--confirm', action='store_true', help='确认执行恢复操作')
    
    args = parser.parse_args()
    
    logger.info(f"开始恢复采购订单: ebeln={args.ebeln}, mandt={args.mandt}")
    
    if not args.confirm:
        logger.warning("⚠️  未使用 --confirm 参数，将只进行检查，不会执行恢复操作")
    
    success = restore_procurement_order(args.ebeln, args.mandt, args.confirm)
    
    if success:
        logger.info("\n✅ 操作完成！")
    else:
        logger.error("\n❌ 操作失败或已取消！")

