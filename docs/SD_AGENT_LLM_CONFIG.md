# SD Agent LLM 配置说明

## 概述

SD Agent 现已支持 LLM（大语言模型）能力，可以更智能地理解用户意图和处理自然语言查询。

## 功能特性

### 1. 智能意图识别
- 使用 LLM 识别用户查询意图，比规则匹配更准确
- 自动提取关键信息（订单号、交货单号、发票号等）
- 支持置信度评估，低置信度时自动回退到规则匹配

### 2. 智能对话
- 对于闲聊或超出能力范围的问题，使用 LLM 自动生成友好回答
- 提供系统能力说明和使用示例

## 配置方法

### 环境变量配置

在启动服务前，设置以下环境变量：

```bash
# 启用 LLM（默认：true）
export USE_LLM_SD_AGENT=true

# LLM API Key（必需）
export OPENAI_API_KEY=your_api_key_here
# 或者使用
export LLM_API_KEY=your_api_key_here

# LLM API Base URL（默认：阿里云 DashScope）
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# 或者使用
export LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# LLM 模型名称（默认：qwen-max-latest）
export SD_AGENT_LLM_MODEL=qwen-max-latest
```

### 支持的 LLM 服务

SD Agent 支持任何兼容 OpenAI API 格式的 LLM 服务：

1. **阿里云 DashScope（推荐）**
   ```bash
   export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   export SD_AGENT_LLM_MODEL=qwen-max-latest
   ```

2. **DeepSeek**
   ```bash
   export OPENAI_BASE_URL=https://api.deepseek.com
   export SD_AGENT_LLM_MODEL=deepseek-chat
   ```

3. **OpenAI**
   ```bash
   export OPENAI_BASE_URL=https://api.openai.com/v1
   export SD_AGENT_LLM_MODEL=gpt-4
   ```

4. **其他兼容服务**
   - 任何支持 OpenAI 兼容 API 的服务都可以使用

## 使用说明

### 启用/禁用 LLM

如果不想使用 LLM，可以禁用：

```bash
export USE_LLM_SD_AGENT=false
```

禁用后，SD Agent 将完全使用规则匹配方式识别意图。

### 工作流程

1. **优先使用 LLM**
   - 首先尝试使用 LLM 识别用户意图
   - 如果 LLM 返回结果且置信度 >= 0.5，使用 LLM 结果

2. **回退到规则匹配**
   - 如果 LLM 未配置、失败或置信度 < 0.5
   - 自动回退到基于规则的意图识别

3. **信息提取**
   - LLM 提取的信息（订单号、交货单号等）优先使用
   - 如果 LLM 未提取到，使用规则提取

## 示例

### 示例 1：查询订单详情

**用户输入：** "帮我看看VB2025000059这个订单的情况"

**LLM 识别：**
```json
{
    "intent": "QUERY_ORDER_DETAIL",
    "confidence": 0.95,
    "extracted": {
        "vbeln": "VB2025000059"
    }
}
```

### 示例 2：创建交货单

**用户输入：** "为销售订单VB2025000059生成一个交货单"

**LLM 识别：**
```json
{
    "intent": "CREATE_DELIVERY",
    "confidence": 0.92,
    "extracted": {
        "vbeln": "VB2025000059"
    }
}
```

### 示例 3：闲聊

**用户输入：** "你好，你能做什么？"

**LLM 回答：**
> 你好！我是SD Agent，可以帮助您：
> 1. 查询销售订单列表和详情
> 2. ATP物料可用性检查
> 3. 自动创建交货单
> 4. 交货单过账
> 5. 创建发票
> 6. 复制订单
> 7. 创建销售订单
> 
> 请告诉我您需要什么帮助？

## 注意事项

1. **API Key 安全**
   - 不要将 API Key 提交到代码仓库
   - 使用环境变量或配置文件管理密钥

2. **网络要求**
   - 确保服务器可以访问 LLM API 服务
   - 注意 API 调用的超时设置（默认 10-15 秒）

3. **成本控制**
   - LLM API 调用可能产生费用
   - 建议设置合理的超时和重试机制

4. **性能优化**
   - LLM 调用有延迟，规则匹配作为备选方案
   - 低置信度时自动回退，避免错误识别

## 故障排查

### LLM 未生效

1. 检查环境变量是否正确设置
2. 检查 API Key 是否有效
3. 查看日志中的 LLM 调用信息

### LLM 识别不准确

1. 检查模型选择是否合适
2. 查看置信度，如果太低会自动回退
3. 可以调整 `temperature` 参数（在代码中）

### API 调用失败

1. 检查网络连接
2. 检查 API Base URL 是否正确
3. 检查 API Key 是否有权限
4. 查看错误日志获取详细信息

## 相关文件

- `ai_erp_agent/backend/app/api/v1/sd_agent.py` - SD Agent 主文件
- `ai_erp_agent/backend/app/api/v1/pp_agent.py` - PP Agent 参考实现

