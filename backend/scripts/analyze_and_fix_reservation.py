#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析生产订单组件清单缺失原因并修复
1. 查询生产订单信息
2. 检查预留编号对应的组件清单
3. 如果缺失，从BOM获取数据并补充到pp_resb表
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


def analyze_production_order(conn, aufnr: str, mandt: str = '600'):
    """分析生产订单的组件清单情况"""
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. 查询生产订单基本信息
        logger.info(f"查询生产订单 {aufnr} 的基本信息...")
        query_afko = """
            SELECT 
                afko.aufnr,
                afko.rsnum,
                afko.gamng,
                afko.gmein,
                afpo.matnr,
                aufk.werks,
                makt.maktx
            FROM pp_afko afko
            LEFT JOIN pp_afpo afpo ON afko.mandt = afpo.mandt 
                AND afko.aufnr = afpo.aufnr
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt 
                AND afko.aufnr = aufk.aufnr
            LEFT JOIN md_makt makt ON afpo.mandt = makt.mandt 
                AND LTRIM(afpo.matnr, '0') = LTRIM(makt.matnr, '0') 
                AND makt.spras = '1'
            WHERE afko.mandt = %s
            AND afko.aufnr = %s
            LIMIT 1
        """
        
        cursor.execute(query_afko, [mandt, aufnr])
        order_info = cursor.fetchone()
        
        if not order_info:
            logger.error(f"未找到生产订单 {aufnr}")
            cursor.close()
            return None
        
        logger.info(f"生产订单信息:")
        logger.info(f"  订单号: {order_info['aufnr']}")
        logger.info(f"  预留编号: {order_info['rsnum']}")
        logger.info(f"  物料号: {order_info['matnr']}")
        logger.info(f"  物料描述: {order_info['maktx']}")
        logger.info(f"  工厂: {order_info['werks']}")
        logger.info(f"  订单数量: {order_info['gamng']} {order_info['gmein']}")
        
        # 2. 检查预留编号对应的组件清单
        rsnum = order_info['rsnum']
        if not rsnum or rsnum == '0000000000':
            logger.warning(f"生产订单没有预留编号或预留编号为空")
            return {
                'order_info': order_info,
                'has_rsnum': False,
                'components': [],
                'missing_components': True
            }
        
        logger.info(f"查询预留编号 {rsnum} 对应的组件清单...")
        query_resb = """
            SELECT 
                resb.*,
                makt.maktx
            FROM pp_resb resb
            LEFT JOIN md_makt makt ON resb.mandt = makt.mandt 
                AND LTRIM(resb.matnr, '0') = LTRIM(makt.matnr, '0') 
                AND makt.spras = '1'
            WHERE resb.mandt = %s
            AND resb.rsnum = %s
            ORDER BY resb.rspos
        """
        
        cursor.execute(query_resb, [mandt, rsnum])
        components = cursor.fetchall()
        
        logger.info(f"找到 {len(components)} 个组件记录")
        
        # 统计有效组件和已删除组件
        valid_components = [c for c in components if c['xloek'] != 'X' and c['xloek'] != 'x']
        deleted_components = [c for c in components if c['xloek'] == 'X' or c['xloek'] == 'x']
        
        logger.info(f"  有效组件: {len(valid_components)} 个")
        logger.info(f"  已删除组件: {len(deleted_components)} 个")
        
        if deleted_components:
            logger.warning("已删除的组件列表:")
            for comp in deleted_components:
                logger.warning(f"  - {comp['matnr']} ({comp['maktx']}) - XLOEK={comp['xloek']}")
        
        if valid_components:
            logger.info("有效组件列表:")
            for comp in valid_components:
                logger.info(f"  - {comp['rspos']}: {comp['matnr']} ({comp['maktx']}) - 需求数量: {comp['bdmng']} {comp['meins']}")
        
        cursor.close()
        
        return {
            'order_info': order_info,
            'has_rsnum': True,
            'rsnum': rsnum,
            'components': components,
            'valid_components': valid_components,
            'deleted_components': deleted_components,
            'missing_components': len(valid_components) == 0
        }
        
    except Exception as e:
        logger.error(f"分析生产订单失败: {e}")
        import traceback
        traceback.print_exc()
        return None


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
                'prvbe': '',  # 生产供应区域
                'posnr': item['posnr'] or ''
            })
        
        logger.info(f"从BOM找到 {len(components)} 个组件")
        return components
        
    except Exception as e:
        logger.error(f"查询BOM组件失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def fix_reservation(conn, aufnr: str, mandt: str, rsnum: str, components: list) -> bool:
    """补充组件清单到pp_resb表"""
    try:
        cursor = conn.cursor()
        
        if not components:
            logger.warning("没有组件清单可补充")
            return False
        
        # 检查是否已有组件记录
        check_query = """
            SELECT COUNT(*) as count
            FROM pp_resb
            WHERE mandt = %s AND rsnum = %s
        """
        cursor.execute(check_query, [mandt, rsnum])
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            logger.warning(f"预留编号 {rsnum} 已存在 {existing_count} 条记录，将删除后重新创建")
            delete_query = "DELETE FROM pp_resb WHERE mandt = %s AND rsnum = %s"
            cursor.execute(delete_query, [mandt, rsnum])
        
        # 获取订单信息以获取工厂等信息
        order_query = """
            SELECT aufk.werks
            FROM pp_afko afko
            LEFT JOIN pp_aufk aufk ON afko.mandt = aufk.mandt AND afko.aufnr = aufk.aufnr
            WHERE afko.aufnr = %s AND afko.mandt = %s
            LIMIT 1
        """
        cursor.execute(order_query, [aufnr, mandt])
        order_result = cursor.fetchone()
        werks = order_result[0] if order_result else ''
        
        # 创建组件清单记录
        rspos = 1
        insert_count = 0
        
        insert_query = """
            INSERT INTO pp_resb (
                mandt, rsnum, rspos, rsart, bdart, rssta, xloek, xwaok, kzear, xfehl,
                matnr, werks, lgort, prvbe, charg, plpla, sobkz, bdter, bdmng, meins,
                shkzg, fmeng, enmng, enwrt, waers, erfmg, erfme, plnum, banfn, bnfpo,
                aufnr
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s
            )
        """
        
        for component in components:
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
                aufnr  # aufnr: 生产订单号
            )
            
            cursor.execute(insert_query, values)
            insert_count += 1
            rspos += 1
        
        conn.commit()
        logger.info(f"✓ 成功补充 {insert_count} 个组件到预留编号 {rsnum}")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"补充组件清单失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    aufnr = sys.argv[1] if len(sys.argv) > 1 else '800000000042'
    mandt = sys.argv[2] if len(sys.argv) > 2 else '600'
    
    logger.info(f"开始分析生产订单 {aufnr} (mandt={mandt})")
    
    conn = get_postgres_connection()
    if not conn:
        logger.error("无法连接到数据库")
        return
    
    try:
        # 分析生产订单
        analysis = analyze_production_order(conn, aufnr, mandt)
        
        if not analysis:
            logger.error("分析失败")
            return
        
        # 如果组件清单缺失，尝试从BOM补充
        if analysis['missing_components']:
            logger.warning("=" * 60)
            logger.warning("检测到组件清单缺失，尝试从BOM补充...")
            logger.warning("=" * 60)
            
            order_info = analysis['order_info']
            matnr = order_info['matnr']
            werks = order_info['werks']
            gamng = Decimal(str(order_info['gamng'] or 0))
            rsnum = analysis.get('rsnum')
            
            if not matnr or not werks:
                logger.error("生产订单缺少物料号或工厂信息，无法查询BOM")
                return
            
            if not rsnum or rsnum == '0000000000':
                logger.error("生产订单没有预留编号，无法补充组件清单")
                return
            
            # 从BOM获取组件
            bom_components = get_bom_components(conn, mandt, matnr, werks, gamng)
            
            if not bom_components:
                logger.error("无法从BOM获取组件清单，可能原因：")
                logger.error("  1) 物料没有BOM")
                logger.error("  2) BOM中没有有效组件")
                logger.error("  3) BOM数据未正确导入")
                return
            
            # 补充组件清单
            if fix_reservation(conn, aufnr, mandt, rsnum, bom_components):
                logger.info("=" * 60)
                logger.info("✓ 组件清单补充成功！")
                logger.info("=" * 60)
                
                # 重新分析验证
                logger.info("重新验证组件清单...")
                analysis_after = analyze_production_order(conn, aufnr, mandt)
                if analysis_after and len(analysis_after['valid_components']) > 0:
                    logger.info(f"✓ 验证成功：现在有 {len(analysis_after['valid_components'])} 个有效组件")
                else:
                    logger.warning("⚠ 验证失败：组件清单仍然为空")
            else:
                logger.error("组件清单补充失败")
        else:
            logger.info("=" * 60)
            logger.info("✓ 组件清单正常，无需修复")
            logger.info(f"  有效组件数量: {len(analysis['valid_components'])}")
            logger.info("=" * 60)
            
    finally:
        conn.close()
        logger.info("数据库连接已关闭")


if __name__ == '__main__':
    main()

