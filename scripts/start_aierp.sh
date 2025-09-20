#!/bin/bash

# AI ERP系统启动脚本

echo "🚀 启动AI ERP系统..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装，请先安装Python3"
    exit 1
fi

# 检查依赖
echo "📦 检查Python依赖..."
cd "$(dirname "$0")/../backend"
if ! python3 -c "import fastapi, pymongo, uvicorn" &> /dev/null; then
    echo "📥 安装Python依赖..."
    python3 -m pip install -r requirements.txt
fi

# 测试数据库连接
echo "🔍 测试数据库连接..."
python3 -c "
from app.db.mongo import get_db
db = get_db()
print(f'数据库类型: {type(db).__name__}')
if hasattr(db, 'process_rules'):
    print('✅ 连接到MongoDB数据库')
else:
    print('⚠️  使用内存数据库（数据不会持久化）')
"

# 启动后端服务
echo "🔧 启动后端服务..."
echo "💡 提示：如果MongoDB连接失败，系统将自动使用内存数据库"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3127 --reload &

# 等待后端启动
sleep 3

# 启动前端服务
echo "🎨 启动前端服务..."
cd "../frontend"
if [ ! -d "node_modules" ]; then
    echo "📥 安装前端依赖..."
    npm install
fi

echo "🌐 启动前端开发服务器..."
npm run dev &

echo "✅ 系统启动完成！"
echo "📊 后端API: http://localhost:3127"
echo "🎨 前端界面: http://localhost:5173"
echo "📚 API文档: http://localhost:3127/docs"

echo ""
echo "💡 使用提示："
echo "   - 按 Ctrl+C 停止所有服务"
echo "   - 流程监管模块（Drools、AI学习、分级告警）已就绪"
echo "   - 如果MongoDB连接失败，系统会使用内存数据库确保正常运行"
