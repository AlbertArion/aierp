#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为物料M2002创建BOM数据
直接在md_mast和md_stpo表中创建数据
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from decimal import Decimal
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'sinocst_erp'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}


def generate_stlnr(conn, mandt: str) -> str:
    """生成BOM编号"""
    try:
        cursor = conn.cursor()
        # 查询当前最大的stlnr
        query = """
            SELECT MAX(CAST(SUBSTRING(stlnr FROM 3) AS BIGINT)) as max_num
            FROM md_mast
            WHERE mandt = %s 
            AND stlnr LIKE 'ST%'
            AND LENGTH(stlnr) = 16
        """
        cursor.execute(query, [mandt])
        result = cursor.fetchone()
        
        if result and result[0]:
            max_num = int(result[0])
            new_num = max_num + 1
        else:
            new_num = 1
        
        # 格式化为14位数字，加上ST前缀
        stlnr = f"ST{new_num:014d}"
        cursor.close()
        logger.info(f"生成BOM编号: {stlnr}")
        return stlnr
    except Exception as e:
        logger.error(f"生成BOM编号失败: {e}")
        # 使用时间戳生成
        timestamp = int(datetime.now().timestamp()) % 100000000000000
        return f"ST{timestamp:014d}"


def get_available_components(conn, mandt: str, werks: str) -> list:
    """获取可用的组件物料列表"""
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # 查询一些可用的物料作为组件
        query = """
            SELECT 
                mara.matnr,
                makt.maktx,
                mara.mtart,
                mara.meins
            FROM md_mara mara
            LEFT JOIN md_makt makt ON mara.mandt = makt.mandt 
                AND LTRIM(mara.matnr, '0') = LTRIM(makt.matnr, '0') 
                AND makt.spras = '1'
            WHERE mara.mandt = %s
            AND mara.matnr != 'M2002'  -- 排除自己
            AND mara.mtart IN ('HALB', 'ROH', 'FERT')  -- 半成品、原材料、成品
            ORDER BY mara.matnr
            LIMIT 10
        """
        cursor.execute(query, [mandt])
        components = cursor.fetchall()
        cursor.close()
        return components
    except Exception as e:
        logger.error(f"查询可用组件失败: {e}")
        return []


def create_bom(conn, mandt: str, matnr: str, werks: str, components: list) -> bool:
    """创建BOM数据"""
    try:
        cursor = conn.cursor()
        
        # 检查是否已存在BOM
        check_query = """
            SELECT COUNT(*) as cnt
            FROM md_mast
            WHERE mandt = %s AND matnr = %s AND werks = %s AND stlan = '1'
        """
        cursor.execute(check_query, [mandt, matnr, werks])
        existing = cursor.fetchone()[0]
        
        if existing > 0:
            logger.warning(f"物料 {matnr} 已存在BOM，将删除后重新创建")
            # 获取现有的stlnr
            get_stlnr_query = """
                SELECT stlnr FROM md_mast
                WHERE mandt = %s AND matnr = %s AND werks = %s AND stlan = '1'
                LIMIT 1
            """
            cursor.execute(get_stlnr_query, [mandt, matnr, werks])
            old_stlnr = cursor.fetchone()
            if old_stlnr:
                # 删除旧的BOM组件
                delete_stpo = "DELETE FROM md_stpo WHERE mandt = %s AND stlnr = %s"
                cursor.execute(delete_stpo, [mandt, old_stlnr[0]])
            # 删除旧的BOM主数据
            delete_mast = "DELETE FROM md_mast WHERE mandt = %s AND matnr = %s AND werks = %s AND stlan = '1'"
            cursor.execute(delete_mast, [mandt, matnr, werks])
        
        # 生成BOM编号
        stlnr = generate_stlnr(conn, mandt)
        stlal = '01'  # 备选物料清单：01
        
        # 创建BOM主数据
        today = datetime.now().strftime('%Y%m%d')
        insert_mast = """
            INSERT INTO md_mast (
                mandt, matnr, werks, stlan, stlnr, stlal,
                losvn, losbs, andat, annam, aedat, aenam
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """
        cursor.execute(insert_mast, [
            mandt, matnr, werks, '1', stlnr, stlal,
            Decimal('0'), Decimal('999999999'), today, 'SYSTEM', today, 'SYSTEM'
        ])
        logger.info(f"✓ 创建BOM主数据: stlnr={stlnr}")
        
        # 创建BOM组件
        if not components:
            logger.warning("没有提供组件列表，创建空的BOM")
            conn.commit()
            return True
        
        stlkn = '0001'  # BOM项目节点号
        posnr = 10  # 项目号（从10开始，步长10）
        
        for i, comp in enumerate(components):
            stpoz = f"{i+1:04d}"  # 内部计数器
            comp_matnr = comp['matnr']
            comp_menge = comp.get('menge', Decimal('1'))  # 默认数量1
            comp_meins = comp.get('meins', 'PC')  # 默认单位PC
            
            insert_stpo = """
                INSERT INTO md_stpo (
                    mandt, stlty, stlnr, stlkn, stpoz,
                    datuv, techv, lkenz, idnrk, pswrk,
                    postp, posnr, meins, menge, fmeng,
                    andat, annam, aedat, aenam
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """
            cursor.execute(insert_stpo, [
                mandt, 'M', stlnr, stlkn, stpoz,  # M-物料BOM
                today, '', '', comp_matnr, werks,  # 组件物料号，工厂
                'L', f"{posnr:04d}", comp_meins, comp_menge, '',  # L-项目类别，项目号，单位，数量
                today, 'SYSTEM', today, 'SYSTEM'
            ])
            logger.info(f"  - 组件 {i+1}: {comp_matnr} ({comp.get('maktx', '')}) - {comp_menge} {comp_meins}")
            posnr += 10
        
        conn.commit()
        logger.info(f"✓ 成功创建BOM，包含 {len(components)} 个组件")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"创建BOM失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    mandt = sys.argv[1] if len(sys.argv) > 1 else '600'
    matnr = sys.argv[2] if len(sys.argv) > 2 else 'M2002'
    werks = sys.argv[3] if len(sys.argv) > 3 else '1001'
    
    logger.info(f"为物料 {matnr} 创建BOM (mandt={mandt}, werks={werks})")
    
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    
    try:
        # 获取可用组件
        available_components = get_available_components(conn, mandt, werks)
        
        if not available_components:
            logger.error("没有找到可用的组件物料")
            return
        
        logger.info(f"找到 {len(available_components)} 个可用组件物料")
        
        # 为M2002（高级变速箱）选择合理的组件
        # 选择前几个物料作为组件（可以根据实际业务需求调整）
        selected_components = []
        for i, comp in enumerate(available_components[:5]):  # 选择前5个
            selected_components.append({
                'matnr': comp['matnr'],
                'maktx': comp['maktx'],
                'menge': Decimal('1') if i == 0 else Decimal('2'),  # 第一个组件数量1，其他2
                'meins': comp['meins'] or 'PC'
            })
        
        logger.info("选择的组件:")
        for comp in selected_components:
            logger.info(f"  - {comp['matnr']} ({comp['maktx']}) - {comp['menge']} {comp['meins']}")
        
        # 创建BOM
        if create_bom(conn, mandt, matnr, werks, selected_components):
            logger.info("=" * 60)
            logger.info("✓ BOM创建成功！")
            logger.info("=" * 60)
        else:
            logger.error("BOM创建失败")
            
    finally:
        conn.close()


if __name__ == '__main__':
    main()

