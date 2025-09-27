#!/bin/bash

# AI ERP 完整系统启动脚本
# 同时启动前端和后端服务

echo "🚀 启动 AI ERP 完整系统..."

# 检查是否在正确的目录
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 函数：启动后端
start_backend() {
    echo "🔧 启动后端服务..."
    cd backend
    
    # 检查 Python 依赖
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt --quiet > /dev/null 2>&1
    fi
    
    # 启动后端（后台运行）
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3127 --reload > ../backend.log 2>&1 &
    BACKEND_PID=$!
    echo "✅ 后端服务已启动 (PID: $BACKEND_PID, 端口: 3127)"
    
    cd ..
}

# 函数：启动前端
start_frontend() {
    echo "🎨 启动前端服务..."
    cd frontend
    
    # 安装依赖（如果需要）
    if [ ! -d "node_modules" ]; then
        echo "📥 安装前端依赖..."
        npm install > /dev/null 2>&1
    fi
    
    # 启动前端（后台运行）
    nohup npm run dev > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "✅ 前端服务已启动 (PID: $FRONTEND_PID, 端口: 5176)"
    
    cd ..
}

# 函数：停止所有服务
stop_services() {
    echo ""
    echo "🛑 正在停止服务..."
    
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo "✅ 后端服务已停止"
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        echo "✅ 前端服务已停止"
    fi
    
    # 清理日志文件
    rm -f backend.log frontend.log
    
    echo "👋 所有服务已停止，再见！"
    exit 0
}

# 设置信号处理
trap stop_services SIGINT SIGTERM

# 启动服务
start_backend
sleep 3  # 等待后端启动

start_frontend
sleep 3  # 等待前端启动

# 显示访问信息
echo ""
echo "🎉 AI ERP 系统启动完成！"
echo "=================================="
echo "🌐 前端访问地址: http://localhost:5176"
echo "🔧 后端API地址: http://localhost:3127"
echo "📚 API文档地址: http://localhost:3127/docs"
echo "📊 后端日志: tail -f backend.log"
echo "🎨 前端日志: tail -f frontend.log"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "=================================="

# 等待用户中断
wait