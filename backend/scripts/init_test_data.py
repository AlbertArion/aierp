#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
初始化测试数据脚本
直接在API进程中初始化测试数据
"""

import requests
import json
from datetime import date, datetime, timedelta
import random

# 测试数据
test_data = [
    {
        "employee_name": "张三",
        "project_name": "ERP系统开发",
        "department_name": "技术部",
        "report_date": "2024-01-15",
        "work_hours": 8.0,
        "work_content": "系统架构设计",
        "work_location": "办公室",
        "status": "approved"
    },
    {
        "employee_name": "李四",
        "project_name": "数据分析平台",
        "department_name": "技术部",
        "report_date": "2024-01-15",
        "work_hours": 7.5,
        "work_content": "前端页面开发",
        "work_location": "办公室",
        "status": "pending"
    },
    {
        "employee_name": "王五",
        "project_name": "移动应用开发",
        "department_name": "产品部",
        "report_date": "2024-01-16",
        "work_hours": 8.5,
        "work_content": "需求分析",
        "work_location": "会议室",
        "status": "approved"
    }
]

def init_test_data():
    """初始化测试数据"""
    base_url = "http://localhost:3127/api"
    
    print("🚀 开始初始化测试数据...")
    
    for i, data in enumerate(test_data):
        try:
            response = requests.post(f"{base_url}/work-reports/", json=data)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print(f"  ✅ 创建测试记录 {i+1}: {data['employee_name']} - {data['project_name']}")
                else:
                    print(f"  ❌ 创建测试记录 {i+1} 失败: {result.get('message', '未知错误')}")
            else:
                print(f"  ❌ 创建测试记录 {i+1} 失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ 创建测试记录 {i+1} 失败: {e}")
    
    # 检查统计信息
    try:
        response = requests.get(f"{base_url}/work-reports/statistics")
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                stats = result.get("data", {})
                print(f"\n📊 当前统计信息:")
                print(f"  总报工记录: {stats.get('total_reports', 0)}")
                print(f"  总工作时长: {stats.get('total_hours', 0):.1f} 小时")
                print(f"  平均工作时长: {stats.get('avg_hours', 0):.1f} 小时")
        else:
            print(f"❌ 获取统计信息失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")
    
    print("\n✅ 测试数据初始化完成！")

if __name__ == "__main__":
    init_test_data()
