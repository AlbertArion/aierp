from enum import Enum
from pydantic import BaseModel

# 说明：模型切换配置，支持简单模型与大模型动态切换


class PredictBackend(str, Enum):
    simple = "simple"  # 简单统计模型
    llm = "llm"  # 大模型直接预测/修正


class ModelSwitch(BaseModel):
    predict_backend: PredictBackend = PredictBackend.llm


global_switch = ModelSwitch()


def get_model_status() -> dict:
    """获取当前模型状态"""
    return {
        "current_backend": global_switch.predict_backend.value,
        "available_backends": [backend.value for backend in PredictBackend],
        "recommended": "llm"
    }


