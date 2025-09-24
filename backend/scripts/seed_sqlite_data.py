#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
向SQLite数据库添加测试数据
"""

import sys
import os
from datetime import date, datetime, timedelta
import random

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.db.mongo import get_db
from backend.app.repository.work_report_repo import WorkReportRepository

async def seed_sqlite_data():
    """向SQLite数据库添加测试数据"""
    print("🚀 开始向SQLite数据库添加测试数据...")
    
    db = get_db()
    repo = WorkReportRepository(db)
    
    # 测试数据
    employees_data = [
        {
            "id": "emp_001",
            "employee_no": "EMP001",
            "name": "张三",
            "position": "高级工程师",
            "department_id": "dept_001",
            "hire_date": "2023-01-15"
        },
        {
            "id": "emp_002", 
            "employee_no": "EMP002",
            "name": "李四",
            "position": "前端工程师",
            "department_id": "dept_001",
            "hire_date": "2023-03-20"
        },
        {
            "id": "emp_003",
            "employee_no": "EMP003", 
            "name": "王五",
            "position": "产品经理",
            "department_id": "dept_002",
            "hire_date": "2023-02-10"
        },
        {
            "id": "emp_004",
            "employee_no": "EMP004",
            "name": "赵六", 
            "position": "运营专员",
            "department_id": "dept_003",
            "hire_date": "2023-04-05"
        },
        {
            "id": "emp_005",
            "employee_no": "EMP005",
            "name": "钱七",
            "position": "后端工程师", 
            "department_id": "dept_001",
            "hire_date": "2023-05-12"
        }
    ]
    
    projects_data = [
        {
            "id": "proj_001",
            "project_code": "PROJ001",
            "project_name": "ERP系统开发",
            "project_type": "软件开发"
        },
        {
            "id": "proj_002",
            "project_code": "PROJ002", 
            "project_name": "数据分析平台",
            "project_type": "数据分析"
        },
        {
            "id": "proj_003",
            "project_code": "PROJ003",
            "project_name": "移动应用开发",
            "project_type": "移动开发"
        },
        {
            "id": "proj_004",
            "project_code": "PROJ004",
            "project_name": "AI智能助手",
            "project_type": "人工智能"
        },
        {
            "id": "proj_005",
            "project_code": "PROJ005",
            "project_name": "用户管理系统",
            "project_type": "系统开发"
        }
    ]
    
    departments_data = [
        {
            "id": "dept_001",
            "department_code": "TECH",
            "department_name": "技术部",
            "level": 1,
            "sort_order": 1
        },
        {
            "id": "dept_002",
            "department_code": "PROD",
            "department_name": "产品部", 
            "level": 1,
            "sort_order": 2
        },
        {
            "id": "dept_003",
            "department_code": "OPS",
            "department_name": "运营部",
            "level": 1,
            "sort_order": 3
        }
    ]
    
    # 添加员工数据
    print("📝 添加员工数据...")
    for emp_data in employees_data:
        try:
            await repo.create_employee(emp_data)
            print(f"  ✅ 员工: {emp_data['name']}")
        except Exception as e:
            print(f"  ❌ 员工 {emp_data['name']} 添加失败: {e}")
    
    # 添加项目数据
    print("📝 添加项目数据...")
    for proj_data in projects_data:
        try:
            await repo.create_project(proj_data)
            print(f"  ✅ 项目: {proj_data['project_name']}")
        except Exception as e:
            print(f"  ❌ 项目 {proj_data['project_name']} 添加失败: {e}")
    
    # 添加部门数据
    print("📝 添加部门数据...")
    for dept_data in departments_data:
        try:
            await repo.create_department(dept_data)
            print(f"  ✅ 部门: {dept_data['department_name']}")
        except Exception as e:
            print(f"  ❌ 部门 {dept_data['department_name']} 添加失败: {e}")
    
    # 添加报工记录
    print("📝 添加报工记录...")
    work_contents = [
        "系统架构设计", "前端页面开发", "后端API开发", "数据库设计",
        "单元测试编写", "代码审查", "需求分析", "用户界面设计",
        "性能优化", "bug修复", "文档编写", "项目会议",
    ]
    
    work_locations = ["办公室", "会议室", "客户现场", "远程办公"]
    
    start_date = date.today() - timedelta(days=30)
    
    for i in range(20):  # 创建20条报工记录
        employee = random.choice(employees_data)
        project = random.choice(projects_data)
        
        # 随机生成日期
        report_date = start_date + timedelta(days=random.randint(0, 29))
        
        # 随机生成工作时长
        work_hours = round(random.uniform(4.0, 10.0), 1)
        
        # 随机选择工作内容和地点
        work_content = random.choice(work_contents)
        work_location = random.choice(work_locations)
        
        # 随机选择状态
        status = random.choice(['pending', 'approved', 'rejected'])
        
        work_report_data = {
            "employee_id": employee["id"],
            "project_id": project["id"],
            "department_id": employee["department_id"],
            "report_date": report_date.isoformat(),
            "work_hours": work_hours,
            "work_content": f"{work_content} - {project['project_name']}项目",
            "work_location": work_location,
            "status": status
        }
        
        try:
            await repo.create_work_report(work_report_data)
            print(f"  ✅ 报工记录 {i+1}: {employee['name']} - {project['project_name']} ({work_hours}h)")
        except Exception as e:
            print(f"  ❌ 报工记录 {i+1} 添加失败: {e}")
    
    # 显示统计信息
    try:
        stats = await repo.get_work_report_statistics()
        print(f"\n📊 数据添加完成:")
        print(f"  总报工记录: {stats['total_reports']}")
        print(f"  总工作时长: {stats['total_hours']:.1f} 小时")
        print(f"  平均工作时长: {stats['avg_hours']:.1f} 小时")
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")
    
    print("\n✅ SQLite测试数据添加完成！")
    print("🌐 现在可以访问前端页面查看报工智能体功能")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_sqlite_data())

