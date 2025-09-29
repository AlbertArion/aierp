import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

# 尝试导入statsmodels，如果失败则使用备选方案
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logging.warning("statsmodels未安装，将使用简化的预测方法")

from ...utils.llm.base_client import LLMClient

logger = logging.getLogger(__name__)

class LLMTimeSeriesPredictor:
    """
    基于LLM的时间序列预测器，使用Qwen-Max-Latest等大模型进行预测
    """
    
    def __init__(self, provider: str = "qwen", model: str = "qwen-max-latest"):
        self.client = LLMClient(provider=provider)
        self.model = model
        self.use_real_llm = os.getenv("USE_REAL_LLM", "false").lower() == "true"
        
    def _build_prediction_prompt(self, series: List[float], horizon_months: int, 
                               context: str = "", factors: List[str] = None) -> str:
        """构建LLM预测提示词"""
        
        # 数据趋势分析
        if len(series) >= 3:
            recent_trend = "上升" if series[-1] > series[-2] > series[-3] else "下降" if series[-1] < series[-2] < series[-3] else "波动"
            volatility = "高" if max(series) - min(series) > sum(series) / len(series) * 0.3 else "低"
        else:
            recent_trend = "未知"
            volatility = "未知"
            
        # 构建数据描述
        data_description = f"""
历史数据序列（共{len(series)}个数据点）：
{json.dumps(series, ensure_ascii=False, indent=2)}

数据特征：
- 最近趋势：{recent_trend}
- 波动性：{volatility}
- 数据范围：{min(series):.2f} - {max(series):.2f}
- 平均值：{sum(series)/len(series):.2f}
"""
        
        # 外部因素
        factors_text = ""
        if factors:
            factors_text = f"\n外部影响因素：\n" + "\n".join([f"- {factor}" for factor in factors])
        
        # 上下文信息
        context_text = f"\n业务上下文：{context}" if context else ""
        
        prompt = f"""
你是一个专业的时间序列预测专家。请基于以下历史数据，预测未来{horizon_months}个月的趋势。

{data_description}{context_text}{factors_text}

请按照以下JSON格式返回预测结果：
{{
    "predictions": [预测值1, 预测值2, ..., 预测值{horizon_months}],
    "confidence": 0.85,
    "trend_analysis": "趋势分析说明",
    "risk_factors": ["风险因素1", "风险因素2"],
    "recommendations": ["建议1", "建议2"],
    "methodology": "使用的预测方法说明"
}}

要求：
1. 预测值应该是合理的数值，与历史数据趋势相符
2. 置信度范围0-1，表示预测的可靠性
3. 提供详细的趋势分析和风险评估
4. 给出实用的业务建议
5. 说明使用的预测方法

请确保返回的是有效的JSON格式。
"""
        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的预测结果"""
        try:
            # 尝试直接解析JSON
            if isinstance(response, dict):
                return response
                
            # 提取JSON部分
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            
            # 如果无法解析JSON，返回默认结构
            return {
                "predictions": [],
                "confidence": 0.5,
                "trend_analysis": "无法解析LLM响应",
                "risk_factors": [],
                "recommendations": [],
                "methodology": "LLM解析失败"
            }
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return {
                "predictions": [],
                "confidence": 0.0,
                "trend_analysis": f"解析错误: {str(e)}",
                "risk_factors": ["数据解析失败"],
                "recommendations": ["请检查数据格式"],
                "methodology": "解析失败"
            }
    
    def predict(self, series: List[float], horizon_months: int, 
                context: str = "", factors: List[str] = None) -> Dict[str, Any]:
        """
        使用LLM进行时间序列预测
        
        Args:
            series: 历史数据序列
            horizon_months: 预测月数
            context: 业务上下文
            factors: 外部影响因素
            
        Returns:
            包含预测结果的字典
        """
        try:
            if not series or len(series) < 3:
                return {
                    "predictions": [series[-1]] * horizon_months if series else [0.0] * horizon_months,
                    "confidence": 0.0,
                    "trend_analysis": "数据不足，无法进行有效预测",
                    "risk_factors": ["历史数据不足"],
                    "recommendations": ["需要更多历史数据"],
                    "methodology": "数据不足回退"
                }
            
            # 构建提示词
            prompt = self._build_prediction_prompt(series, horizon_months, context, factors)
            
            # 调用LLM
            if self.use_real_llm:
                response = self.client.chat(prompt, model=self.model, temperature=0.1)
                llm_result = response.get("completion", "")
            else:
                # 模拟LLM响应
                llm_result = self._generate_mock_prediction(series, horizon_months)
            
            # 解析结果
            result = self._parse_llm_response(llm_result)
            
            # 验证预测结果
            if not result.get("predictions") or len(result["predictions"]) != horizon_months:
                # 如果LLM返回的预测数量不对，使用指数平滑作为备选
                fallback_predictions = self._fallback_prediction(series, horizon_months)
                result["predictions"] = fallback_predictions
                result["methodology"] = "LLM预测失败，使用指数平滑备选"
                result["confidence"] = 0.6
            
            return result
            
        except Exception as e:
            logger.error(f"LLM预测失败: {e}")
            # 回退到指数平滑
            fallback_predictions = self._fallback_prediction(series, horizon_months)
            return {
                "predictions": fallback_predictions,
                "confidence": 0.5,
                "trend_analysis": f"LLM预测失败: {str(e)}",
                "risk_factors": ["LLM服务异常"],
                "recommendations": ["使用传统方法预测"],
                "methodology": "LLM失败回退到指数平滑"
            }
    
    def _generate_mock_prediction(self, series: List[float], horizon_months: int) -> str:
        """生成模拟的LLM预测结果（用于测试）"""
        # 简单的趋势分析
        if len(series) >= 3:
            recent_avg = sum(series[-3:]) / 3
            trend = (series[-1] - series[-3]) / 2
        else:
            recent_avg = series[-1] if series else 0
            trend = 0
        
        # 生成预测值
        predictions = []
        for i in range(1, horizon_months + 1):
            pred_value = recent_avg + trend * i + (i * 0.1 * recent_avg)  # 添加一些随机性
            predictions.append(round(pred_value, 2))
        
        # 分析趋势
        if trend > 0:
            trend_analysis = "数据呈现上升趋势，预计未来将继续增长"
        elif trend < 0:
            trend_analysis = "数据呈现下降趋势，需要关注风险"
        else:
            trend_analysis = "数据相对稳定，预计未来保持平稳"
        
        mock_result = {
            "predictions": predictions,
            "confidence": 0.75,
            "trend_analysis": trend_analysis,
            "risk_factors": ["市场波动", "季节性影响"],
            "recommendations": ["持续监控数据变化", "制定风险应对策略"],
            "methodology": "基于历史趋势的智能分析"
        }
        
        return json.dumps(mock_result, ensure_ascii=False, indent=2)
    
    def _fallback_prediction(self, series: List[float], horizon_months: int) -> List[float]:
        """使用指数平滑作为备选预测方法"""
        try:
            if not series:
                return [0.0] * horizon_months
            
            # 如果statsmodels可用，使用指数平滑
            if STATSMODELS_AVAILABLE:
                model = ExponentialSmoothing(series, trend='add', seasonal=None)
                fit_model = model.fit()
                forecast = fit_model.forecast(horizon_months)
                return forecast.tolist()
            else:
                # 备选方案：使用简单的移动平均和趋势
                return self._simple_trend_prediction(series, horizon_months)
            
        except Exception as e:
            logger.error(f"预测失败: {e}")
            # 最后回退：使用最后一个值
            return [series[-1]] * horizon_months if series else [0.0] * horizon_months
    
    def _simple_trend_prediction(self, series: List[float], horizon_months: int) -> List[float]:
        """简化的趋势预测方法（当statsmodels不可用时使用）"""
        if not series:
            return [0.0] * horizon_months
        
        if len(series) == 1:
            return [series[0]] * horizon_months
        
        # 计算简单移动平均
        if len(series) >= 3:
            recent_avg = sum(series[-3:]) / 3
            # 计算趋势
            trend = (series[-1] - series[-3]) / 2
        else:
            recent_avg = sum(series) / len(series)
            trend = series[-1] - series[0] if len(series) > 1 else 0
        
        # 生成预测值
        predictions = []
        for i in range(1, horizon_months + 1):
            # 基于趋势和移动平均的简单预测
            pred_value = recent_avg + trend * i
            predictions.append(round(pred_value, 2))
        
        return predictions
    
    def train_and_evaluate(self, series: List[float], test_size: float = 0.2) -> Dict[str, Any]:
        """
        训练和评估LLM预测器（实际上LLM不需要训练，这里主要是评估）
        """
        if not series or len(series) < 6:
            return {
                "model_type": "LLM",
                "is_trained": False,
                "error": "数据不足"
            }
        
        # 分割数据
        split_index = int(len(series) * (1 - test_size))
        train_series = series[:split_index]
        test_series = series[split_index:]
        
        if len(test_series) == 0:
            return {
                "model_type": "LLM",
                "is_trained": False,
                "error": "测试数据不足"
            }
        
        # 使用训练数据进行预测
        predictions_result = self.predict(train_series, len(test_series))
        predictions = predictions_result.get("predictions", [])
        
        if not predictions or len(predictions) != len(test_series):
            return {
                "model_type": "LLM",
                "is_trained": False,
                "error": "预测失败"
            }
        
        # 计算评估指标
        import numpy as np
        mae = np.mean(np.abs(np.array(test_series) - np.array(predictions)))
        mape = np.mean(np.abs((np.array(test_series) - np.array(predictions)) / np.array(test_series))) * 100
        
        return {
            "model_type": "LLM",
            "is_trained": True,
            "mae": float(mae),
            "mape": float(mape),
            "confidence": predictions_result.get("confidence", 0.5),
            "methodology": predictions_result.get("methodology", "LLM预测")
        }


# 全局LLM预测器实例
_llm_predictor = LLMTimeSeriesPredictor()


def predict_with_llm(series: List[float], horizon_months: int, 
                     context: str = "", factors: List[str] = None) -> Dict[str, Any]:
    """使用LLM进行预测的便捷函数"""
    return _llm_predictor.predict(series, horizon_months, context, factors)


def train_llm_model(series: List[float], test_size: float = 0.2) -> Dict[str, Any]:
    """训练LLM模型（实际上是评估）"""
    return _llm_predictor.train_and_evaluate(series, test_size)


def get_llm_model_status() -> Dict[str, Any]:
    """获取LLM模型状态"""
    return {
        "model_type": "LLM",
        "provider": _llm_predictor.client.provider,
        "model": _llm_predictor.model,
        "use_real_llm": _llm_predictor.use_real_llm,
        "available": True
    }
