#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
指标影响因素分析服务
分析指标的正向和负向影响因素
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ..db.sqlite_db import get_sqlite_db

logger = logging.getLogger(__name__)


class MetricFactorAnalysisService:
    """指标影响因素分析服务"""
    
    def __init__(self):
        self.db = get_sqlite_db()
    
    async def analyze_factors(
        self, 
        metric_id: int, 
        time_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[Dict]]:
        """
        分析指标的影响因素
        
        Args:
            metric_id: 指标ID
            time_range: 时间范围，格式：{"start": "2025-01-01", "end": "2025-01-31"}
        
        Returns:
            {
                "positive_factors": [...],
                "negative_factors": [...]
            }
        """
        try:
            # 1. 获取指标的所有影响因素配置
            factors = self._get_metric_factors(metric_id)
            
            positive_factors = []
            negative_factors = []
            
            for factor in factors:
                # 2. 计算因素的影响值
                impact_value = await self._calculate_factor_impact(
                    factor, 
                    time_range
                )
                
                factor_data = {
                    "id": factor['id'],
                    "code": factor['factor_code'],
                    "name": factor['factor_name'],
                    "impact": impact_value,
                    "weight": float(factor.get('weight', 1.0)),
                    "description": factor.get('description', '')
                }
                
                if factor['factor_type'] == "positive":
                    positive_factors.append(factor_data)
                else:
                    negative_factors.append(factor_data)
            
            return {
                "positive_factors": sorted(
                    positive_factors, 
                    key=lambda x: abs(x['impact']), 
                    reverse=True
                ),
                "negative_factors": sorted(
                    negative_factors, 
                    key=lambda x: abs(x['impact']), 
                    reverse=True
                )
            }
            
        except Exception as e:
            logger.error(f"分析影响因素失败: {e}", exc_info=True)
            return {"positive_factors": [], "negative_factors": []}
    
    def _get_metric_factors(self, metric_id: int) -> List[Dict]:
        """获取指标的影响因素配置"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT * FROM biz_metric_factor
            WHERE metric_id = ? AND is_enabled = 1
            ORDER BY weight DESC
        ''', (metric_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def _calculate_factor_impact(
        self, 
        factor: Dict, 
        time_range: Optional[Dict[str, str]] = None
    ) -> float:
        """
        计算因素的影响值
        
        这里简化实现，实际应该根据impact_formula计算
        """
        try:
            # 如果配置了影响计算公式，应该解析并执行
            impact_formula = factor.get('impact_formula')
            if impact_formula:
                # 这里应该实现公式解析器
                # 简化实现：返回示例值
                pass
            
            # 根据因素代码返回示例影响值
            factor_code = factor.get('factor_code', '')
            
            # 示例：DSI指标的影响因素
            if factor_code == 'NEW_PRODUCT_STOCKING':
                return 8.5  # 增加8.5天
            elif factor_code == 'CHANNEL_PRESSURE':
                return 6.0  # 增加6天
            elif factor_code == 'OLD_PRODUCT_PROMOTION':
                return -4.0  # 减少4天
            elif factor_code == 'VMI_ENABLED':
                return -3.0  # 减少3天
            
            # 默认返回0
            return 0.0
            
        except Exception as e:
            logger.error(f"计算因素影响值失败: {e}")
            return 0.0

