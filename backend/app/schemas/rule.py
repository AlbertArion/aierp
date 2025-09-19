from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# 说明：流程规则模型（最小版），单条件触发


class RuleCondition(BaseModel):
    field: str = Field(..., description="事件字段名")
    op: str = Field(..., description="比较操作：gt/gte/lt/lte/eq/neq/contains")
    value: Any = Field(..., description="阈值或期望值")
    level: str = Field("warning", description="触发时的告警级别")
    solution: Optional[str] = Field(None, description="建议解决方案")


class ProcessRule(BaseModel):
    name: str
    enabled: bool = True
    condition: RuleCondition
    description: Optional[str] = None


