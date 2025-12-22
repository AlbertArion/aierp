#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
操作效果评估API接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
import logging

from ...services.operation_impact_evaluation_service import OperationImpactEvaluationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operation-evaluation", tags=["操作评估"])


class OperationEvaluationRequest(BaseModel):
    """操作评估请求"""
    operation_type: str
    operation_id: str
    operation_data: Dict[str, Any]


def get_evaluation_service() -> OperationImpactEvaluationService:
    """获取评估服务实例"""
    return OperationImpactEvaluationService()


@router.post("/evaluate")
async def evaluate_operation(
    request: OperationEvaluationRequest,
    service: OperationImpactEvaluationService = Depends(get_evaluation_service)
) -> Dict:
    """
    评估业务操作效果
    
    Request Body:
        {
            "operation_type": "create_delivery",
            "operation_id": "8000000048",
            "operation_data": {...}
        }
    
    Returns:
        {
            "operation_type": "...",
            "operation_id": "...",
            "impacts": [
                {
                    "metric_id": 1,
                    "metric_name": "DSI",
                    "impact_value": -2.5,
                    "impact_type": "positive",
                    "improvement": {
                        "value": -2.5,
                        "percent": -2.1,
                        "description": "改进 2.5 天"
                    }
                }
            ],
            "related_issues": [...]
        }
    """
    try:
        result = await service.evaluate_operation_impact(
            request.operation_type,
            request.operation_id,
            request.operation_data
        )
        return result
    except Exception as e:
        logger.error(f"评估操作效果失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"评估操作效果失败: {str(e)}")


@router.get("/history/{operation_id}")
async def get_operation_evaluation_history(
    operation_id: str,
    service: OperationImpactEvaluationService = Depends(get_evaluation_service)
) -> List[Dict]:
    """
    获取操作的历史评估记录
    """
    try:
        history = await service.get_evaluation_history(operation_id)
        return history
    except Exception as e:
        logger.error(f"获取评估历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取评估历史失败: {str(e)}")

