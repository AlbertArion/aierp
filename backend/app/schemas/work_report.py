# backend/app/schemas/work_report.py
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Dict, Any
from enum import Enum

class WorkReportStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class WorkReportBase(BaseModel):
    employee_id: str = Field(..., description="员工ID")
    project_id: str = Field(..., description="项目ID")
    department_id: str = Field(..., description="部门ID")
    report_date: date = Field(..., description="报工日期")
    work_hours: float = Field(..., ge=0, le=24, description="工作时长")
    work_content: Optional[str] = Field(None, description="工作内容")
    work_location: Optional[str] = Field(None, description="工作地点")
    status: WorkReportStatus = Field(WorkReportStatus.PENDING, description="状态")

class WorkReportCreate(WorkReportBase):
    pass

class WorkReportUpdate(BaseModel):
    work_hours: Optional[float] = Field(None, ge=0, le=24)
    work_content: Optional[str] = None
    work_location: Optional[str] = None
    status: Optional[WorkReportStatus] = None

class WorkReportResponse(WorkReportBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    # 关联信息
    employee_name: Optional[str] = None
    project_name: Optional[str] = None
    department_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class WorkReportSearchRequest(BaseModel):
    keyword: Optional[str] = Field(None, description="搜索关键字")
    employee_name: Optional[str] = Field(None, description="员工姓名")
    project_name: Optional[str] = Field(None, description="项目名称")
    department_name: Optional[str] = Field(None, description="部门名称")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    status: Optional[WorkReportStatus] = Field(None, description="状态")
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")

class EmployeeBase(BaseModel):
    employee_no: str = Field(..., description="员工编号")
    name: str = Field(..., description="员工姓名")
    pinyin: Optional[str] = Field(None, description="姓名拼音")
    phone: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    position: Optional[str] = Field(None, description="职位")
    department_id: Optional[str] = Field(None, description="部门ID")
    hire_date: Optional[date] = Field(None, description="入职日期")

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeResponse(EmployeeBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    project_code: str = Field(..., description="项目编码")
    project_name: str = Field(..., description="项目名称")
    project_type: Optional[str] = Field(None, description="项目类型")
    manager_id: Optional[str] = Field(None, description="项目经理ID")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    description: Optional[str] = Field(None, description="项目描述")

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DepartmentBase(BaseModel):
    department_code: str = Field(..., description="部门编码")
    department_name: str = Field(..., description="部门名称")
    parent_id: Optional[str] = Field(None, description="上级部门ID")
    manager_id: Optional[str] = Field(None, description="部门经理ID")
    level: int = Field(1, description="部门层级")
    sort_order: int = Field(0, description="排序")

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
