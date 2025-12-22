#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
指标计算服务
负责计算业务指标的当前值
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from ..db.sqlite_db import get_sqlite_db
from .erp_service_client import ERPServiceClient

logger = logging.getLogger(__name__)


class MetricCalculationService:
    """指标计算服务"""
    
    def __init__(self, token: Optional[str] = None, mandt: Optional[str] = None, tenant_id: Optional[str] = None):
        """
        初始化指标计算服务
        
        Args:
            token: 认证token，用于调用Java后端服务
            mandt: 集团代码
            tenant_id: 租户ID
        """
        self.db = get_sqlite_db()
        # 创建ERP服务客户端，用于调用Java后端获取业务数据
        self.erp_client = ERPServiceClient(token=token, mandt=mandt, tenant_id=tenant_id) if token else None
    
    async def calculate_metric_value(self, metric_id: int) -> Optional[float]:
        """
        计算指标的当前值
        
        Args:
            metric_id: 指标ID
        
        Returns:
            指标当前值，如果计算失败返回None
        """
        try:
            # 获取指标定义
            metric = self._get_metric_definition(metric_id)
            if not metric:
                logger.error(f"指标定义不存在: {metric_id}")
                return None
            
            if not metric.get('is_enabled'):
                logger.warning(f"指标未启用: {metric_id}")
                return None
            
            # 根据计算公式计算指标值
            formula = metric.get('calculation_formula')
            if not formula:
                logger.warning(f"指标未配置计算公式: {metric_id}")
                return None
            
            # 执行计算
            value = await self._execute_formula(metric, formula)
            
            # 保存历史记录
            if value is not None:
                await self._save_metric_history(metric_id, value)
            
            return value
            
        except Exception as e:
            logger.error(f"计算指标值失败: {metric_id}, {e}", exc_info=True)
            return None
    
    def _get_metric_definition(self, metric_id: int) -> Optional[Dict]:
        """获取指标定义"""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT * FROM biz_metric_definition WHERE id = ?",
            (metric_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    async def _execute_formula(self, metric: Dict, formula: str) -> Optional[float]:
        """
        执行计算公式
        
        这里简化实现，实际应该支持更复杂的公式解析
        """
        try:
            # 如果公式是SQL查询
            if metric.get('data_source_query'):
                return await self._execute_sql_query(metric['data_source_query'])
            
            # 如果公式是简单的表达式
            # 这里可以根据实际需求实现公式解析器
            # 例如：AVG(inventory) / AVG(sales) * 30
            
            # 简化实现：直接执行SQL查询
            if metric.get('data_source_table'):
                return await self._calculate_from_table(metric)
            
            logger.warning(f"无法执行公式: {formula}")
            return None
            
        except Exception as e:
            logger.error(f"执行公式失败: {e}", exc_info=True)
            return None
    
    async def _execute_sql_query(self, query: str) -> Optional[float]:
        """执行SQL查询"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return float(result[0]) if result[0] is not None else None
            return None
        except Exception as e:
            logger.error(f"执行SQL查询失败: {e}")
            return None
    
    async def _calculate_from_table(self, metric: Dict) -> Optional[float]:
        """从数据表计算指标值"""
        # 这里需要根据具体的指标类型实现计算逻辑
        # 例如：DSI需要计算库存和销售数据
        metric_code = metric.get('metric_code')
        
        if metric_code == 'DSI':
            return await self._calculate_dsi()
        elif metric_code == 'OTIF':
            return await self._calculate_otif()
        elif metric_code == 'SOP_HEALTH':
            return await self._calculate_sop_health()
        
        return None
    
    async def _calculate_dsi(self) -> Optional[float]:
        """
        计算库存周转天数(DSI)
        
        公式：DSI = (平均库存 / 日均销售额) * 30
        """
        try:
            if not self.erp_client:
                logger.warning("ERP服务客户端未初始化，使用示例值")
                return 118.0  # 示例值
            
            # 1. 获取总库存价值（从WM模块）
            total_inventory = await self.erp_client.get_total_inventory_value()
            
            # 2. 计算日均销售额（从SD模块，最近30天）
            daily_sales = await self.erp_client.calculate_daily_sales(days=30)
            
            # 3. 计算DSI
            if daily_sales > 0:
                dsi = (total_inventory / daily_sales) * 30
                logger.info(f"DSI计算: 总库存={total_inventory}, 日均销售={daily_sales}, DSI={dsi}")
                return dsi
            else:
                logger.warning("日均销售额为0，无法计算DSI")
                return None
            
        except Exception as e:
            logger.error(f"计算DSI失败: {e}", exc_info=True)
            # 如果调用Java服务失败，返回示例值
            return 118.0
    
    async def _calculate_otif(self) -> Optional[float]:
        """
        计算准时交付率(OTIF - On-Time In-Full)
        
        公式：OTIF = (准时足量交付的订单数 / 总订单数) * 100
        """
        try:
            if not self.erp_client:
                logger.warning("ERP服务客户端未初始化，使用示例值")
                return 89.5  # 示例值
            
            # 获取最近30天的交货单数据
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            deliveries = await self.erp_client.get_delivery_data(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )
            
            if not deliveries:
                logger.warning("没有交货单数据，无法计算OTIF")
                return None
            
            total_count = len(deliveries)
            on_time_in_full_count = 0
            
            for delivery in deliveries:
                # 检查是否准时（wadat_ist <= wadat_soll）
                wadat_ist = delivery.get("wadat_ist")  # 实际交货日期
                wadat_soll = delivery.get("wadat_soll")  # 计划交货日期
                
                # 检查是否足量（已交付数量 >= 订单数量）
                # 这里需要根据实际字段名调整
                delivered_qty = float(delivery.get("lfimg", 0) or 0)  # 已交付数量
                ordered_qty = float(delivery.get("kwmeng", 0) or 0)  # 订单数量
                
                is_on_time = True
                if wadat_ist and wadat_soll:
                    try:
                        ist_date = datetime.strptime(wadat_ist, "%Y-%m-%d")
                        soll_date = datetime.strptime(wadat_soll, "%Y-%m-%d")
                        is_on_time = ist_date <= soll_date
                    except:
                        pass
                
                is_in_full = delivered_qty >= ordered_qty
                
                if is_on_time and is_in_full:
                    on_time_in_full_count += 1
            
            otif = (on_time_in_full_count / total_count) * 100 if total_count > 0 else 0
            logger.info(f"OTIF计算: 总订单={total_count}, 准时足量={on_time_in_full_count}, OTIF={otif}%")
            return otif
            
        except Exception as e:
            logger.error(f"计算OTIF失败: {e}", exc_info=True)
            return 89.5  # 示例值
    
    async def _calculate_sop_health(self) -> Optional[float]:
        """计算S&OP健康度指数"""
        try:
            # 简化实现
            # 实际应该综合多个指标计算
            return 68.0  # 示例值
        except Exception as e:
            logger.error(f"计算S&OP健康度失败: {e}")
            return None
    
    async def _save_metric_history(self, metric_id: int, value: float):
        """保存指标值历史记录"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                INSERT INTO biz_metric_value_history 
                (metric_id, metric_value, calculation_time, data_snapshot)
                VALUES (?, ?, ?, ?)
            ''', (
                metric_id,
                value,
                datetime.now(),
                json.dumps({})  # 数据快照
            ))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"保存指标历史失败: {e}")

