#!/bin/bash

# AI ERP 前端启动脚本
# 启动 Vue3 + TypeScript + Element Plus 前端服务

echo "🎨 启动 AI ERP 前端服务..."

# 检查是否在正确的目录
if [ ! -f "package.json" ]; then
    echo "❌ 错误：请在frontend目录下运行此脚本"
    exit 1
fi

# 检查Node.js环境
if ! command -v node &> /dev/null; then
    echo "❌ 错误：未找到 Node.js，请先安装 Node.js"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ 错误：未找到 npm，请先安装 npm"
    exit 1
fi

echo "📦 Node.js版本: $(node --version)"
echo "📦 npm版本: $(npm --version)"

# 检查package.json
if [ ! -f "package.json" ]; then
    echo "❌ 错误：未找到package.json"
    exit 1
fi

# 检查并安装依赖
if [ ! -d "node_modules" ]; then
    echo "📥 安装前端依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败"
        exit 1
    fi
    echo "✅ 依赖安装完成"
else
    echo "✅ 依赖已存在"
fi

# 检查端口是否被占用
PORT=5176
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口 $PORT 已被占用，尝试停止现有进程..."
    pkill -f "vite.*$PORT" || true
    sleep 2
fi

# 启动前端服务
echo "🌟 启动前端开发服务器 (端口 $PORT)..."
echo "🌐 前端访问地址: http://localhost:$PORT"
echo "📚 后端API地址: http://localhost:3127"
echo "📖 API文档地址: http://localhost:3127/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=================================="

# 启动Vite开发服务器
npm run dev
