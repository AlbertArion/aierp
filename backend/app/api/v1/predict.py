from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any, Dict, List
from ...models.train.lstm_predictor import predict_lstm, train_model, save_model, load_model, evaluate_model
from ...utils.llm.predict_correction import correct_forecast
from fastapi import HTTPException, Request

# 说明：指标预测模块接口，占位实现

router = APIRouter()


class IndicatorsPredictRequest(BaseModel):
    series: List[float] = Field(..., description="历史营收/利润率序列")
    horizon_months: int = Field(1, ge=1, le=6, description="预测月份范围")


class WithFactorsRequest(BaseModel):
    base_forecast: List[float]
    text_factors: str = Field(..., description="外部文本因素，例如‘9月有促销活动’")


@router.post("/indicators")
async def indicators_predict(payload: IndicatorsPredictRequest) -> Dict[str, Any]:
    model = load_model()
    forecast = predict_lstm(payload.series, payload.horizon_months, model)
    return {"forecast": forecast}


@router.post("/with-factors")
async def predict_with_factors(payload: WithFactorsRequest) -> Dict[str, Any]:
    result = correct_forecast(payload.base_forecast, payload.text_factors)
    return result


@router.post("/llm-simple")
async def llm_simple(payload: IndicatorsPredictRequest, request: Request) -> Dict[str, Any]:
    # 简单限流兜底：若全局限流触发则返回静态提示（由中间件统一处理429）。
    # 这里提供额外fallback，保障前端交互稳定。
    try:
        months = min(3, payload.horizon_months)
        return {"forecast": [0.0] * months, "note": "llm simple placeholder"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="llm simple temporarily unavailable") from e


class TrainRequest(BaseModel):
    series: List[float]
    eval_horizon: int = 1


@router.post("/train")
async def train(payload: TrainRequest) -> Dict[str, Any]:
    model = train_model(payload.series)
    save_model(model)
    metrics = evaluate_model(payload.series, payload.eval_horizon, model)
    return {"model": model, "metrics": metrics}


