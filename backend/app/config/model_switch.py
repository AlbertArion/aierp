from enum import Enum
from pydantic import BaseModel

# 说明：模型切换配置，支持传统模型与大模型动态切换


class PredictBackend(str, Enum):
    traditional = "traditional"  # 传统LSTM等
    llm = "llm"  # 大模型直接预测/修正


class ModelSwitch(BaseModel):
    predict_backend: PredictBackend = PredictBackend.traditional


global_switch = ModelSwitch()


