from .base_client import LLMClient
from typing import List, Dict, Any

# 说明：使用大模型对传统模型预测结果进行外部因素修正


def correct_forecast(base_forecast: List[float], text_factors: str) -> Dict[str, Any]:
    client = LLMClient(provider="deepseek")
    prompt = (
        "以下是模型给出的未来预测与外部文本因素，请根据因素给出修正建议，"
        "返回JSON，仅包含corrected数组（与base长度一致）与explain说明。\n"
        f"base: {base_forecast}\n"
        f"factors: {text_factors}"
    )
    result = client.chat(prompt)
    return {"raw": result}


