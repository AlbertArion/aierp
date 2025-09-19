from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# 说明：流程监管-报警数据模型（用于请求/响应校验）


class ProcessAlert(BaseModel):
    level: str = Field(..., description="告警级别：info/warning/error/critical")
    message: str = Field(..., description="告警信息")
    solution: Optional[str] = Field(None, description="建议解决方案")
    source: Optional[str] = Field(None, description="来源模块，如order-sync")
    created_at: Optional[float] = Field(None, description="Unix时间戳")
    extra: Optional[Dict[str, Any]] = None


