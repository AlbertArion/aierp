#!/bin/bash

# AI ERP 前端启动脚本
# 启动 Vue 3 + Vite 前端服务

echo "🚀 启动 AI ERP 前端服务..."

# 检查是否在正确的目录
if [ ! -d "frontend" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 进入前端目录
cd frontend

# 检查 Node.js 和 npm
if ! command -v node &> /dev/null; then
    echo "❌ 错误：未找到 Node.js，请先安装 Node.js"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ 错误：未找到 npm，请先安装 npm"
    exit 1
fi

echo "📦 Node.js 版本: $(node --version)"
echo "📦 npm 版本: $(npm --version)"

# 检查 package.json
if [ ! -f "package.json" ]; then
    echo "❌ 错误：未找到 package.json"
    exit 1
fi

# 安装依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "📥 安装前端依赖..."
    npm install
else
    echo "✅ 前端依赖已安装"
fi

# 启动前端开发服务器
echo "🌟 启动前端开发服务器 (端口 5176)..."
echo "🌐 前端访问地址: http://localhost:5176"
echo "🔧 后端API地址: http://localhost:3127"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=================================="

npm run dev
