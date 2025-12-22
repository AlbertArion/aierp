#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
操作效果评估服务
评估业务操作对指标的改进效果
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..db.sqlite_db import get_sqlite_db
from .metric_calculation_service import MetricCalculationService

logger = logging.getLogger(__name__)


class OperationImpactEvaluationService:
    """业务操作效果评估服务"""
    
    def __init__(self):
        self.db = get_sqlite_db()
        self.metric_service = MetricCalculationService()
    
    async def evaluate_operation_impact(
        self,
        operation_type: str,
        operation_id: str,
        operation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估业务操作对指标的影响
        
        Args:
            operation_type: 操作类型（如：create_delivery, create_production_order）
            operation_id: 操作ID
            operation_data: 操作数据
        
        Returns:
            影响评估结果
        """
        try:
            # 1. 获取该操作关联的所有指标
            relations = self._get_operation_relations(operation_type)
            
            impacts = []
            related_issues = []
            
            for relation in relations:
                # 2. 计算操作对该指标的影响值
                impact_value = await self._calculate_operation_impact(
                    relation,
                    operation_data
                )
                
                if impact_value == 0:
                    continue
                
                # 3. 获取指标当前值（操作前）
                before_value = await self.metric_service.calculate_metric_value(
                    relation['metric_id']
                )
                
                # 4. 更新指标值（操作后）
                after_value = before_value + impact_value if before_value else impact_value
                
                # 5. 计算改进度
                improvement = self._calculate_improvement(
                    before_value,
                    after_value,
                    impact_value
                )
                
                # 6. 保存影响记录
                await self._save_impact_record(
                    operation_type,
                    operation_id,
                    relation['metric_id'],
                    impact_value,
                    relation.get('impact_type', 'positive' if impact_value < 0 else 'negative'),
                    before_value,
                    after_value,
                    improvement.get('percent', 0)
                )
                
                # 7. 检查是否解决了相关问题
                issue_updates = await self._check_issue_updates(
                    relation['metric_id'],
                    after_value
                )
                
                impacts.append({
                    "metric_id": relation['metric_id'],
                    "metric_code": relation.get('metric_code', ''),
                    "metric_name": relation.get('metric_name', ''),
                    "impact_value": impact_value,
                    "impact_type": relation.get('impact_type', 'positive' if impact_value < 0 else 'negative'),
                    "before_value": before_value,
                    "after_value": after_value,
                    "improvement": improvement
                })
                
                related_issues.extend(issue_updates)
            
            return {
                "operation_type": operation_type,
                "operation_id": operation_id,
                "operation_time": datetime.now().isoformat(),
                "impacts": impacts,
                "related_issues": related_issues
            }
            
        except Exception as e:
            logger.error(f"评估操作影响失败: {e}", exc_info=True)
            return {
                "operation_type": operation_type,
                "operation_id": operation_id,
                "operation_time": datetime.now().isoformat(),
                "impacts": [],
                "related_issues": []
            }
    
    def _get_operation_relations(self, operation_type: str) -> List[Dict]:
        """获取操作关联的指标"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT omr.*, md.metric_code, md.metric_name
            FROM biz_operation_metric_relation omr
            JOIN biz_metric_definition md ON omr.metric_id = md.id
            WHERE omr.operation_type = ? AND omr.is_enabled = 1
        ''', (operation_type,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def _calculate_operation_impact(
        self,
        relation: Dict,
        operation_data: Dict[str, Any]
    ) -> float:
        """
        计算操作对指标的具体影响值
        
        这里简化实现，实际应该根据impact_formula计算
        """
        try:
            impact_formula = relation.get('impact_formula')
            if not impact_formula:
                return 0.0
            
            # 解析公式并计算
            # 简化实现：根据操作类型返回示例值
            
            operation_type = relation.get('operation_type', '')
            metric_code = relation.get('metric_code', '')
            
            # 示例：创建交货单对DSI的影响
            if operation_type == 'create_delivery' and metric_code == 'DSI':
                # 假设交货数量为operation_data中的quantity
                quantity = operation_data.get('quantity', 0)
                # 简化计算：每100单位减少0.1天
                return -float(quantity) / 1000.0 * 0.1
            
            # 示例：创建采购订单对DSI的影响（增加库存）
            elif operation_type == 'create_purchase_order' and metric_code == 'DSI':
                quantity = operation_data.get('quantity', 0)
                return float(quantity) / 1000.0 * 0.1
            
            return 0.0
            
        except Exception as e:
            logger.error(f"计算操作影响值失败: {e}")
            return 0.0
    
    def _calculate_improvement(
        self,
        before_value: Optional[float],
        after_value: Optional[float],
        impact_value: float
    ) -> Dict[str, Any]:
        """计算改进度"""
        if before_value is None or before_value == 0:
            return {
                "value": impact_value,
                "percent": 0.0,
                "description": f"影响 {impact_value:+.2f}"
            }
        
        percent = (impact_value / abs(before_value)) * 100
        
        return {
            "value": impact_value,
            "percent": percent,
            "description": f"改进 {abs(impact_value):.2f} ({percent:+.2f}%)"
        }
    
    async def _save_impact_record(
        self,
        operation_type: str,
        operation_id: str,
        metric_id: int,
        impact_value: float,
        impact_type: str,
        before_value: Optional[float],
        after_value: Optional[float],
        improvement_percent: float
    ):
        """保存影响记录"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                INSERT INTO biz_operation_impact_record 
                (operation_type, operation_id, operation_time, metric_id,
                 impact_value, impact_type, before_value, after_value, improvement_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_type,
                operation_id,
                datetime.now(),
                metric_id,
                impact_value,
                impact_type,
                before_value,
                after_value,
                improvement_percent
            ))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"保存影响记录失败: {e}")
    
    async def _check_issue_updates(
        self,
        metric_id: int,
        new_value: float
    ) -> List[Dict]:
        """检查是否解决了相关问题"""
        try:
            cursor = self.db.conn.cursor()
            # 获取该指标的活跃问题
            cursor.execute('''
                SELECT * FROM biz_issue_record
                WHERE metric_id = ? AND status = 'active'
            ''', (metric_id,))
            
            rows = cursor.fetchall()
            updates = []
            
            for row in rows:
                issue = dict(row)
                target_value = issue.get('target_value')
                
                # 如果新值达到目标值，标记问题为已解决
                if target_value and abs(new_value - target_value) <= abs(issue.get('deviation', 0)):
                    cursor.execute('''
                        UPDATE biz_issue_record
                        SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (issue['id'],))
                    
                    updates.append({
                        "issue_id": issue['id'],
                        "issue_title": issue['issue_title'],
                        "status": "resolved",
                        "change": f"问题已解决，指标值从{issue.get('current_value')}改善到{new_value}"
                    })
            
            if updates:
                self.db.conn.commit()
            
            return updates
            
        except Exception as e:
            logger.error(f"检查问题更新失败: {e}")
            return []
    
    async def get_evaluation_history(self, operation_id: str) -> List[Dict]:
        """获取操作的历史评估记录"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                SELECT oir.*, md.metric_code, md.metric_name, md.unit
                FROM biz_operation_impact_record oir
                JOIN biz_metric_definition md ON oir.metric_id = md.id
                WHERE oir.operation_id = ?
                ORDER BY oir.operation_time DESC
            ''', (operation_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"获取评估历史失败: {e}")
            return []

