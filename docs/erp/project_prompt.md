请基于以下需求和技术架构，生成AI ERP创业项目的核心代码框架与关键功能实现逻辑，需严格遵循前后端分离架构，整合大模型在特定场景的替代应用，覆盖三大核心业务方向：

### 一、项目背景与核心业务

开发AI驱动的ERP系统，涵盖三大核心业务方向：

1. 企业指标预测系统：多周期指标预测、利润关联量化、多报表数据整合
2. 对接流程监管机制：智能规则自迭代、范围内自动修复、分级报警与方案输出
3. 自动化订单协同与更新系统：多模态订单检索、语音驱动数据修改、语音确认执行
   需支持与企业现有ERP（如SAP、用友）对接，适配Web端与移动端访问。

### 二、技术架构与目录结构

1. 根目录结构：
   ├── frontend（Web前端：vue+vite+antd+uni-icon）
   ├── mobile（移动端：uni-app+原生语音API）
   └── backend（后端：python+fastapi+mongodb）

### 三、后端技术实现要求（python+fastapi+mongodb）

1. 数据集成模块（传统技术为主，大模型辅助）：

   - 核心流程：使用DataX实现ERP结构化数据（财务报表、销售数据）自动同步，Python Pandas清洗后存储至Snowflake，mongodb缓存热点数据
   - 大模型辅助场景（集成Qwen/DeepSeek）：
     - 非结构化数据转换：实现PDF报表/Excel非规范表格解析（utils/llm/data_extract.py），调用Qwen API提取关键字段（如"从PDF中提取2024年Q3各区域销售额"）
     - 字段映射规则生成：新ERP系统对接时，大模型分析源字段（如SAP的"VBELN"）与目标字段语义关联，生成初始映射规则（utils/llm/field_mapping.py）
   - 接口：POST /api/data/sync（数据同步）、POST /api/data/parse-unstructured（非结构化解析）
2. 指标预测模块（LLM为主，传统模型辅助）：

   - 核心流程：基于LLM（Qwen/DeepSeek）实现1-6个月营收/利润率预测（models/train/llm_predictor.py），支持业务上下文和外部因素分析
   - 传统模型辅助场景：
     - 轻量级预测：提供简单统计模型（指数平滑）作为LLM的快速替代方案（models/train/simple_predictor.py）
     - 回退机制：当LLM服务不可用时，自动切换到传统模型进行基础预测
   - 接口：POST /api/predict/indicators（LLM预测）、POST /api/predict/with-factors（融合外部因素的预测）、POST /api/predict/llm-predict（直接LLM预测）
3. 流程监管模块：

   - 集成Drools规则引擎定义初始监管规则，规则数据存储于mongodb
   - 通过Flink实时采集流程日志（订单-库存-财务对账、供应商数据同步等）
   - 实现AI规则自迭代逻辑，处理标准化问题自动修复
   - 超出修复范围时触发分级报警，接口（GET /api/process/alerts）返回报警信息与解决方案
4. 订单协同模块（Web端 + 移动端）：

   **Web端功能：**
   - 文字输入支持：通过文本输入框实现订单指令输入，支持自然语言处理
   - 通过BERT模型提取关键信息（订单号、修改字段、操作类型），封装为工具函数
   - 订单数据存储于mongodb，修改记录同步至MySQL数据库
   - 提供订单检索（GET /api/orders/search）、修改（PUT /api/orders/update）接口，包含合法性校验逻辑

   **移动端功能（新增）：**
   - 原生语音转文字（TTS）集成：支持iOS/Android原生语音识别API，实现实时语音输入
   - 语音指令实时处理：移动端语音指令通过WebSocket实时传输至服务器，支持连续语音输入
   - 多端数据同步：移动端订单操作实时同步至Web端和MongoDB，确保数据一致性
   - 离线语音缓存：支持网络不佳时本地语音缓存，网络恢复后自动同步
   - 语音反馈机制：订单操作完成后，通过TTS语音播报操作结果和状态
   - 移动端专用接口：POST /api/mobile/voice/process（语音处理）、WebSocket /ws/mobile/orders（实时同步）
5. 通用配置：

   - 大模型接口封装：统一管理Qwen/DeepSeek API调用（utils/llm/base_client.py），包含超时重试、成本控制（按token计数）
   - 使用Pydantic定义数据模型，FastAPI实现请求验证与响应格式化
   - 实现模型切换机制，可在传统模型与大模型间动态切换（config/model_switch.py）
   - 提供Dockerfile支持容器化部署

### 四、前端技术实现要求（Web端 + 移动端）

#### 4.1 Web前端（vue+vite+antd+uni-icon）

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
   - 指标预测页：增加"外部因素输入框"（文本形式），提交后展示LLM修正后的预测结果对比
   - 订单协同页：集成文本输入组件，实现订单查询与修改界面，支持与移动端实时同步

3. 通用实现：
   - vite.config.js配置跨域代理，对接后端API
   - 全局注册antd组件与uni-icon，统一UI风格
   - 实现响应式布局，适配Web与移动端访问

#### 4.2 移动端（uni-app+原生语音API）

1. 项目结构：
   ├── mobile
   │  ├── pages（移动端页面：订单语音操作、实时同步状态等）
   │  ├── components（移动端组件：语音输入、TTS播报、离线缓存等）
   │  ├── utils（移动端工具：语音处理、WebSocket连接、数据同步等）
   │  ├── store（移动端状态管理）
   │  └── manifest.json（uni-app配置）

2. 核心功能实现：
   - **语音转文字（TTS）**：
     - 集成iOS Speech Framework和Android SpeechRecognizer
     - 支持连续语音识别和实时文本转换
     - 语音指令智能解析（订单号、操作类型、数据字段）
   
   - **实时数据同步**：
     - WebSocket连接管理，支持断线重连
     - 订单操作实时推送至Web端和服务器
     - 离线操作缓存，网络恢复后自动同步
   
   - **语音反馈系统**：
     - 操作结果TTS语音播报
     - 错误提示和操作指导语音提示
     - 支持多语言语音反馈

3. 移动端专用页面：
   - 订单语音操作页：语音输入订单号、修改指令，实时显示操作结果
   - 数据同步状态页：显示与Web端和服务器同步状态
   - 离线缓存管理页：管理离线操作记录，手动同步功能

### 五、代码输出要求

1. 分frontend、mobile和backend三大模块，按目录结构提供核心文件代码
2. 重点包含LLM核心场景的实现：非结构化数据解析、字段映射生成、LLM预测与修正的完整代码与注释
3. 移动端语音功能实现：原生TTS集成、WebSocket实时同步、离线缓存机制的完整代码
4. 明确LLM与传统模型的调用边界，包含模型切换逻辑代码
5. 代码需符合行业规范（Python 3.9+、Vue 3+、uni-app），便于后续扩展与维护
6. 包含大模型API密钥管理、调用成本控制的示例代码
7. 移动端与Web端数据同步机制：WebSocket连接管理、实时数据推送、离线操作缓存的完整实现
