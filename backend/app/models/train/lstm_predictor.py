from typing import List, Dict, Any, Optional
import json
import os

# 说明：训练/评估/预测最小实现
# - 若可用TensorFlow则可扩展为真实LSTM；当前默认使用指数平滑作为回退


CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
DEFAULT_MODEL_PATH = os.path.join(CHECKPOINT_DIR, "model.json")


def _exp_smooth(series: List[float], alpha: float = 0.5) -> List[float]:
    if not series:
        return []
    s = series[0]
    smoothed = [s]
    for x in series[1:]:
        s = alpha * x + (1 - alpha) * s
        smoothed.append(s)
    return smoothed


def predict_lstm(history_series: List[float], horizon_months: int, model: Optional[Dict[str, Any]] = None) -> List[float]:
    # 回退：使用指数平滑的末值外推
    if not history_series:
        return [0.0 for _ in range(horizon_months)]
    alpha = 0.5
    if model and isinstance(model, dict):
        alpha = float(model.get("alpha", alpha))
    smoothed = _exp_smooth(history_series, alpha)
    last = smoothed[-1]
    return [last for _ in range(horizon_months)]


def train_model(series: List[float]) -> Dict[str, Any]:
    # 最小训练：网格搜索alpha以最小化1步MAPE
    if len(series) < 3:
        return {"type": "exp_smooth", "alpha": 0.5}
    best_alpha = 0.5
    best_mape = 1e9
    for alpha in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        smoothed = _exp_smooth(series[:-1], alpha)
        if not smoothed:
            continue
        pred = smoothed[-1]
        actual = series[-1]
        denom = max(1e-6, abs(actual))
        mape = abs(actual - pred) / denom
        if mape < best_mape:
            best_mape = mape
            best_alpha = alpha
    return {"type": "exp_smooth", "alpha": best_alpha}


def evaluate_model(series: List[float], horizon: int, model: Dict[str, Any]) -> Dict[str, Any]:
    # 简化评估：最后horizon步做naive回测（滚动外推last）
    if horizon <= 0 or len(series) <= horizon:
        return {"mape": None, "mae": None}
    train = series[:-horizon]
    actuals = series[-horizon:]
    preds = predict_lstm(train, horizon, model)
    abs_errors = [abs(a - p) for a, p in zip(actuals, preds)]
    mae = sum(abs_errors) / len(abs_errors)
    mape_items = [abs(a - p) / max(1e-6, abs(a)) for a, p in zip(actuals, preds)]
    mape = sum(mape_items) / len(mape_items)
    return {"mae": mae, "mape": mape, "preds": preds, "actuals": actuals}


def save_model(model: Dict[str, Any], path: str = DEFAULT_MODEL_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model, f)


def load_model(path: str = DEFAULT_MODEL_PATH) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


