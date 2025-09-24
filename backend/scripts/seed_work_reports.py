#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
报工数据初始化脚本
用于创建示例报工数据，方便测试报工智能体功能
"""

import asyncio
import sys
import os
from datetime import date, datetime, timedelta
import random

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongo import get_db
from app.repository.work_report_repo import WorkReportRepository

# 示例数据
EMPLOYEES = [
    {"id": "emp001", "employee_no": "E001", "name": "张三", "pinyin": "zhangsan", "department_id": "dept001"},
    {"id": "emp002", "employee_no": "E002", "name": "李四", "pinyin": "lisi", "department_id": "dept001"},
    {"id": "emp003", "employee_no": "E003", "name": "王五", "pinyin": "wangwu", "department_id": "dept002"},
    {"id": "emp004", "employee_no": "E004", "name": "赵六", "pinyin": "zhaoliu", "department_id": "dept002"},
    {"id": "emp005", "employee_no": "E005", "name": "钱七", "pinyin": "qianqi", "department_id": "dept003"},
]

PROJECTS = [
    {"id": "proj001", "project_code": "P001", "project_name": "ERP系统开发", "project_type": "软件开发"},
    {"id": "proj002", "project_code": "P002", "project_name": "数据分析平台", "project_type": "数据分析"},
    {"id": "proj003", "project_code": "P003", "project_name": "移动应用开发", "project_type": "移动开发"},
    {"id": "proj004", "project_code": "P004", "project_name": "AI智能助手", "project_type": "人工智能"},
]

DEPARTMENTS = [
    {"id": "dept001", "department_code": "D001", "department_name": "技术部", "level": 1},
    {"id": "dept002", "department_code": "D002", "department_name": "产品部", "level": 1},
    {"id": "dept003", "department_code": "D003", "department_name": "运营部", "level": 1},
]

WORK_CONTENTS = [
    "系统架构设计",
    "前端页面开发",
    "后端API开发",
    "数据库设计",
    "单元测试编写",
    "代码审查",
    "需求分析",
    "用户界面设计",
    "性能优化",
    "bug修复",
    "文档编写",
    "项目会议",
    "技术调研",
    "部署上线",
    "用户培训",
]

WORK_LOCATIONS = [
    "办公室",
    "会议室",
    "客户现场",
    "远程办公",
    "实验室",
]

async def create_sample_data():
    """创建示例数据"""
    try:
        # 获取数据库连接
        db = get_db()
        repo = WorkReportRepository(db)
        
        print("🚀 开始创建报工示例数据...")
        
        # 1. 创建员工数据
        print("📝 创建员工数据...")
        for employee in EMPLOYEES:
            try:
                await repo.create_employee(employee)
                print(f"  ✅ 员工 {employee['name']} 创建成功")
            except Exception as e:
                print(f"  ⚠️  员工 {employee['name']} 可能已存在: {e}")
        
        # 2. 创建项目数据
        print("📝 创建项目数据...")
        for project in PROJECTS:
            try:
                await repo.create_project(project)
                print(f"  ✅ 项目 {project['project_name']} 创建成功")
            except Exception as e:
                print(f"  ⚠️  项目 {project['project_name']} 可能已存在: {e}")
        
        # 3. 创建部门数据
        print("📝 创建部门数据...")
        for department in DEPARTMENTS:
            try:
                await repo.create_department(department)
                print(f"  ✅ 部门 {department['department_name']} 创建成功")
            except Exception as e:
                print(f"  ⚠️  部门 {department['department_name']} 可能已存在: {e}")
        
        # 4. 创建报工记录
        print("📝 创建报工记录...")
        work_reports = []
        
        # 生成过去30天的报工记录
        start_date = date.today() - timedelta(days=30)
        
        for i in range(100):  # 创建100条报工记录
            # 随机选择员工、项目、部门
            employee = random.choice(EMPLOYEES)
            project = random.choice(PROJECTS)
            department = random.choice(DEPARTMENTS)
            
            # 随机生成日期（过去30天内）
            report_date = start_date + timedelta(days=random.randint(0, 29))
            
            # 随机生成工作时长（4-10小时）
            work_hours = round(random.uniform(4.0, 10.0), 1)
            
            # 随机选择工作内容和地点
            work_content = random.choice(WORK_CONTENTS)
            work_location = random.choice(WORK_LOCATIONS)
            
            # 随机选择状态
            status = random.choice(['pending', 'approved', 'rejected'])
            
            work_report = {
                "employee_id": employee["id"],
                "project_id": project["id"],
                "department_id": department["id"],
                "employee_name": employee["name"],
                "project_name": project["project_name"],
                "department_name": department["department_name"],
                "report_date": report_date,
                "work_hours": work_hours,
                "work_content": work_content,
                "work_location": work_location,
                "status": status,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            work_reports.append(work_report)
        
        # 批量插入报工记录
        try:
            count = await repo.import_excel_data(work_reports)
            print(f"  ✅ 成功创建 {count} 条报工记录")
        except Exception as e:
            print(f"  ❌ 创建报工记录失败: {e}")
        
        # 5. 显示统计信息
        print("\n📊 数据统计:")
        stats = await repo.get_work_report_statistics()
        print(f"  总报工记录: {stats.get('total_reports', 0)}")
        print(f"  总工作时长: {stats.get('total_hours', 0):.1f} 小时")
        print(f"  平均工作时长: {stats.get('avg_hours', 0):.1f} 小时")
        
        print("\n✅ 报工示例数据创建完成！")
        print("🌐 现在可以访问前端页面 /work-report-agent 查看报工智能体功能")
        
    except Exception as e:
        print(f"❌ 创建示例数据失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("=" * 60)
    print("🎯 AI ERP 报工智能体 - 示例数据初始化")
    print("=" * 60)
    
    await create_sample_data()

if __name__ == "__main__":
    asyncio.run(main())
