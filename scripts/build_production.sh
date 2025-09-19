#!/bin/bash

# 生产环境构建脚本
# 设置API基础URL为线上环境
export VITE_API_BASE_URL=http://192.144.231.158:3127

echo "开始构建生产环境..."
echo "API基础URL: $VITE_API_BASE_URL"

# 进入前端目录
cd frontend

# 安装依赖
echo "安装依赖..."
npm install

# 构建生产版本
echo "构建生产版本..."
npm run build

echo "构建完成！"
echo "构建文件位于: frontend/dist/"
echo "请将dist目录部署到Web服务器"
