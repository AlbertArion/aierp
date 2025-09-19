AI ERP 项目

快速开始

后端:
- 进入 backend，创建虚拟环境并安装依赖
- 运行脚本: BACKEND_PORT=3127 ./scripts/start_backend.sh（默认已改为3127）

前端:
- 进入 frontend，安装依赖 (pnpm/npm/yarn)
- 运行 dev 启动开发服务 (默认端口5173)
- 生产环境构建: VITE_API_BASE_URL=http://192.144.231.158:3127 npm run build

环境变量:
- 在项目根目录创建 .env，设置 LLM_API_KEY=your_api_key_here
- Mongo连接：默认 MONGO_URI=mongodb://localhost:27017, MONGO_DB=aierp
- Snowflake 连接（示例最小集）：
  - SNOWFLAKE_ACCOUNT=xxx
  - SNOWFLAKE_USER=xxx
  - SNOWFLAKE_PASSWORD=xxx
  - SNOWFLAKE_WAREHOUSE=COMPUTE_WH
  - SNOWFLAKE_DATABASE=AIERP
  - SNOWFLAKE_SCHEMA=PUBLIC
- LLM真实调用（最小闭环HTTP）：
  - USE_REAL_LLM=true
  - LLM_API_BASE=https://your-gateway.example.com
  - LLM_API_KEY=sk-xxx
  - LLM_MODEL=qwen-plus 或 deepseek-chat
 - MySQL（订单变更日志最小闭环）
   - MYSQL_HOST=127.0.0.1
   - MYSQL_PORT=3306
   - MYSQL_USER=root
   - MYSQL_PASSWORD=yourpass
   - MYSQL_DATABASE=aierp

目录结构:
- backend: FastAPI + MongoDB + Snowflake + LLM封装
- frontend: Vue3 + Vite + Ant Design Vue + Pinia + Router

接口速览(后端端口: 3127):
- POST /api/data/sync
- POST /api/data/parse-unstructured
- POST /api/predict/indicators
- POST /api/predict/with-factors
- POST /api/predict/llm-simple
- GET  /api/process/alerts
- POST /api/process/alerts
- GET  /api/orders/search
- PUT  /api/orders/update
- POST /api/auth/login

种子数据:
- 启动本地MongoDB后执行：
```
cd backend
python scripts/seed_mongo.py
```

说明:
- LLM调用封装于 app/utils/llm，包含成本估算示例
- 当前含占位实现，可逐步替换为真实模型与存储

使用说明补充:
- 登录演示账号：admin/admin123（角色admin）、ops/ops123（角色ops）
- 成功登录后本地存储token，并自动携带Authorization头

生产环境部署:
- 前端API地址已配置为: http://192.144.231.158:3127
- 使用脚本构建: ./scripts/build_production.sh
- 将frontend/dist目录部署到Web服务器


