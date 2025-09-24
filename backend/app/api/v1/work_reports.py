# backend/app/api/v1/work_reports.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from typing import Optional, List, Dict, Any
from datetime import date
import logging
import pandas as pd
import io
import re

from ...schemas.work_report import (
    WorkReportResponse, 
    WorkReportSearchRequest,
    WorkReportCreate,
    WorkReportUpdate,
    EmployeeCreate,
    ProjectCreate,
    DepartmentCreate
)
from ...repository.work_report_repo import WorkReportRepository
from ...db.mongo import get_db

router = APIRouter(prefix="/work-reports", tags=["报工管理"])
logger = logging.getLogger(__name__)

@router.get("/search")
async def search_work_reports(
    keyword: Optional[str] = Query(None, description="搜索关键字"),
    employee_name: Optional[str] = Query(None, description="员工姓名"),
    project_name: Optional[str] = Query(None, description="项目名称"),
    department_name: Optional[str] = Query(None, description="部门名称"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db = Depends(get_db)
):
    """智能搜索报工记录"""
    try:
        repo = WorkReportRepository(db)
        result = await repo.search_work_reports(
            keyword=keyword,
            employee_name=employee_name,
            project_name=project_name,
            department_name=department_name,
            start_date=start_date,
            end_date=end_date,
            status=status,
            page=page,
            size=size
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"搜索报工记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_excel_data(
    data: List[Dict[str, Any]],
    db = Depends(get_db)
):
    """导入Excel数据"""
    try:
        repo = WorkReportRepository(db)
        count = await repo.import_excel_data(data)
        return {
            "success": True,
            "message": f"成功导入 {count} 条记录",
            "count": count
        }
    except Exception as e:
        logger.error(f"导入Excel数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-excel")
async def upload_excel_file(
    file: UploadFile = File(...),
    db = Depends(get_db)
):
    """上传Excel文件并解析导入"""
    try:
        # 检查文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="只支持Excel文件格式")
        
        # 读取文件内容
        content = await file.read()
        
        # 使用pandas读取Excel
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Excel文件解析失败: {str(e)}")
        
        # 转换为字典列表
        data = df.to_dict('records')
        
        # 清理空值
        cleaned_data = []
        for item in data:
            cleaned_item = {k: v for k, v in item.items() if pd.notna(v)}
            if cleaned_item:  # 只添加非空记录
                cleaned_data.append(cleaned_item)
        
        # 导入数据
        repo = WorkReportRepository(db)
        count = await repo.import_excel_data(cleaned_data)
        
        return {
            "success": True,
            "message": f"成功导入 {count} 条记录",
            "count": count,
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传Excel文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_statistics(db = Depends(get_db)):
    """获取报工统计信息"""
    try:
        repo = WorkReportRepository(db)
        stats = await repo.get_work_report_statistics()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_data(
    keyword: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db = Depends(get_db)
):
    """导出数据"""
    try:
        repo = WorkReportRepository(db)
        result = await repo.search_work_reports(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            page=1,
            size=10000  # 导出所有数据
        )
        return {
            "success": True,
            "data": result["data"]
        }
    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=Dict[str, Any])
async def create_work_report(
    work_report: WorkReportCreate,
    db = Depends(get_db)
):
    """创建报工记录"""
    try:
        repo = WorkReportRepository(db)
        work_report_data = work_report.dict()
        report_id = await repo.create_work_report(work_report_data)
        
        return {
            "success": True,
            "message": "报工记录创建成功",
            "id": report_id
        }
    except Exception as e:
        logger.error(f"创建报工记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{report_id}")
async def get_work_report(
    report_id: str,
    db = Depends(get_db)
):
    """获取报工记录详情"""
    try:
        repo = WorkReportRepository(db)
        result = await repo.get_work_report_by_id(report_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="报工记录不存在")
        
        return {
            "success": True,
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报工记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{report_id}")
async def update_work_report(
    report_id: str,
    work_report: WorkReportUpdate,
    db = Depends(get_db)
):
    """更新报工记录"""
    try:
        repo = WorkReportRepository(db)
        update_data = work_report.dict(exclude_unset=True)
        success = await repo.update_work_report(report_id, update_data)
        
        if not success:
            raise HTTPException(status_code=404, detail="报工记录不存在或更新失败")
        
        return {
            "success": True,
            "message": "报工记录更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新报工记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{report_id}")
async def delete_work_report(
    report_id: str,
    db = Depends(get_db)
):
    """删除报工记录"""
    try:
        repo = WorkReportRepository(db)
        success = await repo.delete_work_report(report_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="报工记录不存在")
        
        return {
            "success": True,
            "message": "报工记录删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除报工记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 员工管理接口
@router.post("/employees")
async def create_employee(
    employee: EmployeeCreate,
    db = Depends(get_db)
):
    """创建员工信息"""
    try:
        repo = WorkReportRepository(db)
        employee_data = employee.dict()
        employee_id = await repo.create_employee(employee_data)
        
        return {
            "success": True,
            "message": "员工信息创建成功",
            "id": employee_id
        }
    except Exception as e:
        logger.error(f"创建员工信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 项目管理接口
@router.post("/projects")
async def create_project(
    project: ProjectCreate,
    db = Depends(get_db)
):
    """创建项目信息"""
    try:
        repo = WorkReportRepository(db)
        project_data = project.dict()
        project_id = await repo.create_project(project_data)
        
        return {
            "success": True,
            "message": "项目信息创建成功",
            "id": project_id
        }
    except Exception as e:
        logger.error(f"创建项目信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 部门管理接口
@router.post("/departments")
async def create_department(
    department: DepartmentCreate,
    db = Depends(get_db)
):
    """创建部门信息"""
    try:
        repo = WorkReportRepository(db)
        department_data = department.dict()
        department_id = await repo.create_department(department_data)
        
        return {
            "success": True,
            "message": "部门信息创建成功",
            "id": department_id
        }
    except Exception as e:
        logger.error(f"创建部门信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === AI对话式查询接口 ===
@router.post("/ai-query")
async def ai_query(
    payload: Dict[str, Any],
    db = Depends(get_db)
):
    """
    对话式文本查询报工：
    - 输入自然语言，如："查询AI智能助手项目的报工情况"、"查询王五9月的报工"
    - 输出检索命中的报工表格数据
    """
    try:
        text = str(payload.get("query", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="query不能为空")

        # 规则式轻量解析：提取可能的员工名/项目名/日期范围
        employee_name = None
        project_name = None
        keyword = None
        start_date = None
        end_date = None

        # 提取“项目XXX/XXX项目”
        m = re.search(r"项目([\u4e00-\u9fa5A-Za-z0-9_\-]+)|([\u4e00-\u9fa5A-Za-z0-9_\-]+)项目", text)
        if m:
            project_name = m.group(1) or m.group(2)

        # 提取“查询XXX的报工/XXX报工” => 认为是员工姓名
        m = re.search(r"查询([\u4e00-\u9fa5A-Za-z]{1,6})的?报工", text)
        if m:
            employee_name = m.group(1)

        # 提取“订单/物料/工序”关键词，作为通用keyword
        m = re.findall(r"(订单\S+|物料\S+|工序\S+)", text)
        if m:
            keyword = " ".join(m)
        else:
            # 回退：去除停用词后的剩余词作为keyword
            stop = ["查询", "报工", "情况", "的", "一下", "下", "请", "帮我"]
            tmp = text
            for s in stop:
                tmp = tmp.replace(s, "")
            tmp = tmp.strip()
            if tmp:
                keyword = tmp

        # TODO：可扩展日期解析，这里先不实现复杂中文日期解析

        repo = WorkReportRepository(db)
        result = await repo.search_work_reports(
            keyword=keyword,
            employee_name=employee_name,
            project_name=project_name,
            start_date=start_date,
            end_date=end_date,
            page=int(payload.get("page", 1)),
            size=int(payload.get("size", 20))
        )

        return {
            "success": True,
            "query": text,
            "parsed": {
                "employee_name": employee_name,
                "project_name": project_name,
                "keyword": keyword
            },
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
