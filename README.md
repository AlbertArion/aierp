# AI ERP 系统

## 🚀 项目简介

AI ERP 系统是一个基于人工智能的企业资源规划系统，集成了订单管理、预测分析、流程监管等核心功能，采用现代化的技术栈构建。

## ✨ 核心功能

### 📊 订单管理
- 订单数据导入和同步
- 订单状态跟踪
- 订单分析报表

### 🔮 智能预测
- 基于历史数据的销售预测
- 库存需求预测
- 多模型预测支持（传统ML + LLM）

### 🛡️ 流程监管
- **Drools规则引擎**：支持复杂业务规则定义和执行
- **AI规则自迭代**：基于历史数据和LLM的规则自动学习和优化
- **分级报警系统**：五级告警分类（INFO/WARNING/ERROR/CRITICAL/EMERGENCY）
- **规则分析功能**：性能监控、趋势分析、优化建议

### 🔗 数据集成
- 多数据源集成
- 实时数据同步
- 数据质量监控

## 🏗️ 技术架构

### 后端技术栈
- **FastAPI** - 现代化Python Web框架
- **MongoDB** - 文档数据库
- **Drools** - 规则引擎（通过JPype集成）
- **scikit-learn** - 机器学习库
- **LLM集成** - 支持DeepSeek/Qwen等大模型

### 前端技术栈
- **Vue 3** - 渐进式JavaScript框架
- **TypeScript** - 类型安全的JavaScript
- **Element Plus** - Vue 3 UI组件库
- **ECharts** - 数据可视化图表库
- **Vite** - 快速构建工具

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Node.js 16+
- MongoDB（可选，支持内存数据库fallback）

### 安装和启动

1. **克隆项目**
```bash
git clone <repository-url>
cd aierp
```

2. **一键启动**
```bash
# 启动完整系统（前后端）
./scripts/start_aierp.sh
```

3. **访问系统**
- 🌐 前端界面：http://localhost:5173
- 🔧 后端API：http://localhost:3127
- 📚 API文档：http://localhost:3127/docs

### 手动启动（可选）

如果需要分别启动前后端：

```bash
# 启动后端
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3127 --reload

# 启动前端
cd frontend
npm install
npm run dev
```

## 📊 数据库配置

### MongoDB配置
系统默认连接到线上MongoDB服务器：`192.144.231.158:27017`

### 环境变量配置（可选）
```bash
# 自定义MongoDB连接
export MONGO_URI="mongodb://192.144.231.158:27017"
export MONGO_DB="aierp"

# 如果需要认证
export MONGO_USERNAME="your_username"
export MONGO_PASSWORD="your_password"
```

### Fallback机制
如果MongoDB连接失败，系统会自动使用内存数据库，确保应用正常运行。

## 🔧 API接口

### 订单管理
- `GET /api/orders` - 获取订单列表
- `POST /api/orders` - 创建订单
- `PUT /api/orders/{id}` - 更新订单
- `DELETE /api/orders/{id}` - 删除订单

### 预测分析
- `POST /api/predict/indicators` - 指标预测
- `GET /api/predict/models` - 获取预测模型

### 流程监管
- `GET /api/process/rules` - 获取规则列表
- `POST /api/process/rules` - 创建规则
- `POST /api/process/events` - 触发事件
- `GET /api/process/alerts` - 获取告警列表

#### Drools规则引擎
- `POST /api/process/drools/rules` - 创建Drools规则
- `POST /api/process/drools/rules/{id}/execute` - 执行规则
- `GET /api/process/drools/rules/statistics` - 获取规则统计

#### AI规则学习
- `GET /api/process/ai/rules/{id}/performance` - 分析规则性能
- `POST /api/process/ai/rules/{id}/learn` - 从反馈学习
- `POST /api/process/ai/rules/{id}/auto-optimize` - 自动优化

#### 分级告警系统
- `POST /api/process/alerts/classify` - 分类告警
- `GET /api/process/alerts/statistics` - 告警统计
- `GET /api/process/alerts/levels` - 告警级别定义

### 规则分析
- `GET /api/process/analytics/rules/{id}/performance` - 性能分析
- `GET /api/process/analytics/rules/comparison` - 规则对比
- `GET /api/process/analytics/rules/{id}/recommendations` - 优化建议

## 📁 项目结构

```
aierp/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API接口
│   │   │   └── v1/         # API v1版本
│   │   ├── db/             # 数据库连接
│   │   ├── models/         # 数据模型
│   │   ├── repository/     # 数据访问层
│   │   ├── schemas/        # 数据验证模式
│   │   └── utils/          # 工具类
│   │       ├── rules/      # 规则引擎工具
│   │       ├── llm/        # LLM集成
│   │       └── nlp/        # NLP工具
│   ├── requirements.txt    # Python依赖
│   └── Dockerfile         # Docker配置
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── pages/         # 页面组件
│   │   ├── router/        # 路由配置
│   │   └── utils/         # 工具函数
│   ├── package.json       # 前端依赖
│   └── vite.config.ts     # Vite配置
├── scripts/               # 脚本文件
│   └── start_aierp.sh     # 启动脚本
├── product/               # 产品文档
└── README.md             # 项目说明
```

## 🔒 安全特性

- JWT身份认证
- 请求频率限制
- 输入数据验证
- SQL注入防护
- XSS攻击防护

## 🧪 测试

```bash
# 运行系统功能测试
cd backend
python3 -c "
from app.main import create_app
app = create_app()
print('✅ 应用创建成功，所有模块加载正常')
"
```

## 📈 性能优化

- 数据库连接池
- 缓存机制
- 异步处理
- 代码分割
- 懒加载

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

如有问题或建议，请联系开发团队。

## 🎯 路线图

- [ ] 微服务架构升级
- [ ] 容器化部署
- [ ] 多租户支持
- [ ] 移动端适配
- [ ] 更多AI模型集成

---

**AI ERP 系统** - 让企业智能化更简单 🚀