from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import date

class SAPAIQueryRequest(BaseModel):
    """SAP AI查询请求"""
    query: str = Field(..., description="用户查询语句")
    size: int = Field(20, ge=1, le=100, description="返回结果数量")

class SAPAIQueryResponse(BaseModel):
    """SAP AI查询响应"""
    success: bool = Field(..., description="查询是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="查询结果数据")
    message: Optional[str] = Field(None, description="响应消息")

class SAPQueryResult(BaseModel):
    """SAP查询结果"""
    explanation: str = Field(..., description="查询结果的语言描述")
    rows: List[Dict[str, Any]] = Field(..., description="查询结果数据行")
    tableType: str = Field(..., description="表格类型：work或sap")
    sql: Optional[str] = Field(None, description="执行的SQL语句")
    queryType: str = Field(..., description="查询类型：order_info, material_info, process_info, status_info, summary")

class AIQueryAnalysis(BaseModel):
    """AI查询分析结果"""
    intent: str = Field(..., description="用户意图")
    queryType: str = Field(..., description="查询类型")
    extractedParams: Dict[str, Any] = Field(..., description="提取的参数")
    sqlTemplate: str = Field(..., description="SQL模板")
    confidence: float = Field(..., description="置信度")
