#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
业务问题识别API接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from ...services.business_issue_detection_service import BusinessIssueDetectionService
from ...services.metric_factor_analysis_service import MetricFactorAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/business-issues", tags=["业务问题"])


def extract_token_and_tenant(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> tuple:
    """
    从请求头提取token和租户信息
    
    Returns:
        (token, mandt, tenant_id) 元组
    """
    token = None
    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
    if not token and blade_auth:
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()
        elif not blade_auth.lower().startswith("crypto "):
            token = blade_auth.strip()
    
    mandt = x_mandt
    tenant_id = x_tenant_id or mandt
    
    return token, mandt, tenant_id


def get_issue_detection_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth"),
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
) -> BusinessIssueDetectionService:
    """获取问题识别服务实例"""
    token, mandt, tenant_id = extract_token_and_tenant(
        authorization=authorization,
        blade_auth=blade_auth,
        x_mandt=x_mandt,
        x_tenant_id=x_tenant_id
    )
    return BusinessIssueDetectionService(token=token, mandt=mandt, tenant_id=tenant_id)


def get_factor_service() -> MetricFactorAnalysisService:
    """获取因素分析服务实例"""
    return MetricFactorAnalysisService()


@router.get("/detect")
async def detect_issues(
    category: Optional[str] = Query(None, description="业务分类(SD/PP/MM/FI/CO)"),
    service: BusinessIssueDetectionService = Depends(get_issue_detection_service)
) -> List[Dict]:
    """
    检测业务问题
    
    Returns:
        问题列表，包含问题基本信息、严重程度、量化数据
    """
    try:
        issues = await service.detect_issues(category)
        return issues
    except Exception as e:
        logger.error(f"检测业务问题失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检测业务问题失败: {str(e)}")


@router.get("/{issue_id}/factors")
async def get_issue_factors(
    issue_id: str,
    time_range: Optional[str] = Query(None, description="时间范围，格式：start,end"),
    factor_service: MetricFactorAnalysisService = Depends(get_factor_service),
    issue_service: BusinessIssueDetectionService = Depends(get_issue_detection_service)
) -> Dict:
    """
    获取问题的影响因素分析
    
    Args:
        issue_id: 问题ID（整数）或指标代码（字符串，如 sop_health, otif）
    
    Returns:
        {
            "positive_factors": [...],
            "negative_factors": [...]
        }
    """
    try:
        # 如果 issue_id 是字符串（metric_code），先查找对应的 metric_id
        if isinstance(issue_id, str) and not issue_id.isdigit():
            from ...db.sqlite_db import get_sqlite_db
            db = get_sqlite_db()
            cursor = db.conn.cursor()
            # 根据 metric_code 查找指标
            cursor.execute('''
                SELECT id FROM biz_metric_definition 
                WHERE metric_code = ? AND is_enabled = 1
                LIMIT 1
            ''', (issue_id.upper(),))
            row = cursor.fetchone()
            if row:
                metric_id = row['id']
            else:
                raise HTTPException(status_code=404, detail=f"未找到指标代码为 {issue_id} 的指标")
        else:
            # 如果是数字字符串，转换为整数
            issue_id_int = int(issue_id)
            # 获取问题信息
            issue = await issue_service.get_issue_detail(issue_id_int)
            if not issue:
                raise HTTPException(status_code=404, detail="问题不存在")
            metric_id = issue['metric_id']
        
        # 解析时间范围
        time_range_dict = None
        if time_range:
            parts = time_range.split(',')
            if len(parts) == 2:
                time_range_dict = {"start": parts[0], "end": parts[1]}
        
        factors = await factor_service.analyze_factors(metric_id, time_range_dict)
        return factors
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取影响因素失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取影响因素失败: {str(e)}")


@router.get("/{issue_id}/improvement-measures")
async def get_improvement_measures(
    issue_id: str,
    use_ai: bool = Query(False, description="是否使用AI推荐措施"),
    service: BusinessIssueDetectionService = Depends(get_issue_detection_service)
) -> List[Dict]:
    """
    获取问题的改进措施列表
    
    Args:
        issue_id: 问题ID（整数）或指标代码（字符串，如 sop_health, otif）
        use_ai: 是否使用AI推荐措施
    
    Returns:
        改进措施列表，包含：
        - 措施名称
        - 目标指标
        - 预期改进度
        - 当前状态
    """
    try:
        # 如果 issue_id 是字符串（metric_code），先查找对应的 metric_id
        if isinstance(issue_id, str) and not issue_id.isdigit():
            metric_code = issue_id.upper()
            from ...db.sqlite_db import get_sqlite_db
            db = get_sqlite_db()
            cursor = db.conn.cursor()
            # 根据 metric_code 查找指标
            cursor.execute('''
                SELECT id FROM biz_metric_definition 
                WHERE metric_code = ? AND is_enabled = 1
                LIMIT 1
            ''', (metric_code,))
            row = cursor.fetchone()
            if row:
                metric_id = row['id']
                # 直接获取改进措施
                measures = service._get_improvement_measures(metric_id)
                # 如果启用AI推荐，需要先获取问题信息
                if use_ai:
                    # 尝试获取问题详情
                    issue = await service.get_issue_detail(metric_code)
                    if issue:
                        ai_measures = await service.get_ai_recommended_measures(issue)
                        measures = measures + ai_measures
            else:
                raise HTTPException(status_code=404, detail=f"未找到指标代码为 {metric_code} 的指标")
        else:
            # 如果是数字字符串，转换为整数
            issue_id_int = int(issue_id)
            issue = await service.get_issue_detail(issue_id_int)
            if not issue:
                raise HTTPException(status_code=404, detail="问题不存在")
            measures = issue.get('improvement_measures', [])
            
            # 如果启用AI推荐，获取AI推荐的措施
            if use_ai:
                ai_measures = await service.get_ai_recommended_measures(issue)
                # 合并配置的措施和AI推荐的措施
                measures = measures + ai_measures
        
        return measures
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取改进措施失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取改进措施失败: {str(e)}")


@router.get("/{issue_id}/detail")
async def get_issue_detail(
    issue_id: str,
    service: BusinessIssueDetectionService = Depends(get_issue_detection_service)
) -> Dict:
    """
    获取问题详情
    
    Args:
        issue_id: 问题ID（整数）或指标代码（字符串，如 sop_health, otif）
    
    Returns:
        问题详情，包括：
        - 问题基本信息
        - 影响因素（正向/负向）
        - 改进措施列表
    """
    try:
        # 如果 issue_id 是字符串（metric_code），先查找对应的 issue_id
        if isinstance(issue_id, str) and not issue_id.isdigit():
            metric_code = issue_id.upper()
            from ...db.sqlite_db import get_sqlite_db
            db = get_sqlite_db()
            cursor = db.conn.cursor()
            # 根据 metric_code 查找最新的问题记录
            cursor.execute('''
                SELECT ir.id 
                FROM biz_issue_record ir
                JOIN biz_metric_definition md ON ir.metric_id = md.id
                WHERE md.metric_code = ? AND ir.status = 'active'
                ORDER BY ir.detected_at DESC
                LIMIT 1
            ''', (metric_code,))
            row = cursor.fetchone()
            if row:
                issue_id = row['id']
            else:
                # 如果没有找到问题记录，尝试根据 metric_code 获取指标信息并创建临时问题详情
                cursor.execute('''
                    SELECT * FROM biz_metric_definition 
                    WHERE metric_code = ? AND is_enabled = 1
                    LIMIT 1
                ''', (metric_code,))
                metric_row = cursor.fetchone()
                if metric_row:
                    metric = dict(metric_row)
                    # 计算当前值
                    current_value = await service.metric_service.calculate_metric_value(metric['id'])
                    if current_value is not None:
                        # 创建临时问题详情
                        detail = {
                            'id': None,
                            'metric_id': metric['id'],
                            'metric_code': metric['metric_code'],
                            'metric_name': metric['metric_name'],
                            'unit': metric.get('unit', ''),
                            'current_value': current_value,
                            'target_value': metric.get('target_value', 0),
                            'deviation': current_value - metric.get('target_value', 0),
                            'status': 'active'
                        }
                        # 获取影响因素
                        from ...services.metric_factor_analysis_service import MetricFactorAnalysisService
                        factor_service = MetricFactorAnalysisService()
                        factors = await factor_service.analyze_factors(metric['id'], {})
                        detail['factors'] = factors
                        
                        # 获取改进措施
                        measures = service._get_improvement_measures(metric['id'])
                        detail['improvement_measures'] = measures
                        
                        return detail
                raise HTTPException(status_code=404, detail=f"未找到指标代码为 {metric_code} 的问题或指标")
        else:
            # 如果是数字字符串，转换为整数
            issue_id = int(issue_id)
        
        detail = await service.get_issue_detail(issue_id)
        if not detail:
            raise HTTPException(status_code=404, detail="问题不存在")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取问题详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取问题详情失败: {str(e)}")


@router.get("")
async def list_issues(
    category: Optional[str] = Query(None, description="业务分类"),
    status: Optional[str] = Query("active", description="问题状态(active/resolved/archived)"),
    severity: Optional[str] = Query(None, description="严重程度(critical/warning/info)"),
    service: BusinessIssueDetectionService = Depends(get_issue_detection_service)
) -> List[Dict]:
    """
    获取问题列表
    
    Returns:
        问题列表
    """
    try:
        from ...db.sqlite_db import get_sqlite_db
        db = get_sqlite_db()
        cursor = db.conn.cursor()
        
        query = '''
            SELECT ir.*, md.metric_name, md.metric_code, md.unit
            FROM biz_issue_record ir
            JOIN biz_metric_definition md ON ir.metric_id = md.id
            WHERE 1=1
        '''
        params = []
        
        if category:
            query += " AND md.metric_category = ?"
            params.append(category)
        
        if status:
            query += " AND ir.status = ?"
            params.append(status)
        
        if severity:
            query += " AND ir.severity = ?"
            params.append(severity)
        
        query += " ORDER BY ir.severity_score DESC, ir.detected_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"获取问题列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取问题列表失败: {str(e)}")

