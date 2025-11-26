#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAP报工数据API接口
提供SAP报工数据的RESTful API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Dict, List, Any, Optional
from datetime import date
import logging

from app.db.sqlite_db import get_sqlite_db
from app.repository.sap_work_report_repo import SAPWorkReportRepository
from app.schemas.sap_work_report import SAPWorkReportSearchRequest
from app.schemas.sap_ai_query import SAPAIQueryRequest, SAPAIQueryResponse
from app.services.sap_ai_query_service import SAPAIQueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sap-work-reports", tags=["SAP报工数据"])

def get_sap_repo(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth")
) -> SAPWorkReportRepository:
    """获取SAP报工数据Repository（现在使用PostgreSQL数据源）"""
    repo = SAPWorkReportRepository()
    
    # 从请求头获取token并设置到repository
    token = None
    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        else:
            token = authorization.strip()
    
    if not token and blade_auth:
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()
        elif blade_auth.lower().startswith("crypto "):
            token = blade_auth.strip()
        else:
            token = blade_auth.strip()
    
    if token:
        repo.set_token(token)
        logger.info(f"Token已设置到SAPWorkReportRepository (长度: {len(token)})")
    
    return repo

@router.get("/search")
async def search_work_reports(
    keyword: Optional[str] = Query(None, description="搜索关键字"),
    aufnr: Optional[str] = Query(None, description="订单号"),
    matnr: Optional[str] = Query(None, description="物料号"),
    werks: Optional[str] = Query(None, description="工厂"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """搜索报工数据"""
    try:
        result = await repo.search_work_reports(
            keyword=keyword,
            aufnr=aufnr,
            matnr=matnr,
            werks=werks,
            start_date=start_date,
            end_date=end_date,
            page=page,
            size=size
        )
        
        return {
            "success": True,
            "data": result,
            "message": "搜索成功"
        }
        
    except Exception as e:
        logger.error(f"搜索报工数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order/{aufnr}")
async def get_order_details(
    aufnr: str,
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """获取订单详细信息"""
    try:
        order_details = await repo.get_order_details(aufnr)
        
        if not order_details:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        return {
            "success": True,
            "data": order_details,
            "message": "获取订单详情成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订单详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/material/{matnr}")
async def get_material_info(
    matnr: str,
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """获取物料信息"""
    try:
        material_info = await repo.get_material_info(matnr)
        
        if not material_info:
            raise HTTPException(status_code=404, detail="物料不存在")
        
        return {
            "success": True,
            "data": material_info,
            "message": "获取物料信息成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取物料信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/work-center/{arbid}")
async def get_work_center_info(
    arbid: str,
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """获取工作中心信息"""
    try:
        work_center_info = await repo.get_work_center_info(arbid)
        
        if not work_center_info:
            raise HTTPException(status_code=404, detail="工作中心不存在")
        
        return {
            "success": True,
            "data": work_center_info,
            "message": "获取工作中心信息成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作中心信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_statistics(
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """获取统计信息"""
    try:
        stats = await repo.get_statistics()
        
        return {
            "success": True,
            "data": stats,
            "message": "获取统计信息成功"
        }
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent-orders")
async def get_recent_orders(
    limit: int = Query(10, ge=1, le=100, description="限制数量"),
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """获取最近的订单"""
    try:
        recent_orders = await repo.get_recent_orders(limit=limit)
        
        return {
            "success": True,
            "data": recent_orders,
            "message": "获取最近订单成功"
        }
        
    except Exception as e:
        logger.error(f"获取最近订单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders-by-status/{status}")
async def get_orders_by_status(
    status: str,
    repo: SAPWorkReportRepository = Depends(get_sap_repo)
):
    """根据状态获取订单"""
    try:
        orders = await repo.get_orders_by_status(status)
        
        return {
            "success": True,
            "data": orders,
            "message": f"获取状态为 {status} 的订单成功"
        }
        
    except Exception as e:
        logger.error(f"根据状态获取订单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ai-query", response_model=SAPAIQueryResponse)
async def ai_query(
    request: SAPAIQueryRequest,
    db: Any = Depends(get_sqlite_db)
):
    """AI智能查询SAP订单报工情况"""
    try:
        # 创建AI查询服务
        ai_service = SAPAIQueryService(db)
        
        # 处理查询
        result = await ai_service.process_query(request.query)
        
        return SAPAIQueryResponse(
            success=True,
            data={
                "explanation": result.explanation,
                "rows": result.rows,
                "tableType": result.tableType,
                "sql": result.sql,
                "queryType": result.queryType
            },
            message="AI查询成功"
        )
        
    except Exception as e:
        logger.error(f"AI查询失败: {e}")
        return SAPAIQueryResponse(
            success=False,
            data=None,
            message=f"AI查询失败: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "success": True,
        "message": "SAP报工数据API服务正常",
        "timestamp": date.today().isoformat()
    }
