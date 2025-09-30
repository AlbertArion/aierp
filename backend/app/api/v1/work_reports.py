# backend/app/api/v1/work_reports.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
import logging
import pandas as pd
import io
import re
import os

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
    payload: Dict[str, Any]
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
        
        # 添加详细调试日志
        print("=" * 50)
        print(f"🔍 AI查询请求开始")
        print(f"📝 原始查询文本: '{text}'")
        print(f"📦 请求参数: {payload}")
        logger.info("=" * 50)
        logger.info(f"🔍 AI查询请求开始")
        logger.info(f"📝 原始查询文本: '{text}'")
        logger.info(f"📦 请求参数: {payload}")

        # 提取项目名称 - 改进的匹配逻辑
        # 1. 先尝试匹配 "XXX项目" 格式（优先匹配字母项目名）
        m = re.search(r"([A-Za-z]{2,})项目", text)
        if m:
            project_name = m.group(1)
        else:
            # 2. 再尝试匹配中文项目名
            m = re.search(r"([\u4e00-\u9fa5]{2,})项目", text)
            if m:
                project_name = m.group(1)
            else:
                # 3. 最后尝试匹配 "项目XXX" 格式
                m = re.search(r"项目([\u4e00-\u9fa5A-Za-z0-9_\-]+)", text)
                if m:
                    project_name = m.group(1)

        # 提取"查询XXX的报工/XXX报工" => 认为是员工姓名
        print("🔍 开始解析员工姓名...")
        logger.info("🔍 开始解析员工姓名...")
        # 修复正则表达式：允许"查询"和"报工"之间有空格和"的"字
        m = re.search(r"查询\s*([\u4e00-\u9fa5A-Za-z]{1,6})\s*的?\s*报工", text)
        if m:
            employee_name = m.group(1)
            print(f"  ✅ 正则匹配成功: '{employee_name}'")
            logger.info(f"  ✅ 正则匹配成功: '{employee_name}'")
            # 去除可能的"的"字
            if employee_name.endswith('的'):
                employee_name = employee_name[:-1]
                print(f"  🔧 去除'的'字后: '{employee_name}'")
                logger.info(f"  🔧 去除'的'字后: '{employee_name}'")
        else:
            print("  ❌ 正则匹配失败，未找到员工名")
            logger.info("  ❌ 正则匹配失败，未找到员工名")
            # 尝试其他模式
            print("  🔍 尝试其他匹配模式...")
            logger.info("  🔍 尝试其他匹配模式...")
            # 可以添加更多匹配模式

        # 提取"订单/物料/工序"关键词，作为通用keyword
        m = re.findall(r"(订单\S+|物料\S+|工序\S+)", text)
        if m:
            keyword = " ".join(m)
        else:
            # 回退：去除停用词后的剩余词作为keyword
            stop = ["查询", "报工", "情况", "的", "一下", "下", "请", "帮我", "项目"]
            tmp = text
            for s in stop:
                tmp = tmp.replace(s, "")
            # 也要排除已识别的员工名和项目名（避免keyword和employee_name/project_name重复）
            if employee_name:
                tmp = tmp.replace(employee_name, "")
            if project_name:
                tmp = tmp.replace(project_name, "")
            tmp = tmp.strip()
            if tmp:
                keyword = tmp

        # 中文时间短语解析（简化版）：上周/本周/上月/本月/今年/9月/2025-09
        def _first_day_of_this_month(today: date) -> date:
            return today.replace(day=1)

        def _first_day_of_last_month(today: date) -> date:
            first_this = _first_day_of_this_month(today)
            return (first_this - timedelta(days=1)).replace(day=1)

        def _last_day_of_month(some_day: date) -> date:
            next_month = (some_day.replace(day=28) + timedelta(days=4)).replace(day=1)
            return next_month - timedelta(days=1)

        today = date.today()
        lowered = text
        # 上周
        if re.search(r"上周", lowered):
            weekday = today.weekday()  # 0=Mon
            last_sunday = today - timedelta(days=weekday + 1)
            last_monday = last_sunday - timedelta(days=6)
            start_date = last_monday
            end_date = last_sunday
        # 本周
        elif re.search(r"本周|这周", lowered):
            weekday = today.weekday()
            start_date = today - timedelta(days=weekday)
            end_date = start_date + timedelta(days=6)
        # 上月
        elif re.search(r"上月|上个月", lowered):
            first_last = _first_day_of_last_month(today)
            start_date = first_last
            end_date = _last_day_of_month(first_last)
        # 本月
        elif re.search(r"本月|这个月", lowered):
            first_this = _first_day_of_this_month(today)
            start_date = first_this
            end_date = _last_day_of_month(first_this)
        # 今年
        elif re.search(r"今年", lowered):
            start_date = date(today.year, 1, 1)
            end_date = date(today.year, 12, 31)
        else:
            # 形如 “2025-09” 或 “9月/09月”
            m = re.search(r"(20\d{2})-(0?[1-9]|1[0-2])", lowered)
            if m:
                y = int(m.group(1)); mth = int(m.group(2))
                start_date = date(y, mth, 1)
                end_date = _last_day_of_month(start_date)
            else:
                m = re.search(r"(\d{1,2})月", lowered)
                if m:
                    mth = int(m.group(1))
                    y = today.year
                    start_date = date(y, mth, 1)
                    end_date = _last_day_of_month(start_date)

        # 默认近90天
        if not start_date and not end_date:
            end_date = today
            start_date = today - timedelta(days=90)
        
        # 打印解析结果
        logger.info("📊 解析结果:")
        logger.info(f"  👤 员工名: '{employee_name}'")
        logger.info(f"  🏢 项目名: '{project_name}'")
        logger.info(f"  🔍 关键词: '{keyword}'")
        logger.info(f"  📅 开始日期: '{start_date}'")
        logger.info(f"  📅 结束日期: '{end_date}'")

        # 若用户开启LLM并配置了密钥，则优先走LLM function call
        use_llm = os.getenv("USE_LLM_WORKREPORT", "true").lower() == "true"
        openai_api_key = os.getenv("OPENAI_API_KEY", 'sk-c3ddf7d415bb492587f725ec3845a4ce')
        openai_base_url = os.getenv("OPENAI_BASE_URL", 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        openai_model = os.getenv("WORKREPORT_LLM_MODEL", "qwen-max-latest")

        print(f"use_llm: {use_llm}")
        print(f"openai_api_key: {openai_api_key}")
        print(f"openai_base_url: {openai_base_url}")
        print(f"openai_model: {openai_model}")

        rows: List[Dict[str, Any]] = []
        explanation = None

        # 直接使用SQLite数据库（与search接口保持一致）
        from ...db.sqlite_db import get_sqlite_db
        db = get_sqlite_db()
        repo = WorkReportRepository(db)

        # 执行数据库查询
        logger.info("🗄️ 开始数据库查询:")
        logger.info(f"  📊 查询参数: employee_name='{employee_name}', project_name='{project_name}'")
        logger.info(f"  📅 时间范围: {start_date} ~ {end_date}")
        logger.info(f"  🗃️ 数据库类型: {type(db)}")
        logger.info(f"  🔗 数据库实例: {db}")
        
        # === 先判断是否更像"闲聊/说明"而非"数据库查询" ===
        # 规则：未识别到实体/时间/状态，且命中常见闲聊词或句长较短
        def _is_smalltalk(q: str) -> bool:
            smalltalk_patterns = [
                r"^你好$", r"^在吗$", r"^嗨$", r"^hello$", r"^hi$",
                r"帮助", r"说明", r"怎么用", r"示例", r"功能",
            ]
            if any(re.search(p, q.strip(), re.IGNORECASE) for p in smalltalk_patterns):
                return True
            # 无实体且字数很短也视为聊天
            no_entity = not any([employee_name, project_name]) and not any([start_date, end_date, status])
            return no_entity and len(q.strip()) <= 12

        if _is_smalltalk(text):
            explanation = None
            if openai_api_key and openai_base_url:
                try:
                    import requests
                    conv_system = (
                        "你是企业报工助手。用简洁中文回答用户的问候或问题，"
                        "可提示使用方式与示例问法（如：查询王五9月报工/AI智能助手项目上周记录），"
                        "不要编造具体数据或表格。"
                    )
                    resp_chat = requests.post(
                        f"{openai_base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"},
                        json={
                            "model": openai_model,
                            "messages": [
                                {"role": "system", "content": conv_system},
                                {"role": "user", "content": text}
                            ]
                        }, timeout=30
                    )
                    resp_chat.raise_for_status()
                    data_chat = resp_chat.json()
                    explanation = (
                        data_chat.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                except Exception as _e:
                    logger.warning(f"LLM聊天回答失败: {_e}")
            # 无LLM或失败，给默认说明
            if not explanation:
                explanation = (
                    "你好，我是报工智能体。你可以这样问我：1) 查询王五9月报工；"
                    "2) AI智能助手项目上周通过的记录；3) 研发部本月报工汇总。"
                )
            return {
                "success": True,
                "query": text,
                "parsed": {
                    "employee_name": None,
                    "project_name": None,
                    "keyword": None,
                    "start_date": None,
                    "end_date": None
                },
                "data": {"rows": [], "total": 0, "explanation": explanation}
            }

        if use_llm and openai_api_key and openai_base_url:
            try:
                # 尝试使用OpenAI兼容接口（function call）
                import requests
                system_prompt = (
                    "你是一个企业级报工智能体，将中文问题解析为查询参数，并严格使用" \
                    "query_work_reports 函数进行检索，返回简短中文说明与表格行。"
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ]
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "query_work_reports",
                            "description": "查询报工记录",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "employee_name": {"type": "string"},
                                    "project_name": {"type": "string"},
                                    "department_name": {"type": "string"},
                                    "status": {"type": "string", "enum": ["pending","approved","rejected"]},
                                    "start_date": {"type": "string"},
                                    "end_date": {"type": "string"},
                                    "size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
                                },
                                "required": [],
                                "additionalProperties": False
                            }
                        }
                    }
                ]

                resp = requests.post(
                    f"{openai_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"},
                    json={
                        "model": openai_model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto"
                    }, timeout=30
                )
                resp.raise_for_status()
                data_json = resp.json()
                tool_calls = (
                    data_json.get("choices", [{}])[0]
                    .get("message", {})
                    .get("tool_calls", [])
                )
                # 若模型给出函数调用参数，则执行仓储查询
                args: Dict[str, Any] = {}
                if tool_calls:
                    for tc in tool_calls:
                        if tc.get("function", {}).get("name") == "query_work_reports":
                            import json as _json
                            arg_str = tc.get("function", {}).get("arguments", "{}")
                            try:
                                args = _json.loads(arg_str)
                            except Exception:
                                args = {}
                            break

                # 合并规则解析出的时间窗口作为缺省
                if "start_date" not in args and start_date:
                    args["start_date"] = start_date.isoformat()
                if "end_date" not in args and end_date:
                    args["end_date"] = end_date.isoformat()
                size = int(args.get("size", payload.get("size", 20)))

                # 调用仓储
                def _coerce_date(s: Optional[str]) -> Optional[date]:
                    if not s:
                        return None
                    try:
                        return datetime.strptime(s, "%Y-%m-%d").date()
                    except Exception:
                        return None

                result = await repo.search_work_reports(
                    keyword=keyword,
                    employee_name=args.get("employee_name") or employee_name,
                    project_name=args.get("project_name") or project_name,
                    department_name=args.get("department_name"),
                    status=args.get("status"),
                    start_date=_coerce_date(args.get("start_date")) or start_date,
                    end_date=_coerce_date(args.get("end_date")) or end_date,
                    page=1,
                    size=size
                )
                rows = result.get("data", [])
                explanation = (
                    f"已为你筛选：员工={args.get('employee_name') or (employee_name or '未指定')}，"
                    f"项目={args.get('project_name') or (project_name or '未指定')}，"
                    f"时间={ ( (_coerce_date(args.get('start_date')) or start_date).isoformat() if (_coerce_date(args.get('start_date')) or start_date) else '未指定') }"
                    f"~{ ( (_coerce_date(args.get('end_date')) or end_date).isoformat() if (_coerce_date(args.get('end_date')) or end_date) else '未指定') }，"
                    f"共{result.get('total', len(rows))}条结果。"
                )
            except Exception as _e:
                logger.warning(f"LLM调用失败，回退规则解析: {_e}")
                result = await repo.search_work_reports(
                    keyword=keyword,
                    employee_name=employee_name,
                    project_name=project_name,
                    start_date=start_date,
                    end_date=end_date,
                    page=int(payload.get("page", 1)),
                    size=int(payload.get("size", 20))
                )
                rows = result.get("data", [])
        else:
            # 直接规则解析查询
            result = await repo.search_work_reports(
                keyword=keyword,
                employee_name=employee_name,
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                page=int(payload.get("page", 1)),
                size=int(payload.get("size", 20))
            )
            rows = result.get("data", [])

        # 查询结果处理
        logger.info(f"📋 数据库查询完成:")
        logger.info(f"  📊 查询到记录数: {len(rows)}")
        logger.info(f"  📝 记录详情: {[{'id': r.get('id'), 'employee_name': r.get('employee_name'), 'report_date': r.get('report_date')} for r in rows[:3]]}")
        
        # 若无命中记录，走对话式回答兜底（优先用LLM，没有则给出规则建议文案）
        if not rows:
            logger.info("⚠️ 未查询到记录，准备生成解释说明")
            if openai_api_key and openai_base_url:
                try:
                    import requests
                    conv_system = (
                        "你现在扮演企业报工助手。如果没有检索到符合条件的报工数据，"
                        "请根据用户的问题给出友好的说明、可尝试的查询建议（如补充员工/项目/时间），"
                        "并提供1-2条可能有帮助的示例问法。不要捏造数据表格。"
                    )
                    resp2 = requests.post(
                        f"{openai_base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"},
                        json={
                            "model": openai_model,
                            "messages": [
                                {"role": "system", "content": conv_system},
                                {"role": "user", "content": text}
                            ]
                        }, timeout=30
                    )
                    resp2.raise_for_status()
                    data2 = resp2.json()
                    completion = (
                        data2.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                    if completion:
                        explanation = completion
                except Exception as _e:
                    logger.warning(f"LLM无数据对话兜底失败: {_e}")
            # 若LLM不可用或失败，返回默认建议说明
            if not explanation:
                explanation = (
                    "未检索到相关报工记录。建议：1) 指定员工姓名（如：查询王五9月报工）；"
                    "2) 指定项目名称（如：AI智能助手项目上周记录）；3) 指定时间范围（如：2025-09、上周、本月）。"
                )

        # 若用户希望“正常沟通也由大模型作答”，则在返回前优先用LLM生成简短说明
        if openai_api_key and openai_base_url and not explanation:
            try:
                import requests as _rq
                sys_prompt = (
                    "你是企业报工助手，请用简洁中文确认你对用户问题的理解，"
                    "如果可能，点明你将依据的筛选条件（员工/项目/时间/状态），"
                    "并提示‘下方表格为匹配结果’。不要编造数据。"
                )
                parsed_text = (
                    f"员工={employee_name or '未指定'}，项目={project_name or '未指定'}，"
                    f"时间={ (start_date.isoformat() if start_date else '未指定') }~{ (end_date.isoformat() if end_date else '未指定') }。"
                )
                _resp = _rq.post(
                    f"{openai_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"},
                    json={
                        "model": openai_model,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": f"原始问题：{text}\n已解析：{parsed_text}"}
                        ]
                    }, timeout=20
                )
                _resp.raise_for_status()
                _data = _resp.json()
                explanation = (
                    _data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                ) or explanation
            except Exception as _e:
                logger.debug(f"LLM简要说明生成失败: {_e}")

        # 最终响应
        response_data = {
            "success": True,
            "query": text,
            "parsed": {
                "employee_name": employee_name,
                "project_name": project_name,
                "keyword": keyword,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            },
            "data": {
                "rows": rows,
                "total": result.get("total", len(rows)),
                "explanation": explanation
            }
        }
        
        logger.info("✅ 响应数据准备完成:")
        logger.info(f"  📊 成功状态: {response_data['success']}")
        logger.info(f"  📝 解析结果: {response_data['parsed']}")
        logger.info(f"  📋 数据条数: {len(rows)}")
        logger.info(f"  💬 解释说明: {explanation[:100] if explanation else 'None'}...")
        logger.info("=" * 50)
        
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
