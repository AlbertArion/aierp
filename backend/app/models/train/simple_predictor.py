"""
简化的预测器，不依赖TensorFlow
使用指数平滑和简单统计方法进行时间序列预测
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import numpy as np

logger = logging.getLogger(__name__)

class SimpleTimeSeriesPredictor:
    """
    简化的时间序列预测器，使用指数平滑和统计方法
    """
    
    def __init__(self):
        self.is_trained = False
        self.model_params = None
        
    def train(self, series: List[float], test_size: float = 0.2) -> Dict[str, Any]:
        """训练预测器"""
        try:
            if len(series) < 6:
                return {"is_trained": False, "error": "数据不足"}
            
            # 使用指数平滑
            model = ExponentialSmoothing(
                series, 
                trend='add', 
                seasonal='add', 
                seasonal_periods=min(12, len(series) // 2)
            )
            fitted_model = model.fit()
            
            # 简单评估
            if len(series) > 6:
                train_series = series[:-3]
                test_series = series[-3:]
                test_model = ExponentialSmoothing(
                    train_series, 
                    trend='add', 
                    seasonal='add', 
                    seasonal_periods=min(12, len(train_series) // 2)
                )
                fitted_test = test_model.fit()
                predictions = fitted_test.forecast(len(test_series))
                
                mae = np.mean(np.abs(np.array(test_series) - predictions))
                mape = np.mean(np.abs((np.array(test_series) - predictions) / np.array(test_series))) * 100
            else:
                mae = 0.0
                mape = 0.0
            
            self.model_params = {
                "model_type": "ExponentialSmoothing",
                "alpha": float(fitted_model.params.get('smoothing_level', 0.5)),
                "mae": float(mae),
                "mape": float(mape),
                "is_accurate": mape < 5.0
            }
            self.is_trained = True
            
            return self.model_params
            
        except Exception as e:
            logger.error(f"训练失败: {e}")
            return {"is_trained": False, "error": str(e)}
    
    def predict(self, series: List[float], horizon_months: int) -> List[float]:
        """进行预测"""
        try:
            if not series:
                return [0.0] * horizon_months
            
            # 使用指数平滑预测
            model = ExponentialSmoothing(series, trend='add', seasonal=None)
            fit_model = model.fit()
            forecast = fit_model.forecast(horizon_months)
            return forecast.tolist()
            
        except Exception as e:
            logger.error(f"预测失败: {e}")
            # 回退到简单方法
            if series:
                last_value = series[-1]
                return [last_value] * horizon_months
            return [0.0] * horizon_months
    
    def evaluate(self, series: List[float], test_size: float = 0.2) -> Dict[str, Any]:
        """评估模型"""
        try:
            if len(series) < 6:
                return {"mae": 0.0, "mape": 0.0, "is_accurate": False}
            
            # 分割数据
            split_index = int(len(series) * (1 - test_size))
            train_series = series[:split_index]
            test_series = series[split_index:]
            
            if len(test_series) == 0:
                return {"mae": 0.0, "mape": 0.0, "is_accurate": False}
            
            # 训练和预测
            self.train(train_series)
            predictions = self.predict(train_series, len(test_series))
            
            # 计算指标
            mae = np.mean(np.abs(np.array(test_series) - np.array(predictions)))
            mape = np.mean(np.abs((np.array(test_series) - np.array(predictions)) / np.array(test_series))) * 100
            
            return {
                "mae": float(mae),
                "mape": float(mape),
                "is_accurate": mape < 5.0,
                "predictions": predictions,
                "actuals": test_series
            }
            
        except Exception as e:
            logger.error(f"评估失败: {e}")
            return {"mae": 0.0, "mape": 0.0, "is_accurate": False, "error": str(e)}


# 全局预测器实例
_predictor = SimpleTimeSeriesPredictor()


def predict_simple(series: List[float], horizon_months: int) -> List[float]:
    """简单预测函数"""
    return _predictor.predict(series, horizon_months)


def train_simple_model(series: List[float], test_size: float = 0.2) -> Dict[str, Any]:
    """训练简单模型"""
    return _predictor.train(series, test_size)


def evaluate_simple_model(series: List[float], test_size: float = 0.2) -> Dict[str, Any]:
    """评估简单模型"""
    return _predictor.evaluate(series, test_size)


def get_simple_model_status() -> Dict[str, Any]:
    """获取简单模型状态"""
    return {
        "model_type": "Simple",
        "is_trained": _predictor.is_trained,
        "model_params": _predictor.model_params,
        "available": True
    }
