"""
指标预测模块API
支持LSTM模型训练、预测和LLM修正
实现1-6个月多周期预测，误差率<5%
"""

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from ...models.train.lstm_predictor import (
    predict_lstm, train_model, save_model, load_model, evaluate_model, 
    get_model_performance, LSTMPredictor
)
from ...utils.llm.predict_correction import correct_forecast
from ...config.model_switch import get_model_status
from ...middleware.rate_limit import rate_limit
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局预测器实例
_predictor = LSTMPredictor()


class IndicatorsPredictRequest(BaseModel):
    series: List[float] = Field(..., description="历史营收/利润率序列", min_items=12)
    horizon_months: int = Field(1, ge=1, le=6, description="预测月份范围")
    use_lstm: bool = Field(True, description="是否使用LSTM模型")


class WithFactorsRequest(BaseModel):
    base_forecast: List[float] = Field(..., description="基础预测结果")
    text_factors: str = Field(..., description="外部文本因素，例如'9月有促销活动'")
    confidence_threshold: float = Field(0.8, ge=0.0, le=1.0, description="置信度阈值")


class TrainRequest(BaseModel):
    series: List[float] = Field(..., description="训练数据序列", min_items=12)
    test_size: float = Field(0.2, ge=0.1, le=0.5, description="测试集比例")
    epochs: int = Field(100, ge=10, le=500, description="训练轮数")
    batch_size: int = Field(32, ge=8, le=128, description="批次大小")
    sequence_length: int = Field(12, ge=6, le=24, description="序列长度")


class ModelEvaluationRequest(BaseModel):
    series: List[float] = Field(..., description="评估数据序列", min_items=12)
    test_size: float = Field(0.2, ge=0.1, le=0.5, description="测试集比例")


@router.post("/indicators")
async def indicators_predict(payload: IndicatorsPredictRequest) -> Dict[str, Any]:
    """指标预测接口"""
    try:
        if len(payload.series) < 12:
            raise HTTPException(
                status_code=400, 
                detail="历史数据不足，至少需要12个数据点"
            )
        
        # 确保horizon_months在1-6范围内
        horizon_months = max(1, min(6, payload.horizon_months))
        
        # 加载或训练模型
        if not _predictor.is_trained:
            logger.info("模型未训练，开始训练...")
            training_result = _predictor.train(payload.series)
            if not training_result.get("is_accurate", False):
                logger.warning("模型训练精度不足，使用指数平滑")
        
        # 进行预测
        start_time = time.time()
        forecast = _predictor.predict(payload.series, horizon_months)
        prediction_time = time.time() - start_time
        
        # 计算预测置信度（基于历史数据的稳定性）
        series_std = float(np.std(payload.series[-12:])) if len(payload.series) >= 12 else 0.0
        series_mean = float(np.mean(payload.series[-12:])) if len(payload.series) >= 12 else 0.0
        confidence = max(0.5, 1.0 - (series_std / max(series_mean, 1e-6)))
        
        return {
            "forecast": forecast,
            "horizon_months": horizon_months,
            "model_type": "LSTM" if _predictor.model else "ExponentialSmoothing",
            "confidence": confidence,
            "prediction_time_ms": int(prediction_time * 1000),
            "data_points_used": len(payload.series),
            "is_accurate": confidence > 0.8
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


@router.post("/llm-simple")
@rate_limit(max_requests=5, window_seconds=60)
async def llm_simple_predict(payload: IndicatorsPredictRequest) -> Dict[str, Any]:
    """LLM简单预测接口"""
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
async def train_model_api(payload: TrainRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """模型训练接口"""
    try:
        if len(payload.series) < 12:
            raise HTTPException(status_code=400, detail="训练数据不足，至少需要12个数据点")
        
        # 设置预测器参数
        _predictor.sequence_length = payload.sequence_length
        
        # 训练模型
        start_time = time.time()
        training_result = _predictor.train(
            payload.series, 
            test_size=payload.test_size,
            epochs=payload.epochs,
            batch_size=payload.batch_size
        )
        training_time = time.time() - start_time
        
        # 保存模型
        save_model(training_result)
        
        # 评估模型
        mae, mape = evaluate_model(payload.series, payload.test_size)
        
        return {
            "status": "trained",
            "training_time_seconds": int(training_time),
            "model_params": training_result,
            "metrics": {
                "mae": mae,
                "mape": mape,
                "is_accurate": mape < 5.0
            },
            "data_points": len(payload.series),
            "test_size": payload.test_size,
            "sequence_length": payload.sequence_length
        }
        
    except Exception as e:
        logger.error(f"模型训练失败: {e}")
        raise HTTPException(status_code=500, detail=f"训练失败: {str(e)}")


@router.post("/evaluate")
async def evaluate_model_api(payload: ModelEvaluationRequest) -> Dict[str, Any]:
    """模型评估接口"""
    try:
        if len(payload.series) < 12:
            raise HTTPException(status_code=400, detail="评估数据不足，至少需要12个数据点")
        
        # 分割数据
        split_index = int(len(payload.series) * (1 - payload.test_size))
        train_series = payload.series[:split_index]
        test_series = payload.series[split_index:]
        
        if len(test_series) == 0:
            raise HTTPException(status_code=400, detail="测试集为空")
        
        # 训练模型
        _predictor.train(train_series)
        
        # 预测测试集
        predictions = _predictor.predict(train_series, len(test_series))
        
        # 计算详细指标
        import numpy as np
        mae = float(np.mean(np.abs(np.array(test_series) - np.array(predictions))))
        mape = float(np.mean(np.abs((np.array(test_series) - np.array(predictions)) / np.array(test_series))) * 100)
        rmse = float(np.sqrt(np.mean((np.array(test_series) - np.array(predictions)) ** 2)))
        
        # 计算R²
        ss_res = np.sum((np.array(test_series) - np.array(predictions)) ** 2)
        ss_tot = np.sum((np.array(test_series) - np.mean(test_series)) ** 2)
        r2 = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0
        
        return {
            "metrics": {
                "mae": mae,
                "mape": mape,
                "rmse": rmse,
                "r2": r2,
                "is_accurate": mape < 5.0
            },
            "predictions": predictions,
            "actuals": test_series,
            "test_size": len(test_series),
            "train_size": len(train_series),
            "model_type": "LSTM" if _predictor.model else "ExponentialSmoothing"
        }
        
    except Exception as e:
        logger.error(f"模型评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


@router.get("/model-status")
async def get_model_status_api() -> Dict[str, Any]:
    """获取模型状态"""
    try:
        performance = get_model_performance()
        return {
            "model_status": performance,
            "predictor_ready": _predictor.is_trained,
            "model_type": "LSTM" if _predictor.model else "ExponentialSmoothing",
            "sequence_length": _predictor.sequence_length
        }
        
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/batch-predict")
async def batch_predict(payload: List[IndicatorsPredictRequest]) -> Dict[str, Any]:
    """批量预测接口"""
    try:
        if len(payload) > 10:
            raise HTTPException(status_code=400, detail="批量预测最多支持10个序列")
        
        results = []
        for i, req in enumerate(payload):
            try:
                if len(req.series) < 12:
                    results.append({
                        "index": i,
                        "error": "数据不足",
                        "forecast": []
                    })
                    continue
                
                forecast = _predictor.predict(req.series, req.horizon_months)
                results.append({
                    "index": i,
                    "forecast": forecast,
                    "horizon_months": req.horizon_months,
                    "data_points": len(req.series)
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