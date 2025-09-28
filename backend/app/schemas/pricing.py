"""
核价相关数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ComplexityLevel(str, Enum):
    """复杂度等级"""
    SIMPLE = "简单"
    MEDIUM = "中等"
    COMPLEX = "复杂"


class PricingStatus(str, Enum):
    """核价状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MaterialData(BaseModel):
    """物料数据"""
    id: Optional[str] = None
    material_code: str = Field(..., description="物料编码")
    material_name: str = Field(..., description="物料名称")
    specification: str = Field(..., description="规格型号")
    quantity: int = Field(..., description="数量", gt=0)
    unit: str = Field(..., description="单位")
    complexity: ComplexityLevel = Field(..., description="复杂度等级")
    process_requirements: List[str] = Field(..., description="工艺要求")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PricingResult(BaseModel):
    """核价结果"""
    id: Optional[str] = None
    material_code: str = Field(..., description="物料编码")
    material_name: str = Field(..., description="物料名称")
    specification: str = Field(..., description="规格型号")
    quantity: int = Field(..., description="数量")
    unit: str = Field(..., description="单位")
    internal_cost: float = Field(..., description="内部制造成本", ge=0)
    external_cost: float = Field(..., description="外协加工成本", ge=0)
    cost_difference: float = Field(..., description="成本差异")
    recommendation: str = Field(..., description="建议")
    status: PricingStatus = Field(default=PricingStatus.PENDING, description="状态")
    approval_time: Optional[datetime] = None
    approved_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchPricingRequest(BaseModel):
    """批量核价请求"""
    materials: List[MaterialData] = Field(..., description="物料列表")
    pricing_rules: Optional[Dict[str, Any]] = Field(default=None, description="核价规则")


class BatchPricingResponse(BaseModel):
    """批量核价响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: List[PricingResult] = Field(..., description="核价结果列表")
    total_count: int = Field(..., description="总数量")
    processing_time: Optional[float] = Field(default=None, description="处理时间(秒)")


class PricingStatistics(BaseModel):
    """核价统计信息"""
    total_materials: int = Field(..., description="总物料数")
    approved_count: int = Field(..., description="已确认数量")
    pending_count: int = Field(..., description="待确认数量")
    rejected_count: int = Field(..., description="已拒绝数量")
    total_savings: float = Field(..., description="总节省成本")
    avg_cost_difference: float = Field(..., description="平均成本差异")


class PricingRule(BaseModel):
    """核价规则"""
    id: Optional[str] = None
    rule_name: str = Field(..., description="规则名称")
    rule_type: str = Field(..., description="规则类型")
    conditions: Dict[str, Any] = Field(..., description="规则条件")
    actions: Dict[str, Any] = Field(..., description="规则动作")
    priority: int = Field(default=1, description="优先级")
    is_active: bool = Field(default=True, description="是否启用")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PricingHistory(BaseModel):
    """核价历史记录"""
    id: Optional[str] = None
    batch_id: str = Field(..., description="批次ID")
    material_code: str = Field(..., description="物料编码")
    material_name: str = Field(..., description="物料名称")
    internal_cost: float = Field(..., description="内部成本")
    external_cost: float = Field(..., description="外协成本")
    final_decision: str = Field(..., description="最终决策")
    decision_reason: Optional[str] = Field(default=None, description="决策原因")
    created_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ExcelUploadResponse(BaseModel):
    """Excel上传响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: List[MaterialData] = Field(..., description="解析的物料数据")
    error_rows: Optional[List[int]] = Field(default=None, description="错误行号")


class PricingSaveRequest(BaseModel):
    """保存核价结果请求"""
    results: List[PricingResult] = Field(..., description="核价结果列表")
    batch_name: Optional[str] = Field(default=None, description="批次名称")
    notes: Optional[str] = Field(default=None, description="备注")


class PricingSaveResponse(BaseModel):
    """保存核价结果响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    saved_count: int = Field(..., description="保存数量")
    batch_id: Optional[str] = Field(default=None, description="批次ID")
