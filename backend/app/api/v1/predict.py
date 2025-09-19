"""
指标预测模块API
基于LLM的智能预测系统
实现1-6个月多周期预测，支持业务上下文和外部因素
"""

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from ...models.train.llm_predictor import (
    predict_with_llm, train_llm_model, get_llm_model_status
)
from ...models.train.simple_predictor import (
    predict_simple, train_simple_model, evaluate_simple_model, get_simple_model_status
)
from ...utils.llm.predict_correction import correct_forecast
from ...middleware.rate_limit import rate_limit
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()


class IndicatorsPredictRequest(BaseModel):
    series: List[float] = Field(..., description="历史营收/利润率序列", min_items=6)
    horizon_months: int = Field(1, ge=1, le=6, description="预测月份范围")
    use_llm: bool = Field(True, description="是否使用LLM预测")


class LLMPredictRequest(BaseModel):
    series: List[float] = Field(..., description="历史数据序列", min_items=6)
    horizon_months: int = Field(1, ge=1, le=6, description="预测月份范围")
    context: str = Field("", description="业务上下文信息")
    factors: List[str] = Field([], description="外部影响因素")


class WithFactorsRequest(BaseModel):
    base_forecast: List[float] = Field(..., description="基础预测结果")
    text_factors: str = Field(..., description="外部文本因素，例如'9月有促销活动'")
    confidence_threshold: float = Field(0.8, ge=0.0, le=1.0, description="置信度阈值")


class ModelEvaluationRequest(BaseModel):
    series: List[float] = Field(..., description="评估数据序列", min_items=6)
    test_size: float = Field(0.2, ge=0.1, le=0.5, description="测试集比例")


@router.post("/indicators")
async def indicators_predict(payload: IndicatorsPredictRequest) -> Dict[str, Any]:
    """指标预测接口"""
    try:
        if len(payload.series) < 6:
            raise HTTPException(
                status_code=400, 
                detail="历史数据不足，至少需要6个数据点"
            )
        
        # 确保horizon_months在1-6范围内
        horizon_months = max(1, min(6, payload.horizon_months))
        
        # 根据用户选择使用LLM或简单预测
        start_time = time.time()
        if payload.use_llm:
            # 使用LLM预测
            result = predict_with_llm(
                series=payload.series,
                horizon_months=horizon_months,
                context="企业指标预测",
                factors=[]
            )
            forecast = result.get("predictions", [])
            confidence = result.get("confidence", 0.5)
            model_type = "LLM"
        else:
            # 使用简单预测
            forecast = predict_simple(payload.series, horizon_months)
            confidence = 0.7  # 简单预测的固定置信度
            model_type = "Simple"
        
        prediction_time = time.time() - start_time
        
        return {
            "forecast": forecast,
            "horizon_months": horizon_months,
            "model_type": model_type,
            "confidence": confidence,
            "prediction_time_ms": int(prediction_time * 1000),
            "data_points_used": len(payload.series),
            "is_accurate": confidence > 0.7
        }
        
    except Exception as e:
        logger.error(f"指标预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.post("/with-factors")
async def predict_with_factors(payload: WithFactorsRequest) -> Dict[str, Any]:
    """带外部因素的预测修正"""
    try:
        if not payload.base_forecast:
            raise HTTPException(status_code=400, detail="基础预测结果不能为空")
        
        # 使用LLM进行预测修正
        correction_result = correct_forecast(payload.base_forecast, payload.text_factors)
        
        # 解析LLM结果
        if isinstance(correction_result, dict) and "raw" in correction_result:
            # 尝试解析LLM返回的JSON
            import json
            try:
                llm_data = json.loads(correction_result["raw"])
                corrected_forecast = llm_data.get("corrected", payload.base_forecast)
                explanation = llm_data.get("explain", "基于外部因素进行了预测修正")
            except:
                corrected_forecast = payload.base_forecast
                explanation = "LLM解析失败，使用原始预测"
        else:
            corrected_forecast = payload.base_forecast
            explanation = "LLM修正失败，使用原始预测"
        
        # 计算修正幅度
        if len(corrected_forecast) == len(payload.base_forecast):
            changes = [abs(c - b) for c, b in zip(corrected_forecast, payload.base_forecast)]
            avg_change = sum(changes) / len(changes) if changes else 0.0
            change_percentage = (avg_change / max(payload.base_forecast)) * 100 if payload.base_forecast else 0.0
        else:
            change_percentage = 0.0
        
        return {
            "base_forecast": payload.base_forecast,
            "corrected_forecast": corrected_forecast,
            "external_factors": payload.text_factors,
            "explanation": explanation,
            "change_percentage": change_percentage,
            "confidence": min(1.0, max(0.5, 1.0 - change_percentage / 100))
        }
        
    except Exception as e:
        logger.error(f"外部因素修正失败: {e}")
        raise HTTPException(status_code=500, detail=f"修正失败: {str(e)}")


@router.post("/llm-predict")
@rate_limit(max_requests=10, window_seconds=60)
async def llm_predict(payload: LLMPredictRequest) -> Dict[str, Any]:
    """LLM智能预测接口"""
    try:
        if len(payload.series) < 6:
            raise HTTPException(status_code=400, detail="历史数据不足，至少需要6个数据点")
        
        # 限制预测月份
        horizon_months = min(6, payload.horizon_months)
        
        # 使用LLM进行预测
        start_time = time.time()
        result = predict_with_llm(
            series=payload.series,
            horizon_months=horizon_months,
            context=payload.context,
            factors=payload.factors
        )
        prediction_time = time.time() - start_time
        
        return {
            "predictions": result.get("predictions", []),
            "horizon_months": horizon_months,
            "model_type": "LLM",
            "confidence": result.get("confidence", 0.5),
            "trend_analysis": result.get("trend_analysis", ""),
            "risk_factors": result.get("risk_factors", []),
            "recommendations": result.get("recommendations", []),
            "methodology": result.get("methodology", "LLM预测"),
            "prediction_time_ms": int(prediction_time * 1000),
            "data_points_used": len(payload.series)
        }
        
    except Exception as e:
        logger.error(f"LLM预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM预测失败: {str(e)}")


@router.post("/llm-simple")
@rate_limit(max_requests=5, window_seconds=60)
async def llm_simple_predict(payload: IndicatorsPredictRequest) -> Dict[str, Any]:
    """LLM简单预测接口（向后兼容）"""
    try:
        if len(payload.series) < 6:
            raise HTTPException(status_code=400, detail="历史数据不足，至少需要6个数据点")
        
        # 限制预测月份为3个月以内
        horizon_months = min(3, payload.horizon_months)
        
        # 使用指数平滑进行基础预测
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(
            payload.series, 
            trend='add', 
            seasonal='add', 
            seasonal_periods=min(6, len(payload.series) // 2)
        )
        fitted_model = model.fit()
        base_forecast = fitted_model.forecast(horizon_months).tolist()
        
        return {
            "forecast": base_forecast,
            "horizon_months": horizon_months,
            "model_type": "LLM_Simple",
            "note": "基于指数平滑的简单预测"
        }
        
    except Exception as e:
        logger.error(f"LLM简单预测失败: {e}")
        raise HTTPException(status_code=503, detail=f"LLM预测暂时不可用: {str(e)}")


@router.post("/train")
async def train_model_api(payload: ModelEvaluationRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """模型训练/评估接口"""
    try:
        if len(payload.series) < 6:
            raise HTTPException(status_code=400, detail="训练数据不足，至少需要6个数据点")
        
        # 训练简单模型
        start_time = time.time()
        training_result = train_simple_model(payload.series, payload.test_size)
        training_time = time.time() - start_time
        
        # 评估模型
        eval_result = evaluate_simple_model(payload.series, payload.test_size)
        
        return {
            "status": "trained" if training_result.get("is_trained", False) else "failed",
            "training_time_seconds": int(training_time),
            "model_params": training_result,
            "metrics": {
                "mae": eval_result.get("mae", 0.0),
                "mape": eval_result.get("mape", 0.0),
                "is_accurate": eval_result.get("is_accurate", False)
            },
            "data_points": len(payload.series),
            "test_size": payload.test_size,
            "model_type": "Simple"
        }
        
    except Exception as e:
        logger.error(f"模型训练失败: {e}")
        raise HTTPException(status_code=500, detail=f"训练失败: {str(e)}")


@router.post("/evaluate")
async def evaluate_model_api(payload: ModelEvaluationRequest) -> Dict[str, Any]:
    """模型评估接口"""
    try:
        if len(payload.series) < 6:
            raise HTTPException(status_code=400, detail="评估数据不足，至少需要6个数据点")
        
        # 使用简单预测器进行评估
        eval_result = evaluate_simple_model(payload.series, payload.test_size)
        
        return {
            "metrics": {
                "mae": eval_result.get("mae", 0.0),
                "mape": eval_result.get("mape", 0.0),
                "is_accurate": eval_result.get("is_accurate", False)
            },
            "predictions": eval_result.get("predictions", []),
            "actuals": eval_result.get("actuals", []),
            "test_size": int(len(payload.series) * payload.test_size),
            "train_size": int(len(payload.series) * (1 - payload.test_size)),
            "model_type": "Simple"
        }
        
    except Exception as e:
        logger.error(f"模型评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


@router.get("/model-status")
async def get_model_status_api() -> Dict[str, Any]:
    """获取模型状态"""
    try:
        llm_status = get_llm_model_status()
        simple_status = get_simple_model_status()
        
        return {
            "llm_status": llm_status,
            "simple_status": simple_status,
            "available_models": ["LLM", "Simple"],
            "recommended_model": "LLM"
        }
        
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/llm-train")
async def train_llm_model_api(payload: ModelEvaluationRequest) -> Dict[str, Any]:
    """LLM模型训练/评估接口"""
    try:
        if len(payload.series) < 6:
            raise HTTPException(status_code=400, detail="训练数据不足，至少需要6个数据点")
        
        # 训练/评估LLM模型
        start_time = time.time()
        result = train_llm_model(payload.series, payload.test_size)
        training_time = time.time() - start_time
        
        return {
            "status": "trained" if result.get("is_trained", False) else "failed",
            "training_time_seconds": int(training_time),
            "model_params": result,
            "data_points": len(payload.series),
            "test_size": payload.test_size
        }
        
    except Exception as e:
        logger.error(f"LLM模型训练失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM训练失败: {str(e)}")


@router.post("/batch-predict")
async def batch_predict(payload: List[IndicatorsPredictRequest]) -> Dict[str, Any]:
    """批量预测接口"""
    try:
        if len(payload) > 10:
            raise HTTPException(status_code=400, detail="批量预测最多支持10个序列")
        
        results = []
        for i, req in enumerate(payload):
            try:
                if len(req.series) < 6:
                    results.append({
                        "index": i,
                        "error": "数据不足",
                        "forecast": []
                    })
                    continue
                
                # 根据用户选择使用LLM或简单预测
                if req.use_llm:
                    result = predict_with_llm(
                        series=req.series,
                        horizon_months=req.horizon_months,
                        context="批量预测",
                        factors=[]
                    )
                    forecast = result.get("predictions", [])
                    model_type = "LLM"
                else:
                    forecast = predict_simple(req.series, req.horizon_months)
                    model_type = "Simple"
                
                results.append({
                    "index": i,
                    "forecast": forecast,
                    "horizon_months": req.horizon_months,
                    "data_points": len(req.series),
                    "model_type": model_type
                })
                
            except Exception as e:
                results.append({
                    "index": i,
                    "error": str(e),
                    "forecast": []
                })
        
        return {
            "batch_results": results,
            "total_processed": len(payload),
            "successful": len([r for r in results if "error" not in r])
        }
        
    except Exception as e:
        logger.error(f"批量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量预测失败: {str(e)}")


# 添加numpy导入
import numpy as np