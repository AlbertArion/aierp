#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
指标配置管理API接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from ...db.sqlite_db import get_sqlite_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metric-config", tags=["指标配置"])


class MetricDefinitionCreate(BaseModel):
    """指标定义创建请求"""
    metric_code: str
    metric_name: str
    metric_category: str
    metric_type: str
    unit: Optional[str] = None
    calculation_formula: Optional[str] = None
    target_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    description: Optional[str] = None


class MetricDefinitionUpdate(BaseModel):
    """指标定义更新请求"""
    metric_name: Optional[str] = None
    metric_category: Optional[str] = None
    metric_type: Optional[str] = None
    unit: Optional[str] = None
    calculation_formula: Optional[str] = None
    target_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None


class FactorCreate(BaseModel):
    """影响因素创建请求"""
    metric_id: int
    factor_code: str
    factor_name: str
    factor_type: str
    impact_formula: Optional[str] = None
    weight: Optional[float] = 1.0
    description: Optional[str] = None


class MeasureCreate(BaseModel):
    """改进措施创建请求"""
    metric_id: int
    measure_code: str
    measure_name: str
    measure_type: Optional[str] = None
    expected_improvement_formula: Optional[str] = None
    priority: Optional[int] = 0
    description: Optional[str] = None


class OperationRelationCreate(BaseModel):
    """操作关联创建请求"""
    operation_type: str
    operation_code: str
    metric_id: int
    impact_formula: Optional[str] = None
    impact_type: Optional[str] = None


@router.get("/metrics")
async def list_metrics(
    category: Optional[str] = Query(None, description="业务分类"),
    is_enabled: Optional[bool] = Query(None, description="是否启用")
) -> List[Dict]:
    """获取指标列表"""
    try:
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        query = "SELECT * FROM biz_metric_definition WHERE 1=1"
        params = []
        
        if category:
            query += " AND metric_category = ?"
            params.append(category)
        
        if is_enabled is not None:
            query += " AND is_enabled = ?"
            params.append(1 if is_enabled else 0)
        
        query += " ORDER BY sort_order, id"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"获取指标列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取指标列表失败: {str(e)}")


@router.post("/metrics")
async def create_metric(metric: MetricDefinitionCreate) -> Dict:
    """创建指标定义"""
    try:
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        cursor.execute('''
            INSERT INTO biz_metric_definition 
            (metric_code, metric_name, metric_category, metric_type, unit,
             calculation_formula, target_value, warning_threshold, critical_threshold,
             description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metric.metric_code,
            metric.metric_name,
            metric.metric_category,
            metric.metric_type,
            metric.unit,
            metric.calculation_formula,
            metric.target_value,
            metric.warning_threshold,
            metric.critical_threshold,
            metric.description
        ))
        
        db.conn.commit()
        
        metric_id = cursor.lastrowid
        return {"id": metric_id, "message": "指标创建成功"}
        
    except Exception as e:
        logger.error(f"创建指标失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建指标失败: {str(e)}")


@router.put("/metrics/{metric_id}")
async def update_metric(
    metric_id: int,
    metric: MetricDefinitionUpdate
) -> Dict:
    """更新指标定义"""
    try:
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        # 构建更新字段
        updates = []
        params = []
        
        if metric.metric_name is not None:
            updates.append("metric_name = ?")
            params.append(metric.metric_name)
        
        if metric.target_value is not None:
            updates.append("target_value = ?")
            params.append(metric.target_value)
        
        if metric.is_enabled is not None:
            updates.append("is_enabled = ?")
            params.append(1 if metric.is_enabled else 0)
        
        # 添加其他字段...
        
        if not updates:
            raise HTTPException(status_code=400, detail="没有要更新的字段")
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(metric_id)
        
        query = f"UPDATE biz_metric_definition SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        db.conn.commit()
        
        return {"message": "指标更新成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新指标失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新指标失败: {str(e)}")


@router.post("/metrics/{metric_id}/factors")
async def create_factor(
    metric_id: int,
    factor: FactorCreate
) -> Dict:
    """创建影响因素"""
    try:
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        cursor.execute('''
            INSERT INTO biz_metric_factor 
            (metric_id, factor_code, factor_name, factor_type, impact_formula, weight, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            metric_id,
            factor.factor_code,
            factor.factor_name,
            factor.factor_type,
            factor.impact_formula,
            factor.weight,
            factor.description
        ))
        
        db.conn.commit()
        
        factor_id = cursor.lastrowid
        return {"id": factor_id, "message": "影响因素创建成功"}
        
    except Exception as e:
        logger.error(f"创建影响因素失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建影响因素失败: {str(e)}")


@router.post("/metrics/{metric_id}/measures")
async def create_measure(
    metric_id: int,
    measure: MeasureCreate
) -> Dict:
    """创建改进措施"""
    try:
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        cursor.execute('''
            INSERT INTO biz_improvement_measure 
            (metric_id, measure_code, measure_name, measure_type, 
             expected_improvement_formula, priority, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            metric_id,
            measure.measure_code,
            measure.measure_name,
            measure.measure_type,
            measure.expected_improvement_formula,
            measure.priority,
            measure.description
        ))
        
        db.conn.commit()
        
        measure_id = cursor.lastrowid
        return {"id": measure_id, "message": "改进措施创建成功"}
        
    except Exception as e:
        logger.error(f"创建改进措施失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建改进措施失败: {str(e)}")


@router.post("/operation-relations")
async def create_operation_relation(
    relation: OperationRelationCreate
) -> Dict:
    """创建操作与指标关联"""
    try:
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        cursor.execute('''
            INSERT INTO biz_operation_metric_relation 
            (operation_type, operation_code, metric_id, impact_formula, impact_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            relation.operation_type,
            relation.operation_code,
            relation.metric_id,
            relation.impact_formula,
            relation.impact_type
        ))
        
        db.conn.commit()
        
        relation_id = cursor.lastrowid
        return {"id": relation_id, "message": "操作关联创建成功"}
        
    except Exception as e:
        logger.error(f"创建操作关联失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建操作关联失败: {str(e)}")

