#!/bin/bash

# AI ERP 后端启动脚本
# 智能部署和启动脚本，适用于开发和生产环境

echo "🚀 AI ERP 后端启动脚本"
echo "================================"

# 检查是否在正确的目录
if [ ! -f "app/main.py" ]; then
    echo "❌ 错误：请在backend目录下运行此脚本"
    exit 1
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python3，请先安装 Python3"
    exit 1
fi

echo "📦 Python版本: $(python3 --version)"

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "🔧 激活虚拟环境..."
    source .venv/bin/activate
    echo "✅ 虚拟环境已激活"
else
    echo "⚠️  未找到虚拟环境，使用系统Python"
fi

# 检查并升级构建工具（仅在需要时）
echo "🔧 检查构建工具版本..."
pip install --upgrade pip setuptools wheel

# 检查并安装依赖（智能安装，避免重复下载）
echo "📥 检查依赖状态..."

# 检查关键依赖是否已安装
check_dependency() {
    python3 -c "import $1" 2>/dev/null
    return $?
}

# 检查requirements.txt是否存在，如果存在则使用它
if [ -f "requirements.txt" ]; then
    echo "📦 使用requirements.txt安装依赖..."
    pip install -r requirements.txt
else
    echo "📦 分步安装依赖..."
    
    # 1. 安装基础构建工具
    echo "📦 安装基础构建工具..."
    pip install setuptools wheel pip
    
    # 2. 安装基础依赖（条件安装）
    echo "📦 检查基础依赖..."
    if ! check_dependency fastapi; then
        echo "📦 安装fastapi..."
        pip install fastapi==0.112.2
    else
        echo "✅ fastapi已安装"
    fi
    
    if ! check_dependency uvicorn; then
        echo "📦 安装uvicorn..."
        pip install uvicorn[standard]==0.30.6
    else
        echo "✅ uvicorn已安装"
    fi
    
    if ! check_dependency pydantic; then
        echo "📦 安装pydantic..."
        pip install pydantic==2.9.2
    else
        echo "✅ pydantic已安装"
    fi
    
    if ! check_dependency multipart; then
        echo "📦 安装python-multipart..."
        pip install python-multipart==0.0.9
    else
        echo "✅ python-multipart已安装"
    fi
    
    # 3. 安装数据处理依赖（条件安装）
    echo "📦 检查数据处理依赖..."
    if ! check_dependency pandas; then
        echo "📦 安装pandas..."
        pip install "pandas>=2.0.0,<2.1.0"
    else
        echo "✅ pandas已安装"
    fi
    
    if ! check_dependency numpy; then
        echo "📦 安装numpy..."
        pip install "numpy>=1.24.0,<2.0.0"
    else
        echo "✅ numpy已安装"
    fi
    
    # 4. 安装机器学习依赖（条件安装）
    echo "📦 检查机器学习依赖..."
    if ! check_dependency sklearn; then
        echo "📦 安装scikit-learn..."
        pip install scikit-learn==1.3.2
    else
        echo "✅ scikit-learn已安装"
    fi
    
    # 5. 尝试安装statsmodels（可能失败）
    if ! check_dependency statsmodels; then
        echo "📦 尝试安装statsmodels..."
        if pip install "statsmodels>=0.14.0"; then
            echo "✅ statsmodels安装成功"
            STATSMODELS_OK=true
        else
            echo "⚠️  statsmodels安装失败，将使用简化预测方法"
            STATSMODELS_OK=false
        fi
    else
        echo "✅ statsmodels已安装"
        STATSMODELS_OK=true
    fi
    
    # 6. 安装其他依赖（条件安装）
    echo "📦 检查其他依赖..."
    for pkg in pymongo snowflake_connector requests pdfplumber openpyxl pymysql; do
        if ! check_dependency $pkg; then
            case $pkg in
                pymongo) pip install pymongo==4.8.0 ;;
                snowflake_connector) pip install snowflake-connector-python==3.11.0 ;;
                requests) pip install requests==2.32.3 ;;
                pdfplumber) pip install pdfplumber==0.11.4 ;;
                openpyxl) pip install openpyxl==3.1.5 ;;
                pymysql) pip install PyMySQL==1.1.1 ;;
            esac
            echo "✅ $pkg 安装完成"
        else
            echo "✅ $pkg 已安装"
        fi
    done
fi
    # jpype1已移除：Drools引擎使用模拟实现，无需Java桥接

# 验证关键模块导入
echo "🔍 验证关键模块..."
python3 -c "
import sys
errors = []

try:
    import fastapi
    print('✅ fastapi导入成功')
except ImportError as e:
    errors.append(f'fastapi: {e}')

try:
    import uvicorn
    print('✅ uvicorn导入成功')
except ImportError as e:
    errors.append(f'uvicorn: {e}')

try:
    import pandas
    print('✅ pandas导入成功')
except ImportError as e:
    errors.append(f'pandas: {e}')

try:
    import numpy
    print('✅ numpy导入成功')
except ImportError as e:
    errors.append(f'numpy: {e}')

try:
    import sklearn
    print('✅ sklearn导入成功')
except ImportError as e:
    errors.append(f'sklearn: {e}')

try:
    import statsmodels
    print('✅ statsmodels导入成功')
except ImportError:
    print('⚠️  statsmodels不可用，将使用简化预测方法')

if errors:
    print('❌ 以下模块导入失败:')
    for error in errors:
        print(f'  - {error}')
    sys.exit(1)
else:
    print('✅ 所有核心模块导入成功')
"

if [ $? -ne 0 ]; then
    echo "❌ 模块验证失败，请检查依赖安装"
    exit 1
fi

# 测试应用启动
echo "🧪 测试应用启动..."
python3 -c "
try:
    from app.main import create_app
    app = create_app()
    print('✅ 应用创建成功')
except Exception as e:
    print(f'❌ 应用创建失败: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ 应用测试失败"
    exit 1
fi

# 检查端口是否被占用
PORT=3127
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口 $PORT 已被占用，尝试停止现有进程..."
    pkill -f "uvicorn.*$PORT" || true
    sleep 2
fi

# 设置环境变量
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export ENVIRONMENT="development"

echo "🎉 启动准备完成！"
echo "================================"
echo "🌟 启动后端服务 (端口 $PORT)..."
echo "🌐 后端API地址: http://localhost:$PORT"
echo "📚 API文档地址: http://localhost:$PORT/docs"
echo "🔍 健康检查: http://localhost:$PORT/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=================================="

# 启动uvicorn服务器
python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
