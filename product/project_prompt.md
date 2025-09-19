请基于以下需求和技术架构，生成AI ERP创业项目的核心代码框架与关键功能实现逻辑，需严格遵循前后端分离架构，整合大模型在特定场景的替代应用，覆盖三大核心业务方向：

### 一、项目背景与核心业务

开发AI驱动的ERP系统，涵盖三大核心业务方向：

1. 企业指标预测系统：多周期指标预测、利润关联量化、多报表数据整合
2. 对接流程监管机制：智能规则自迭代、范围内自动修复、分级报警与方案输出
3. 自动化订单协同与更新系统：多模态订单检索、语音驱动数据修改、语音确认执行
   需支持与企业现有ERP（如SAP、用友）对接，适配Web端与移动端访问。

### 二、技术架构与目录结构

1. 根目录结构：
   ├── frontend（前端：vue+vite+antd+uni-icon）
   └── backend（后端：python+fastapi+mongodb）

### 三、后端技术实现要求（python+fastapi+mongodb）

1. 数据集成模块（传统技术为主，大模型辅助）：

   - 核心流程：使用DataX实现ERP结构化数据（财务报表、销售数据）自动同步，Python Pandas清洗后存储至Snowflake，mongodb缓存热点数据
   - 大模型辅助场景（集成Qwen/DeepSeek）：
     - 非结构化数据转换：实现PDF报表/Excel非规范表格解析（utils/llm/data_extract.py），调用Qwen API提取关键字段（如"从PDF中提取2024年Q3各区域销售额"）
     - 字段映射规则生成：新ERP系统对接时，大模型分析源字段（如SAP的"VBELN"）与目标字段语义关联，生成初始映射规则（utils/llm/field_mapping.py）
   - 接口：POST /api/data/sync（数据同步）、POST /api/data/parse-unstructured（非结构化解析）
2. 指标预测模块（传统模型为主，大模型辅助修正）：

   - 核心流程：基于TensorFlow搭建LSTM模型（models/train/lstm_predictor.py），实现1-6个月营收/利润率预测（误差率<5%）
   - 大模型辅助场景（集成Qwen/DeepSeek）：
     - 外部因素融合：接收文本类外部信息（如"9月有促销活动"），调用DeepSeek API分析影响权重，修正LSTM预测结果（utils/llm/predict_correction.py）
     - 中短期简单预测：提供轻量接口（POST /api/predict/llm-simple），直接通过大模型生成3个月内趋势预测（适用于小数据场景）
   - 接口：POST /api/predict/indicators（LSTM预测）、POST /api/predict/with-factors（融合外部因素的预测）
3. 流程监管模块：

   - 集成Drools规则引擎定义初始监管规则，规则数据存储于mongodb
   - 通过Flink实时采集流程日志（订单-库存-财务对账、供应商数据同步等）
   - 实现AI规则自迭代逻辑，处理标准化问题自动修复
   - 超出修复范围时触发分级报警，接口（GET /api/process/alerts）返回报警信息与解决方案
4. 订单协同模块：

   - 集成百度AI语音识别API，实现语音指令转文本（utils/voice/baidu_voice.py）
   - 通过BERT模型提取关键信息（订单号、修改字段、操作类型），封装为工具函数
   - 订单数据存储于mongodb，修改记录同步至MySQL数据库
   - 提供订单检索（GET /api/orders/search）、修改（PUT /api/orders/update）接口，包含合法性校验逻辑
5. 通用配置：

   - 大模型接口封装：统一管理Qwen/DeepSeek API调用（utils/llm/base_client.py），包含超时重试、成本控制（按token计数）
   - 使用Pydantic定义数据模型，FastAPI实现请求验证与响应格式化
   - 实现模型切换机制，可在传统模型与大模型间动态切换（config/model_switch.py）
   - 提供Dockerfile支持容器化部署

### 四、前端技术实现要求（vue+vite+antd+uni-icon）

1. 项目结构：
   ├── src
   │  ├── api（接口封装，对应后端各模块）
   │  ├── components（业务组件：预测图表、流程监控面板、订单表单等）
   │  ├── pages（三大业务模块页面）
   │  ├── router（路由配置）
   │  ├── store（pinia状态管理）
   │  └── assets（uni-icon图标资源）
2. 核心页面增强实现（针对大模型场景）：

   - 数据集成页：增加"非结构化数据解析"区域，支持上传PDF/Excel，展示大模型提取结果
   - 指标预测页：增加"外部因素输入框"（文本形式），提交后展示大模型修正后的预测结果对比
   - 订单协同页：集成语音输入组件，实现订单查询与修改界面
3. 通用实现：

   - vite.config.js配置跨域代理，对接后端API
   - 全局注册antd组件与uni-icon，统一UI风格
   - 实现响应式布局，适配Web与移动端访问

### 五、代码输出要求

1. 分frontend和backend两大模块，按目录结构提供核心文件代码
2. 重点包含大模型辅助场景的实现：非结构化数据解析、字段映射生成、预测结果修正的完整代码与注释
3. 明确传统技术与大模型的调用边界，包含模型切换逻辑代码
4. 代码需符合行业规范（Python 3.9+、Vue 3+），便于后续扩展与维护
5. 包含大模型API密钥管理、调用成本控制的示例代码
