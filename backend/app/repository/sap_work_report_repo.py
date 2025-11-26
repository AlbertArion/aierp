#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAP报工数据Repository
提供SAP报工数据的数据库操作接口
现在使用PostgreSQL作为数据源（通过Java项目的API）
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from app.db.sqlite_db import SQLiteCollection
from app.services.pp_service import PPService

logger = logging.getLogger(__name__)

class SAPWorkReportRepository:
    """SAP报工数据Repository - 使用PostgreSQL数据源"""
    
    def __init__(self, db=None):
        """
        初始化Repository
        
        Args:
            db: SQLite数据库连接（保留以支持其他方法，但不再用于主要查询）
        """
        self.db = db
        self.pp_service = PPService()
    
    def set_token(self, token: str):
        """设置认证token（用于调用Java项目API）"""
        self.pp_service.set_token(token)
    
    async def search_work_reports(self, 
                                keyword: Optional[str] = None,
                                aufnr: Optional[str] = None,
                                matnr: Optional[str] = None,
                                werks: Optional[str] = None,
                                start_date: Optional[date] = None,
                                end_date: Optional[date] = None,
                                page: int = 1,
                                size: int = 20) -> Dict[str, Any]:
        """搜索报工数据 - 使用PostgreSQL数据源"""
        try:
            # 构建查询参数（用于Java项目的listV2接口）
            params = {
                'current': page,
                'size': size
            }
            
            # 添加查询条件
            if aufnr:
                params['aufnr'] = aufnr
            if matnr:
                params['matnr'] = matnr
            if werks:
                params['werks'] = werks
            if start_date:
                # Java项目可能使用不同的日期格式，这里使用ISO格式
                params['gstrp'] = start_date.strftime('%Y%m%d')
            if end_date:
                params['gltrp'] = end_date.strftime('%Y%m%d')
            
            # 关键字搜索（如果Java项目支持）
            if keyword:
                params['aufnr'] = keyword  # 或者使用专门的keyword参数，取决于Java接口
            
            # 调用Java项目的生产订单列表接口
            logger.info(f"查询报工数据: 调用PostgreSQL数据源, params={params}")
            result = await self.pp_service.get_order_list(params)
            
            # 解析Java项目的响应格式
            # 期望格式: {"code": 200, "success": true, "data": {"records": [...], "total": 100, ...}}
            if result and result.get('code') == 200:
                data = result.get('data', {})
                
                if isinstance(data, dict):
                    records = data.get('records', [])
                    total = data.get('total', len(records))
                    
                    # 转换数据格式以匹配原有接口
                    enriched_records = []
                    for record in records:
                        # 转换Java项目返回的数据格式到报工一览表需要的格式
                        enriched_record = self._convert_to_work_report_format(record)
                        enriched_records.append(enriched_record)
                    
                    # 计算总页数
                    pages = (total + size - 1) // size if total > 0 else 0
                    
                    return {
                        'records': enriched_records,
                        'total': total,
                        'page': page,
                        'size': size,
                        'pages': pages
                    }
                else:
                    # 如果返回的不是分页数据，直接返回
                    logger.warning(f"返回的数据格式不符合预期: {type(data)}")
                    return {
                        'records': [],
                        'total': 0,
                        'page': page,
                        'size': size,
                        'pages': 0
                    }
            else:
                error_msg = result.get('msg', '查询失败') if result else '响应为空'
                logger.error(f"查询报工数据失败: {error_msg}")
                return {
                    'records': [],
                    'total': 0,
                    'page': page,
                    'size': size,
                    'pages': 0
                }
            
        except Exception as e:
            logger.error(f"搜索报工数据失败: {e}", exc_info=True)
            raise
    
    def _convert_to_work_report_format(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        将Java项目返回的生产订单数据格式转换为报工一览表需要的格式
        
        Args:
            record: Java项目返回的生产订单记录
            
        Returns:
            转换后的记录格式
        """
        # Java项目返回的数据可能包含以下字段：
        # aufnr, matnr, maktx, auart, werks, gamng, gmein, stat, statL等
        
        # 提取订单类型（auart）
        auart = record.get('auart', '')
        
        # 提取状态信息
        stat = record.get('stat', '')
        statL = record.get('statL', [])
        
        # 转换后的记录格式（兼容原有格式）
        converted = {
            'aufnr': record.get('aufnr', ''),
            'matnr': record.get('matnr', ''),
            'maktx': record.get('maktx', ''),  # 物料描述
            'auart': auart,  # 订单类型
            'werks': record.get('werks', ''),
            'gamng': record.get('gamng'),  # 订单数量
            'gmein': record.get('gmein', ''),  # 单位
            'gstrp': record.get('gstrp', ''),  # 开始日期
            'gltrp': record.get('gltrp', ''),  # 完成日期
            'stat': stat,  # 状态
            'statL': statL,  # 状态列表
            'kdauf': record.get('kdauf', ''),  # 销售订单号
            'kdpos': record.get('kdpos', ''),  # 销售订单行项目号
            'objnr': record.get('objnr', ''),
            # 保留原始记录的所有字段
            **record
        }
        
        return converted
    
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
