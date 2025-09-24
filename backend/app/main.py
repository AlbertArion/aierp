from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .middleware.request_id import RequestIdMiddleware
from .middleware.rate_limit import SimpleRateLimit
import logging
from datetime import date, datetime, timedelta
import random

# 说明：FastAPI应用入口，注册路由与中间件

async def init_test_data(memory_db):
    """初始化测试数据"""
    try:
        # 测试数据
        employees = [
            {"id": "emp_001", "name": "张三", "department": "技术部", "department_id": "dept_001", "position": "高级工程师"},
            {"id": "emp_002", "name": "李四", "department": "技术部", "department_id": "dept_001", "position": "前端工程师"},
            {"id": "emp_003", "name": "王五", "department": "产品部", "department_id": "dept_002", "position": "产品经理"},
            {"id": "emp_004", "name": "赵六", "department": "运营部", "department_id": "dept_003", "position": "运营专员"},
            {"id": "emp_005", "name": "钱七", "department": "技术部", "department_id": "dept_001", "position": "后端工程师"},
        ]
        
        projects = [
            {"id": "proj_001", "name": "ERP系统开发", "type": "软件开发"},
            {"id": "proj_002", "name": "数据分析平台", "type": "数据分析"},
            {"id": "proj_003", "name": "移动应用开发", "type": "移动开发"},
            {"id": "proj_004", "name": "AI智能助手", "type": "人工智能"},
            {"id": "proj_005", "name": "用户管理系统", "type": "系统开发"},
        ]
        
        departments = [
            {"id": "dept_001", "name": "技术部", "code": "TECH"},
            {"id": "dept_002", "name": "产品部", "code": "PROD"},
            {"id": "dept_003", "name": "运营部", "code": "OPS"},
        ]
        
        work_contents = [
            "系统架构设计", "前端页面开发", "后端API开发", "数据库设计",
            "单元测试编写", "代码审查", "需求分析", "用户界面设计",
            "性能优化", "bug修复", "文档编写", "项目会议",
        ]
        
        work_locations = ["办公室", "会议室", "客户现场", "远程办公"]
        
        # 添加员工数据
        for emp in employees:
            emp_data = {
                "id": emp["id"],
                "employee_no": emp["id"],
                "name": emp["name"],
                "position": emp["position"],
                "department_id": emp["department_id"],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            memory_db["employees"].append(emp_data)
        
        # 添加项目数据
        for proj in projects:
            proj_data = {
                "id": proj["id"],
                "project_code": proj["id"],
                "project_name": proj["name"],
                "project_type": proj["type"],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            memory_db["projects"].append(proj_data)
        
        # 添加部门数据
        for dept in departments:
            dept_data = {
                "id": dept["id"],
                "department_code": dept["code"],
                "department_name": dept["name"],
                "level": 1,
                "sort_order": 0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            memory_db["departments"].append(dept_data)
        
        # 添加报工记录
        start_date = date.today() - timedelta(days=30)
        
        for i in range(20):  # 创建20条报工记录
            employee = random.choice(employees)
            project = random.choice(projects)
            
            # 随机生成日期
            report_date = start_date + timedelta(days=random.randint(0, 29))
            
            # 随机生成工作时长
            work_hours = round(random.uniform(4.0, 10.0), 1)
            
            # 随机选择工作内容和地点
            work_content = random.choice(work_contents)
            work_location = random.choice(work_locations)
            
            # 随机选择状态
            status = random.choice(['pending', 'approved', 'rejected'])
            
            work_report = {
                "id": f"wr_{i+1:03d}",
                "employee_id": employee["id"],
                "project_id": project["id"],
                "department_id": employee["department_id"],
                "report_date": report_date,
                "work_hours": work_hours,
                "work_content": f"{work_content} - {project['name']}项目",
                "work_location": work_location,
                "status": status,
                "employee_name": employee["name"],
                "project_name": project["name"],
                "department_name": employee["department"],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            memory_db["work_reports"].append(work_report)
        
        logging.info(f"测试数据初始化完成: {len(memory_db['work_reports'])} 条报工记录")
        
    except Exception as e:
        logging.error(f"初始化测试数据失败: {e}")

def create_app() -> FastAPI:
    app = FastAPI(title="AI ERP Backend", version="0.1.0")

    # CORS配置：前后端分离，允许本地开发端口访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求ID与开发环境全局限流（可按需调整limit）
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SimpleRateLimit, limit_per_minute=120)

    # 路由注册
    from .api.routes import register_routes
    register_routes(app)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    # 启动时初始化测试数据（仅当使用内存数据库时）
    @app.on_event("startup")
    async def startup_event():
        from .db.mongo import get_memory_db
        memory_db = get_memory_db()
        
        # 检查是否已有数据
        if len(memory_db["work_reports"]) == 0:
            logging.info("初始化报工智能体测试数据...")
            await init_test_data(memory_db)

    return app


app = create_app()


