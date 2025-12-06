#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查物料的BOM数据
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'sinocst_erp'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

def main():
    matnr = sys.argv[1] if len(sys.argv) > 1 else 'M2002'
    mandt = sys.argv[2] if len(sys.argv) > 2 else '600'
    
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 检查所有工厂的BOM
    query = """
        SELECT 
            mast.matnr,
            mast.werks,
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
        ORDER BY mast.werks, mast.stlal
    """
    
    cursor.execute(query, [mandt, matnr])
    results = cursor.fetchall()
    
    if results:
        logger.info(f"找到 {len(results)} 条BOM记录:")
        for r in results:
            logger.info(f"  工厂: {r['werks']}, BOM编号: {r['stlnr']}, 用途: {r['stlan']}, 组件数: {r['component_count']}")
    else:
        logger.warning(f"物料 {matnr} 没有BOM记录")
        
        # 检查物料是否存在
        check_mat = "SELECT COUNT(*) as cnt FROM md_mara WHERE mandt = %s AND matnr = %s"
        cursor.execute(check_mat, [mandt, matnr])
        mat_exists = cursor.fetchone()['cnt']
        if mat_exists > 0:
            logger.info(f"物料 {matnr} 存在，但没有BOM")
        else:
            logger.warning(f"物料 {matnr} 不存在")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()

