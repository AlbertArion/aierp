#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAP报工数据导入脚本
用于将Excel文件中的SAP报工数据导入到SQLite数据库中
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.sqlite_db import get_sqlite_db
from app.utils.parsers.sap_excel_parser import SAPExcelParser

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sap_import.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class SAPDataImporter:
    """SAP报工数据导入器"""
    
    def __init__(self, excel_file_path: str):
        self.excel_file_path = excel_file_path
        self.db = get_sqlite_db()
        self.parser = SAPExcelParser(excel_file_path)
        
    async def import_all_data(self) -> Dict[str, int]:
        """导入所有数据"""
        try:
            logger.info("🚀 开始导入SAP报工数据...")
            
            # 解析Excel文件
            logger.info("📊 正在解析Excel文件...")
            sheets_data = self.parser.parse_all_sheets()
            
            # 导入各个表的数据
            import_results = {}
            
            for sheet_name, records in sheets_data.items():
                logger.info(f"📝 正在导入 {sheet_name} 表数据...")
                count = await self._import_table_data(sheet_name.lower(), records)
                import_results[sheet_name] = count
                logger.info(f"✅ {sheet_name} 表导入完成，共 {count} 条记录")
            
            logger.info("🎉 SAP报工数据导入完成！")
            return import_results
            
        except Exception as e:
            logger.error(f"❌ 导入数据失败: {e}")
            raise
    
    async def _import_table_data(self, table_name: str, records: List[Dict[str, Any]]) -> int:
        """导入单个表的数据"""
        try:
            collection = self.db.get_collection(table_name)
            
            # 清空现有数据（可选）
            # await self._clear_table_data(table_name)
            
            # 批量插入数据
            if records:
                result = collection.insert_many(records)
                return len(result.inserted_ids)
            else:
                logger.warning(f"⚠️ {table_name} 表没有数据需要导入")
                return 0
                
        except Exception as e:
            logger.error(f"❌ 导入 {table_name} 表数据失败: {e}")
            raise
    
    async def _clear_table_data(self, table_name: str):
        """清空表数据"""
        try:
            collection = self.db.get_collection(table_name)
            # 删除所有数据
            cursor = self.db.conn.cursor()
            cursor.execute(f"DELETE FROM {table_name}")
            self.db.conn.commit()
            logger.info(f"🗑️ 已清空 {table_name} 表数据")
        except Exception as e:
            logger.warning(f"⚠️ 清空 {table_name} 表数据失败: {e}")
    
    async def get_import_statistics(self) -> Dict[str, Any]:
        """获取导入统计信息"""
        try:
            stats = {}
            
            # 统计各个表的记录数
            tables = ['afko', 'afpo', 'afvc', 'afvv', 'aufk', 'jest', 'makt']
            
            for table_name in tables:
                try:
                    collection = self.db.get_collection(table_name)
                    count = collection.count_documents({})
                    stats[table_name] = count
                except Exception as e:
                    logger.warning(f"⚠️ 获取 {table_name} 表统计信息失败: {e}")
                    stats[table_name] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}

async def main():
    """主函数"""
    print("=" * 60)
    print("🎯 SAP报工数据导入工具")
    print("=" * 60)
    
    # Excel文件路径
    excel_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "workreport", "报工一览表所需数据.xlsx"
    )
    
    if not os.path.exists(excel_file_path):
        print(f"❌ Excel文件不存在: {excel_file_path}")
        return
    
    try:
        # 创建导入器
        importer = SAPDataImporter(excel_file_path)
        
        # 导入数据
        import_results = await importer.import_all_data()
        
        # 显示导入结果
        print("\n📊 导入结果统计:")
        print("-" * 40)
        total_records = 0
        for sheet_name, count in import_results.items():
            print(f"  {sheet_name:8}: {count:6} 条记录")
            total_records += count
        
        print("-" * 40)
        print(f"  总计    : {total_records:6} 条记录")
        
        # 获取数据库统计信息
        print("\n📈 数据库统计信息:")
        print("-" * 40)
        stats = await importer.get_import_statistics()
        for table_name, count in stats.items():
            print(f"  {table_name:8}: {count:6} 条记录")
        
        print("\n✅ 数据导入完成！")
        print("🌐 现在可以访问前端页面查看SAP报工数据")
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        logger.error(f"导入失败: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
