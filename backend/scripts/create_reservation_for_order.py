#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为生产订单创建预留编号和组件清单
1. 生成预留编号
2. 查询物料的BOM
3. 创建组件清单（pp_resb记录）
4. 更新订单的rsnum字段
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from decimal import Decimal

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


def generate_rsnum(conn, mandt: str) -> str:
    """生成预留编号（10位数字）"""
    try:
        cursor = conn.cursor()
        
        # 查询当前最大的rsnum（排除0000000000）
        query = """
            SELECT MAX(CAST(rsnum AS BIGINT)) as max_rsnum
            FROM pp_resb
            WHERE mandt = %s 
            AND rsnum != '0000000000'
            AND rsnum ~ '^[0-9]+$'
        """
        
        cursor.execute(query, [mandt])
        result = cursor.fetchone()
        
        if result and result[0]:
            max_rsnum = int(result[0])
            new_rsnum = max_rsnum + 1
        else:
            # 如果没有现有记录，从1开始
            new_rsnum = 1
        
        # 格式化为10位数字
        rsnum = f"{new_rsnum:010d}"
        
        # 确保不超过10位
        if len(rsnum) > 10:
            rsnum = rsnum[-10:]
        
        cursor.close()
        logger.info(f"生成预留编号: {rsnum}")
        return rsnum
        
    except Exception as e:
        logger.error(f"生成预留编号失败: {e}")
        # 如果失败，使用一个基于时间戳的编号
        import time
        timestamp = int(time.time()) % 10000000000
        return f"{timestamp:010d}"


def get_bom_components(conn, mandt: str, matnr: str, werks: str, gamng: Decimal) -> list:
    """查询物料的BOM组件清单"""
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 第一步：通过md_mast表查找BOM主数据
        logger.info(f"查询物料 {matnr} 在工厂 {werks} 的BOM主数据...")
        query_mast = """
            SELECT 
                mast.stlnr,
                mast.stlal,
                mast.stlan,
                (SELECT COUNT(*) 
                 FROM md_stpo stpo 
                 WHERE stpo.mandt = mast.mandt 
                 AND stpo.stlnr = mast.stlnr 
                 AND stpo.stlty = 'M'
                 AND (stpo.lkenz IS NULL OR stpo.lkenz != 'X')
                 AND stpo.idnrk IS NOT NULL
                 AND stpo.idnrk != '') as component_count
            FROM md_mast mast
            WHERE mast.mandt = %s
            AND mast.matnr = %s
            AND mast.werks = %s
            AND mast.stlan = '1'  -- BOM用途：1-生产
            ORDER BY component_count DESC, mast.stlal
            LIMIT 1
        """
        
        cursor.execute(query_mast, [mandt, matnr, werks])
        mast_result = cursor.fetchone()
        
        if not mast_result:
            logger.warning(f"未找到物料 {matnr} 在工厂 {werks} 的BOM主数据")
            cursor.close()
            return []
        
        stlnr = mast_result['stlnr']
        stlal = mast_result['stlal']
        component_count = mast_result['component_count'] or 0
        logger.info(f"找到BOM主数据: stlnr={stlnr}, stlal={stlal}, 组件数量={component_count}")
        
        # 第二步：通过md_stpo表查询BOM组件项目
        # 注意：md_stpo表中组件物料字段是idnrk，不是matnr
        query_stpo = """
            SELECT 
                stpo.idnrk as component_matnr,
                stpo.menge as component_menge,
                stpo.meins as component_meins,
                stpo.posnr as posnr,
                makt.maktx as component_maktx,
                marc.lgpro as lgort
            FROM md_stpo stpo
            LEFT JOIN md_makt makt ON stpo.mandt = makt.mandt 
                AND LTRIM(stpo.idnrk, '0') = LTRIM(makt.matnr, '0') 
                AND makt.spras = '1'
            LEFT JOIN md_marc marc ON stpo.mandt = marc.mandt 
                AND stpo.idnrk = marc.matnr 
                AND marc.werks = %s
            WHERE stpo.mandt = %s
            AND stpo.stlnr = %s
            AND stpo.stlty = 'M'  -- BOM类型：M-物料BOM
            AND (stpo.lkenz IS NULL OR stpo.lkenz != 'X')  -- 排除已删除的项目
            AND stpo.idnrk IS NOT NULL  -- 确保有组件物料号
            AND stpo.idnrk != ''  -- 排除空的组件物料号
            ORDER BY stpo.posnr
        """
        
        cursor.execute(query_stpo, [werks, mandt, stlnr])
        bom_items = cursor.fetchall()
        
        cursor.close()
        
        if not bom_items:
            logger.warning(f"BOM编号 {stlnr} 下没有找到组件项目")
            return []
        
        # 计算实际需求数量（根据订单数量）
        components = []
        for item in bom_items:
            component_menge = Decimal(str(item['component_menge'] or 0))
            # 需求数量 = BOM数量 * 订单数量
            bdmng = component_menge * gamng
            
            components.append({
                'matnr': item['component_matnr'] or '',
                'maktx': item['component_maktx'] or '',
                'menge': component_menge,
                'meins': item['component_meins'] or 'PC',
                'bdmng': bdmng,
                'lgort': item['lgort'] or '',
                'prvbe': '',  # 生产供应区域，如果md_marc没有此字段则留空
                'posnr': item['posnr'] or ''
            })
        
        logger.info(f"找到 {len(components)} 个BOM组件")
        return components
        
    except Exception as e:
        logger.error(f"查询BOM组件失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def create_reservation(conn, aufnr: str, mandt: str, rsnum: str, components: list) -> bool:
    """创建预留和组件清单"""
    # 如果之前有错误，需要重新开始事务
    try:
        conn.rollback()
    except:
        pass
    
    try:
        cursor = conn.cursor()
        
        # 如果没有组件，创建一个空的预留记录（至少更新订单的rsnum）
        if not components:
            logger.warning("没有组件清单，只更新订单的rsnum字段")
            update_afko = """
                UPDATE pp_afko
                SET rsnum = %s
                WHERE aufnr = %s AND mandt = %s
            """
            cursor.execute(update_afko, [rsnum, aufnr, mandt])
            conn.commit()
            logger.info(f"✓ 已更新订单 {aufnr} 的预留编号为 {rsnum}")
            return True
        
        # 创建组件清单记录
        rspos = 1
        insert_count = 0
        
        for component in components:
            insert_query = """
                INSERT INTO pp_resb (
                    mandt, rsnum, rspos, rsart, bdart, rssta, xloek, xwaok,
                    kzear, xfehl, matnr, werks, lgort, prvbe, charg, plpla,
                    sobkz, bdter, bdmng, meins, shkzg, fmeng, enmng, enwrt,
                    waers, erfmg, erfme, plnum, banfn, bnfpo, aufnr, vornr,
                    kostl, sgt_scat
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s
                )
            """
            
            # 获取订单信息以获取工厂
            order_query = """
                SELECT aufk.werks
                FROM pp_afko afko
                LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
                WHERE afko.aufnr = %s AND afko.mandt = %s
            """
            cursor.execute(order_query, [aufnr, mandt])
            order_info = cursor.fetchone()
            werks = order_info[0] if order_info else ''
            
            values = (
                mandt,  # mandt
                rsnum,  # rsnum
                f"{rspos:04d}",  # rspos (4位)
                'M',  # rsart: M-物料预留
                'AR',  # bdart: AR-生产订单预留
                '',  # rssta: 预定状态（空-未处理）
                '',  # xloek: 项目未删除
                'X',  # xwaok: 允许预订的货物移动
                '',  # kzear
                '',  # xfehl
                component['matnr'],  # matnr
                werks,  # werks
                component['lgort'] or '',  # lgort
                component.get('prvbe', '') or '',  # prvbe: 生产供应区域
                '',  # charg
                None,  # plpla
                '',  # sobkz
                '00000000',  # bdter: 需求日期
                component['bdmng'],  # bdmng: 需求数量
                component['meins'],  # meins: 单位
                'S',  # shkzg: S-借方（出库）
                '',  # fmeng: 数量不固定
                Decimal('0'),  # enmng: 已提货数量
                None,  # enwrt: 已提货价值
                None,  # waers: 货币码
                Decimal('0'),  # erfmg: 已录入数量
                component['meins'],  # erfme: 条目单位
                '',  # plnum
                '',  # banfn
                '00000',  # bnfpo
                aufnr,  # aufnr: 生产订单号
                '',  # vornr: 工序号
                '',  # kostl: 成本中心
                ''  # sgt_scat: 库存细分
            )
            
            cursor.execute(insert_query, values)
            insert_count += 1
            rspos += 1
        
        # 更新订单的rsnum字段
        update_afko = """
            UPDATE pp_afko
            SET rsnum = %s
            WHERE aufnr = %s AND mandt = %s
        """
        cursor.execute(update_afko, [rsnum, aufnr, mandt])
        
        conn.commit()
        logger.info(f"✓ 成功创建预留 {rsnum}，包含 {insert_count} 个组件")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"创建预留失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_reservation_for_order(aufnr: str, mandt: str = '600'):
    """为生产订单创建预留和组件清单"""
    conn = get_postgres_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. 查询订单信息
        logger.info(f"\n{'='*80}")
        logger.info(f"查询订单信息: aufnr={aufnr}, mandt={mandt}")
        logger.info(f"{'='*80}")
        
        query_order = """
            SELECT 
                afko.aufnr,
                afko.mandt,
                afko.rsnum,
                afko.gamng,
                afko.gmein,
                afpo.matnr,
                aufk.werks
            FROM pp_afko afko
            LEFT JOIN pp_afpo afpo ON afko.mandt = afpo.mandt AND afko.aufnr = afpo.aufnr
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            WHERE afko.aufnr = %s AND afko.mandt = %s
        """
        
        cursor.execute(query_order, [aufnr, mandt])
        order = cursor.fetchone()
        
        if not order:
            logger.error(f"未找到订单: aufnr={aufnr}, mandt={mandt}")
            return False
        
        logger.info(f"订单信息:")
        logger.info(f"  物料: {order['matnr']}")
        logger.info(f"  工厂: {order['werks']}")
        logger.info(f"  订单数量: {order['gamng']} {order['gmein']}")
        logger.info(f"  当前预留编号: {order['rsnum']}")
        
        # 检查是否已有预留编号
        if order['rsnum'] and order['rsnum'] != '0000000000':
            logger.warning(f"订单已有预留编号: {order['rsnum']}，将使用新生成的预留编号覆盖")
            # 非交互式模式：直接覆盖
        
        # 2. 生成预留编号
        logger.info(f"\n{'='*80}")
        logger.info("生成预留编号")
        logger.info(f"{'='*80}")
        
        rsnum = generate_rsnum(conn, mandt)
        
        # 3. 查询BOM组件
        logger.info(f"\n{'='*80}")
        logger.info(f"查询物料 {order['matnr']} 的BOM组件")
        logger.info(f"{'='*80}")
        
        components = get_bom_components(
            conn, 
            mandt, 
            order['matnr'], 
            order['werks'] or '', 
            Decimal(str(order['gamng'] or 0))
        )
        
        if components:
            logger.info("BOM组件清单:")
            for i, comp in enumerate(components, 1):
                logger.info(f"  {i}. {comp['matnr']} - {comp['maktx']}: {comp['bdmng']} {comp['meins']}")
        
        # 4. 创建预留和组件清单
        logger.info(f"\n{'='*80}")
        logger.info("创建预留和组件清单")
        logger.info(f"{'='*80}")
        
        success = create_reservation(conn, aufnr, mandt, rsnum, components)
        
        cursor.close()
        return success
        
    except Exception as e:
        logger.error(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    # 从命令行参数获取订单号
    aufnr = sys.argv[1] if len(sys.argv) > 1 else '800000000042'
    mandt = sys.argv[2] if len(sys.argv) > 2 else '600'
    
    logger.info(f"开始为生产订单创建预留: aufnr={aufnr}, mandt={mandt}")
    success = create_reservation_for_order(aufnr, mandt)
    
    if success:
        logger.info("\n✓ 创建预留完成！")
    else:
        logger.error("\n✗ 创建预留失败！")

