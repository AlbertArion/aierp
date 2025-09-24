#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试数据库脚本
检查内存数据库中的数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongo import get_db

def debug_database():
    """调试数据库"""
    print("🔍 调试数据库...")
    
    try:
        db = get_db()
        print(f"数据库类型: {type(db).__name__}")
        
        if hasattr(db, 'work_reports'):
            work_reports = db.work_reports
            print(f"报工集合类型: {type(work_reports).__name__}")
            print(f"报工集合数据: {work_reports.data}")
            print(f"报工记录数量: {len(work_reports.data)}")
            
            if work_reports.data:
                print("第一条记录:")
                print(work_reports.data[0])
        else:
            print("没有找到work_reports集合")
            
    except Exception as e:
        print(f"调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_database()
