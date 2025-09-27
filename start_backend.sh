#!/bin/bash

# AI ERP 后端启动脚本
# 启动 FastAPI 后端服务

echo "🚀 启动 AI ERP 后端服务..."

# 检查是否在正确的目录
if [ ! -d "backend" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 进入后端目录
cd backend

# 检查 Python 依赖
echo "📦 检查 Python 依赖..."
if [ ! -f "requirements.txt" ]; then
    echo "❌ 错误：未找到 requirements.txt"
    exit 1
fi

# 检查虚拟环境（可选）
if [ -d "venv" ]; then
    echo "🔧 激活虚拟环境..."
    source venv/bin/activate
elif command -v python3 &> /dev/null; then
    echo "🐍 使用系统 Python3"
else
    echo "❌ 错误：未找到 Python3"
    exit 1
fi

# 安装依赖（如果需要）
echo "📥 检查并安装依赖..."
pip3 install -r requirements.txt --quiet

# 启动后端服务
echo "🌟 启动后端服务 (端口 3127)..."
echo "📱 前端访问地址: http://localhost:5176"
echo "🔧 后端API地址: http://localhost:3127"
echo "📚 API文档地址: http://localhost:3127/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=================================="

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3127 --reload
