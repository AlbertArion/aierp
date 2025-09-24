#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量填充报工数据脚本
为报工智能体添加测试数据
"""

import requests
import json
from datetime import date, datetime, timedelta
import random

# 测试数据 - 模拟真实的报工记录
EMPLOYEES = [
    {"name": "张三", "department": "技术部", "position": "高级工程师"},
    {"name": "李四", "department": "技术部", "position": "前端工程师"},
    {"name": "王五", "department": "产品部", "position": "产品经理"},
    {"name": "赵六", "department": "运营部", "position": "运营专员"},
    {"name": "钱七", "department": "技术部", "position": "后端工程师"},
    {"name": "孙八", "department": "产品部", "position": "UI设计师"},
    {"name": "周九", "department": "运营部", "position": "数据分析师"},
    {"name": "吴十", "department": "技术部", "position": "测试工程师"},
]

PROJECTS = [
    {"name": "ERP系统开发", "type": "软件开发"},
    {"name": "数据分析平台", "type": "数据分析"},
    {"name": "移动应用开发", "type": "移动开发"},
    {"name": "AI智能助手", "type": "人工智能"},
    {"name": "用户管理系统", "type": "系统开发"},
    {"name": "财务管理系统", "type": "系统开发"},
    {"name": "库存管理系统", "type": "系统开发"},
    {"name": "报表系统", "type": "数据可视化"},
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
    "系统维护",
    "功能测试",
    "接口联调",
    "数据迁移",
    "安全加固",
]

WORK_LOCATIONS = [
    "办公室",
    "会议室",
    "客户现场",
    "远程办公",
    "实验室",
    "培训室",
]

def create_test_data():
    """创建测试数据"""
    base_url = "http://localhost:3127/api"
    
    print("🚀 开始创建报工测试数据...")
    
    # 生成过去30天的报工记录
    start_date = date.today() - timedelta(days=30)
    success_count = 0
    error_count = 0
    
    for i in range(50):  # 创建50条报工记录
        # 随机选择员工、项目
        employee = random.choice(EMPLOYEES)
        project = random.choice(PROJECTS)
        
        # 随机生成日期（过去30天内）
        report_date = start_date + timedelta(days=random.randint(0, 29))
        
        # 随机生成工作时长（4-10小时）
        work_hours = round(random.uniform(4.0, 10.0), 1)
        
        # 随机选择工作内容和地点
        work_content = random.choice(WORK_CONTENTS)
        work_location = random.choice(WORK_LOCATIONS)
        
        # 随机选择状态
        status = random.choice(['pending', 'approved', 'rejected'])
        
        # 构建请求数据
        data = {
            "employee_id": f"emp_{i+1:03d}",
            "project_id": f"proj_{i+1:03d}",
            "department_id": f"dept_{employee['department']}",
            "report_date": report_date.strftime('%Y-%m-%d'),
            "work_hours": work_hours,
            "work_content": f"{work_content} - {project['name']}项目",
            "work_location": work_location,
            "status": status
        }
        
        try:
            response = requests.post(f"{base_url}/work-reports/", json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    success_count += 1
                    print(f"  ✅ 创建记录 {i+1}: {employee['name']} - {project['name']} ({work_hours}h)")
                else:
                    error_count += 1
                    print(f"  ❌ 创建记录 {i+1} 失败: {result.get('message', '未知错误')}")
            else:
                error_count += 1
                print(f"  ❌ 创建记录 {i+1} 失败: HTTP {response.status_code}")
        except Exception as e:
            error_count += 1
            print(f"  ❌ 创建记录 {i+1} 失败: {e}")
    
    print(f"\n📊 创建结果:")
    print(f"  成功: {success_count} 条")
    print(f"  失败: {error_count} 条")
    
    # 检查统计信息
    try:
        response = requests.get(f"{base_url}/work-reports/statistics", timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                stats = result.get("data", {})
                print(f"\n📈 当前统计信息:")
                print(f"  总报工记录: {stats.get('total_reports', 0)}")
                print(f"  总工作时长: {stats.get('total_hours', 0):.1f} 小时")
                print(f"  平均工作时长: {stats.get('avg_hours', 0):.1f} 小时")
        else:
            print(f"❌ 获取统计信息失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")
    
    print("\n✅ 测试数据创建完成！")
    print("🌐 现在可以访问前端页面查看报工智能体功能")

if __name__ == "__main__":
    create_test_data()
