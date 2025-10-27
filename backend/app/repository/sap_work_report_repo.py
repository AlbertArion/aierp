#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAP报工数据Repository
提供SAP报工数据的数据库操作接口
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from app.db.sqlite_db import SQLiteCollection

logger = logging.getLogger(__name__)

class SAPWorkReportRepository:
    """SAP报工数据Repository"""
    
    def __init__(self, db):
        self.db = db
    
    async def search_work_reports(self, 
                                keyword: Optional[str] = None,
                                aufnr: Optional[str] = None,
                                matnr: Optional[str] = None,
                                werks: Optional[str] = None,
                                start_date: Optional[date] = None,
                                end_date: Optional[date] = None,
                                page: int = 1,
                                size: int = 20) -> Dict[str, Any]:
        """搜索报工数据"""
        try:
            # 构建查询条件
            filter_dict = {}
            
            if aufnr:
                filter_dict['aufnr'] = aufnr
            if matnr:
                filter_dict['matnr'] = matnr
            if werks:
                filter_dict['werks'] = werks
            if start_date:
                filter_dict['erdat'] = {'$gte': start_date.isoformat()}
            if end_date:
                filter_dict['erdat'] = {'$lte': end_date.isoformat()}
            
            # 关键字搜索
            if keyword:
                # 在多个字段中搜索关键字
                keyword_filter = {
                    '$or': [
                        {'aufnr': {'$regex': keyword}},
                        {'ktext': {'$regex': keyword}},
                        {'ltext': {'$regex': keyword}},
                        {'ernam': {'$regex': keyword}},
                        {'aenam': {'$regex': keyword}}
                    ]
                }
                if filter_dict:
                    filter_dict = {'$and': [filter_dict, keyword_filter]}
                else:
                    filter_dict = keyword_filter
            
            # 查询AUFK表（订单主数据）
            aufk_collection = self.db.get_collection('aufk')
            aufk_records = aufk_collection.find(filter_dict)
            
            # 分页
            total = len(aufk_records)
            start_index = (page - 1) * size
            end_index = start_index + size
            records = aufk_records[start_index:end_index]
            
            # 关联查询其他表的数据
            enriched_records = []
            for record in records:
                enriched_record = await self._enrich_record(record)
                enriched_records.append(enriched_record)
            
            return {
                'records': enriched_records,
                'total': total,
                'page': page,
                'size': size,
                'pages': (total + size - 1) // size
            }
            
        except Exception as e:
            logger.error(f"搜索报工数据失败: {e}")
            raise
    
    async def _enrich_record(self, aufk_record: Dict[str, Any]) -> Dict[str, Any]:
        """丰富记录数据，关联其他表"""
        try:
            aufnr = aufk_record.get('aufnr')
            if not aufnr:
                return aufk_record
            
            # 查询AFKO表
            afko_collection = self.db.get_collection('afko')
            afko_record = afko_collection.find_one({'aufnr': aufnr})
            if afko_record:
                aufk_record.update({
                    'gltrp': afko_record.get('gltrp'),
                    'gstrp': afko_record.get('gstrp'),
                    'gamng': afko_record.get('gamng'),
                    'gmein': afko_record.get('gmein')
                })
            
            # 查询AFPO表
            afpo_collection = self.db.get_collection('afpo')
            afpo_records = list(afpo_collection.find({'aufnr': aufnr}))
            aufk_record['afpo_items'] = afpo_records
            
            # 查询AFVC表 - 暂时跳过，因为需要更复杂的关联逻辑
            aufk_record['afvc_items'] = []
            
            # 查询AFVV表 - 暂时跳过，因为需要更复杂的关联逻辑
            aufk_record['afvv_items'] = []
            
            # 查询JEST表
            jest_collection = self.db.get_collection('jest')
            jest_records = jest_collection.find({'objnr': aufk_record.get('objnr')})
            aufk_record['jest_items'] = list(jest_records)
            
            # 查询MAKT表（物料描述）
            if aufk_record['afpo_items']:
                matnr_list = [item.get('matnr') for item in aufk_record['afpo_items'] if item.get('matnr')]
                if matnr_list:
                    makt_collection = self.db.get_collection('makt')
                    makt_records = makt_collection.find({'matnr': {'$in': matnr_list}})
                    aufk_record['makt_items'] = list(makt_records)
            
            return aufk_record
            
        except Exception as e:
            logger.warning(f"丰富记录数据失败: {e}")
            return aufk_record
    
    async def get_order_details(self, aufnr: str) -> Optional[Dict[str, Any]]:
        """获取订单详细信息"""
        try:
            # 查询AUFK表
            aufk_collection = self.db.get_collection('aufk')
            aufk_record = aufk_collection.find_one({'aufnr': aufnr})
            
            if not aufk_record:
                return None
            
            # 丰富记录数据
            enriched_record = await self._enrich_record(aufk_record)
            return enriched_record
            
        except Exception as e:
            logger.error(f"获取订单详细信息失败: {e}")
            raise
    
    async def get_material_info(self, matnr: str) -> Optional[Dict[str, Any]]:
        """获取物料信息"""
        try:
            makt_collection = self.db.get_collection('makt')
            makt_record = makt_collection.find_one({'matnr': matnr})
            
            if not makt_record:
                return None
            
            return makt_record
            
        except Exception as e:
            logger.error(f"获取物料信息失败: {e}")
            raise
    
    async def get_work_center_info(self, arbid: str) -> Optional[Dict[str, Any]]:
        """获取工作中心信息"""
        try:
            # 这里可以扩展查询工作中心表
            # 目前返回基本信息
            return {
                'arbid': arbid,
                'description': f"工作中心 {arbid}"
            }
            
        except Exception as e:
            logger.error(f"获取工作中心信息失败: {e}")
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
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
                    logger.warning(f"获取 {table_name} 表统计信息失败: {e}")
                    stats[table_name] = 0
            
            # 计算总记录数
            stats['total_records'] = sum(stats.values())
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    async def get_recent_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的订单"""
        try:
            aufk_collection = self.db.get_collection('aufk')
            
            # 按创建日期排序，获取最近的订单
            records = aufk_collection.find({})
            records = sorted(records, key=lambda x: x.get('erdat', ''), reverse=True)
            
            # 限制数量
            records = records[:limit]
            
            # 丰富记录数据
            enriched_records = []
            for record in records:
                enriched_record = await self._enrich_record(record)
                enriched_records.append(enriched_record)
            
            return enriched_records
            
        except Exception as e:
            logger.error(f"获取最近订单失败: {e}")
            raise
    
    async def get_orders_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取订单"""
        try:
            # 查询JEST表获取状态信息
            jest_collection = self.db.get_collection('jest')
            jest_records = jest_collection.find({'stat': status})
            
            orders = []
            for jest_record in jest_records:
                objnr = jest_record.get('objnr')
                if objnr:
                    # 查询AUFK表
                    aufk_collection = self.db.get_collection('aufk')
                    aufk_record = aufk_collection.find_one({'objnr': objnr})
                    
                    if aufk_record:
                        enriched_record = await self._enrich_record(aufk_record)
                        orders.append(enriched_record)
            
            return orders
            
        except Exception as e:
            logger.error(f"根据状态获取订单失败: {e}")
            raise
