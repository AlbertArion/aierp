<template>
  <div class="pricing-agent-page">
    <!-- 标题区域 -->
    <div class="chat-header">
      <h3>💬 AI 核价智能体</h3>
    </div>

    <!-- 聊天内容区域 -->
    <div class="chat-window">
      <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
        <div v-if="m.role === 'user'" class="bubble user">{{ m.content }}</div>
        <div v-else class="bubble ai">
          <div v-if="m.type === 'text'">{{ m.content }}</div>
          <div v-else-if="m.type === 'typing'" class="typing-animation">
            <span>{{ m.content }}</span>
            <span class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
          <div v-else-if="m.type === 'materials'" class="materials-display">
            <div class="materials-header">
              <h4>📋 找到需要核价的物料数据</h4>
              <p>共找到 {{ m.materials?.length || 0 }} 条物料，请确认是否开始核查分析</p>
              <a-button type="primary" @click="startPricingWithMaterials(m.materials || [])" :loading="isProcessing">
                开始核查分析
              </a-button>
            </div>
            <a-table :columns="materialColumns" :data-source="m.materials" :pagination="false" size="small" row-key="id"
              :scroll="{ x: 800 }" />
          </div>
          <div v-else-if="m.type === 'pricing_results'" class="pricing-results-display">
            <div class="results-header">
              <h4>📈 核价分析结果</h4>
              <a-space>
                <a-button @click="approveAll" type="primary" size="small">
                  批量确认
                </a-button>
                <a-button @click="saveResults" size="small">
                  保存记录
                </a-button>
              </a-space>
            </div>
            <a-table :columns="pricingColumns" :data-source="m.results" :pagination="false" row-key="id" size="small"
              :scroll="{ x: 1200 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-tag :color="getStatusColor(record.status)">
                    {{ getStatusText(record.status) }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'approve'">
                  <a-button v-if="record.status === 'pending'" type="link" size="small" @click="approveItem(record)">
                    确认
                  </a-button>
                  <a-tag v-else color="green">已确认</a-tag>
                </template>
                <template v-else-if="column.key === 'recommendation'">
                  <span :class="getRecommendationClass(record.recommendation)">
                    {{ record.recommendation }}
                  </span>
                </template>
              </template>
            </a-table>
          </div>
        </div>
      </div>
    </div>

    <!-- AI处理进度显示 -->
    <div v-if="isProcessing" class="processing-display">
      <a-steps :current="currentStep" size="small">
        <a-step title="搜索物料" />
        <a-step title="数据解析" />
        <a-step title="成本核算" />
        <a-step title="外协分析" />
        <a-step title="生成报告" />
        <a-step title="核价完成" />
      </a-steps>
      <div class="processing-message">
        <a-spin size="small" />
        <span>{{ processingMessage }}</span>
      </div>
    </div>

    <div class="input-bar">
      <a-input v-model:value="input" placeholder="请输入您的问题" @pressEnter="onSend"
        :disabled="isProcessing" />
      <a-button type="primary" @click="onSend" :disabled="isProcessing">
        发送
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import apiClient from '../utils/axios'
import { message } from 'ant-design-vue'

// 物料数据接口
interface MaterialData {
  id: string
  materialCode: string      // 物料编码
  materialName: string      // 物料名称
  specification: string     // 规格型号
  quantity: number         // 数量
  unit: string            // 单位
  complexity: string      // 复杂度等级
  processRequirements: string[] // 工艺要求
}

// 核价结果接口
interface PricingResult {
  id: string
  material_code: string
  material_name: string
  specification: string
  quantity: number
  unit: string
  internal_cost: number     // 内部制造成本
  external_cost: number     // 外协加工成本
  cost_difference: number   // 成本差异
  recommendation: string   // 建议
  status: 'pending' | 'approved' | 'rejected'
  approval_time?: string
  approved_by?: string
}

// 状态管理
const input = ref('')
const loading = ref(false)
const isProcessing = ref(false)
const currentStep = ref(0)
const processingMessage = ref('')
const messages = reactive<Array<{ role: 'user' | 'ai', content: string, type?: 'text' | 'typing' | 'materials' | 'pricing_results', materials?: MaterialData[], results?: PricingResult[] }>>([
  { role: 'ai', content: '你好，我是AI核价智能体。请告诉我你需要核价的物料信息。', type: 'text' }
])

// 表格列定义
const materialColumns = [
  { title: '物料编码', dataIndex: 'materialCode', key: 'materialCode', width: 120 },
  { title: '物料名称', dataIndex: 'materialName', key: 'materialName', width: 150 },
  { title: '规格型号', dataIndex: 'specification', key: 'specification', width: 120 },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
  { title: '单位', dataIndex: 'unit', key: 'unit', width: 60 },
  { title: '复杂度', dataIndex: 'complexity', key: 'complexity', width: 80 },
  { title: '工艺要求', dataIndex: 'processRequirements', key: 'processRequirements', width: 150 }
]

const pricingColumns = [
  { title: '物料编码', dataIndex: 'material_code', key: 'material_code', width: 120 },
  { title: '物料名称', dataIndex: 'material_name', key: 'material_name', width: 150 },
  { title: '规格型号', dataIndex: 'specification', key: 'specification', width: 120 },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
  { title: '单位', dataIndex: 'unit', key: 'unit', width: 60 },
  { title: '内部成本(元)', dataIndex: 'internal_cost', key: 'internal_cost', width: 120 },
  { title: '外协成本(元)', dataIndex: 'external_cost', key: 'external_cost', width: 120 },
  { title: '成本差异(元)', dataIndex: 'cost_difference', key: 'cost_difference', width: 120 },
  { title: '建议', dataIndex: 'recommendation', key: 'recommendation', width: 300, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '操作', dataIndex: 'approve', key: 'approve', width: 100 }
]

// 发送消息
const onSend = async () => {
  const q = input.value.trim()
  if (!q) return

  messages.push({ role: 'user', content: q })
  input.value = ''
  loading.value = true

  try {
    // 第一步：延迟1秒后显示AI回复消息
    await sleep(500)
    messages.push({
      role: 'ai',
      content: '好的，我来帮您查找这些物料并进行核价分析',
      type: 'text'
    })
    
    // 第二步：延迟500ms后添加带三个点动画的消息
    await sleep(500)
    const typingMessageIndex = messages.length
    messages.push({
      role: 'ai',
      content: '正在搜索物料数据',
      type: 'typing'
    })
    
    // 等待1-5秒随机，显示三个点动画
    await sleep(getRandomWaitTime())
    
    // 第三步：移除动画消息，添加搜索结果
    messages.splice(typingMessageIndex, 1) // 移除动画消息
    
    // 解析用户查询，搜索相关物料
    const searchResults = await searchMaterialsByQuery(q)

    if (searchResults.length === 0) {
      messages.push({
        role: 'ai',
        content: '未找到相关物料数据，请尝试其他关键词或检查物料名称。',
        type: 'text'
      })
    } else {
      messages.push({
        role: 'ai',
        content: '',
        type: 'materials',
        materials: searchResults
      })
    }
  } catch (error) {
    message.error('搜索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 根据查询搜索物料
const searchMaterialsByQuery = async (query: string): Promise<MaterialData[]> => {
  // 模拟从后端搜索物料数据
  const allMaterials = [
    {
      id: '1',
      materialCode: 'SY001',
      materialName: '纺机主轴',
      specification: 'Φ50×200mm',
      quantity: 100,
      unit: '件',
      complexity: '中等',
      processRequirements: ['车削', '磨削', '热处理']
    },
    {
      id: '2',
      materialCode: 'SY002',
      materialName: '纺机齿轮',
      specification: '模数2.5',
      quantity: 50,
      unit: '件',
      complexity: '复杂',
      processRequirements: ['铣削', '滚齿', '淬火']
    },
    {
      id: '3',
      materialCode: 'SY003',
      materialName: '纺机轴承座',
      specification: '内径30mm',
      quantity: 200,
      unit: '件',
      complexity: '简单',
      processRequirements: ['车削', '钻孔']
    },
    {
      id: '4',
      materialCode: 'SY004',
      materialName: '纺机联轴器',
      specification: '弹性联轴器',
      quantity: 80,
      unit: '件',
      complexity: '中等',
      processRequirements: ['车削', '铣削', '装配']
    },
    {
      id: '5',
      materialCode: 'SY005',
      materialName: '纺机皮带轮',
      specification: 'Φ150mm',
      quantity: 120,
      unit: '件',
      complexity: '简单',
      processRequirements: ['车削', '滚齿']
    },
    {
      id: '6',
      materialCode: 'SY006',
      materialName: '纺机导丝轮',
      specification: 'Φ80×20mm',
      quantity: 150,
      unit: '件',
      complexity: '简单',
      processRequirements: ['车削', '抛光']
    },
    {
      id: '7',
      materialCode: 'SY007',
      materialName: '纺机张力器',
      specification: '弹簧张力器',
      quantity: 60,
      unit: '件',
      complexity: '中等',
      processRequirements: ['车削', '弹簧装配', '调校']
    },
    {
      id: '8',
      materialCode: 'SY008',
      materialName: '纺机罗拉',
      specification: 'Φ25×200mm',
      quantity: 300,
      unit: '件',
      complexity: '中等',
      processRequirements: ['车削', '表面处理', '动平衡']
    },
    {
      id: '9',
      materialCode: 'SY009',
      materialName: '纺机锭子',
      specification: '高速锭子',
      quantity: 180,
      unit: '件',
      complexity: '复杂',
      processRequirements: ['精密加工', '热处理', '动平衡', '装配']
    },
    {
      id: '10',
      materialCode: 'SY010',
      materialName: '纺机钢领',
      specification: 'Φ42mm',
      quantity: 250,
      unit: '件',
      complexity: '中等',
      processRequirements: ['车削', '磨削', '表面涂层']
    },
    {
      id: '11',
      materialCode: 'SY011',
      materialName: '纺机锭脚',
      specification: '铝合金锭脚',
      quantity: 180,
      unit: '件',
      complexity: '简单',
      processRequirements: ['压铸', '机加工', '表面处理']
    },
    {
      id: '12',
      materialCode: 'SY012',
      materialName: '纺机锭翼',
      specification: '铝合金锭翼',
      quantity: 180,
      unit: '件',
      complexity: '复杂',
      processRequirements: ['压铸', '精密加工', '动平衡', '表面处理']
    }
  ]

  // 智能关键词匹配
  const keywords = query.toLowerCase()

  // 如果查询包含"纺机"相关词汇，返回所有纺机物料
  if (keywords.includes('纺机') || keywords.includes('纺') || keywords.includes('机械') ||
    keywords.includes('主轴') || keywords.includes('齿轮') || keywords.includes('轴承') ||
    keywords.includes('联轴器') || keywords.includes('皮带轮') || keywords.includes('导丝轮') ||
    keywords.includes('张力器') || keywords.includes('罗拉') || keywords.includes('锭子') ||
    keywords.includes('钢领') || keywords.includes('锭脚') || keywords.includes('锭翼')) {
    return allMaterials
  }

  // 如果查询包含特定物料编号，精确匹配这些物料
  const materialCodes = ['sy005', 'sy006', 'sy009', 'sy010', 'sy012']
  const hasSpecificCodes = materialCodes.some(code => keywords.includes(code))
  
  if (hasSpecificCodes) {
    return allMaterials.filter(material => 
      materialCodes.includes(material.materialCode.toLowerCase())
    )
  }

  // 精确匹配
  return allMaterials.filter(material =>
    material.materialName.toLowerCase().includes(keywords) ||
    material.materialCode.toLowerCase().includes(keywords) ||
    material.specification.toLowerCase().includes(keywords)
  )
}

// 开始核价处理
const startPricingWithMaterials = async (materials: MaterialData[]) => {
  isProcessing.value = true
  currentStep.value = 0
  processingMessage.value = '正在初始化核查分析...'

  try {
    // 初始loading 1-5秒随机
    await sleep(getRandomWaitTime())
    
    // 步骤1：搜索物料
    currentStep.value = 1
    processingMessage.value = '正在搜索物料数据...'
    await sleep(getRandomWaitTime())

    // 步骤2：数据解析
    currentStep.value = 2
    processingMessage.value = '正在解析物料数据...'
    await sleep(getRandomWaitTime())

    // 步骤3：成本核算
    currentStep.value = 3
    processingMessage.value = '正在计算内部制造成本...'
    await sleep(getRandomWaitTime())

    // 步骤4：外协分析
    currentStep.value = 4
    processingMessage.value = '正在分析外协加工可行性...'
    await sleep(getRandomWaitTime())

    // 步骤5：生成核价报告
    currentStep.value = 5
    processingMessage.value = '正在生成核价报告...'
    await sleep(getRandomWaitTime())

    // 调用核价API，转换字段名称以匹配后端期望的格式
    const formattedMaterials = materials.map(material => ({
      material_code: material.materialCode,
      material_name: material.materialName,
      specification: material.specification,
      quantity: material.quantity,
      unit: material.unit,
      complexity: material.complexity,
      process_requirements: material.processRequirements
    }))

    const { data } = await apiClient.post('/api/pricing/batch-calculate', {
      materials: formattedMaterials
    })

    if (data.success) {
      // 步骤6：完成
      currentStep.value = 6
      processingMessage.value = '核价分析完成！'

      messages.push({
        role: 'ai',
        content: '',
        type: 'pricing_results',
        results: data.data
      })

      message.success(`成功完成 ${data.data.length} 项核价分析`)

      // 等待DOM更新后滚动到底部
      await nextTick()
      scrollToBottom()
    } else {
      throw new Error('核价计算失败')
    }

  } catch (error) {
    message.error('核价处理失败')
  } finally {
    setTimeout(() => {
      isProcessing.value = false
      processingMessage.value = ''
    }, 500)
  }
}

// 获取当前核价结果
const getCurrentPricingResults = (): PricingResult[] => {
  const lastMessage = messages[messages.length - 1]
  return lastMessage?.type === 'pricing_results' ? lastMessage.results || [] : []
}

// 滚动到底部
const scrollToBottom = () => {
  const chatWindow = document.querySelector('.chat-window')
  if (chatWindow) {
    chatWindow.scrollTop = chatWindow.scrollHeight
  }
}

// 确认单个项目
const approveItem = (record: PricingResult) => {
  record.status = 'approved'
  record.approval_time = new Date().toISOString()
  record.approved_by = '当前用户'
  message.success('项目确认成功')
}

// 批量确认
const approveAll = () => {
  const currentResults = getCurrentPricingResults()
  const pendingCount = currentResults.filter(item => item.status === 'pending').length

  currentResults.forEach(item => {
    if (item.status === 'pending') {
      item.status = 'approved'
      item.approval_time = new Date().toISOString()
      item.approved_by = '当前用户'
    }
  })

  message.success(`批量确认完成，共确认 ${pendingCount} 个项目`)
}

// 保存结果
const saveResults = async () => {
  try {
    const currentResults = getCurrentPricingResults()
    const approvedResults = currentResults.filter(r => r.status === 'approved')

    if (approvedResults.length === 0) {
      message.warning('没有已确认的核价结果需要保存')
      return
    }

    // 直接使用后端返回的数据格式
    const formattedResults = approvedResults.map(result => ({
      material_code: result.material_code,
      material_name: result.material_name,
      specification: result.specification,
      quantity: result.quantity,
      unit: result.unit,
      internal_cost: result.internal_cost,
      external_cost: result.external_cost,
      cost_difference: result.cost_difference,
      recommendation: result.recommendation,
      status: result.status,
      approval_time: result.approval_time,
      approved_by: result.approved_by
    }))

    const { data } = await apiClient.post('/api/pricing/save-results', {
      results: formattedResults
    })

    if (data.success) {
      message.success(`核价记录保存成功，共保存 ${approvedResults.length} 条记录`)
    } else {
      throw new Error('保存失败')
    }
  } catch (error) {
    message.error('保存失败')
  }
}

// 工具函数
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// 生成1-3秒之间的随机等待时间
const getRandomWaitTime = () => Math.floor(Math.random() * 2000) + 1000 // 1000-3000ms

const getStatusColor = (status: string) => {
  const colors: { [key: string]: string } = { pending: 'orange', approved: 'green', rejected: 'red' }
  return colors[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: { [key: string]: string } = { pending: '待确认', approved: '已确认', rejected: '已拒绝' }
  return texts[status] || status
}

const getRecommendationClass = (recommendation: string) => {
  if (recommendation.includes('✅')) return 'recommendation-good'
  if (recommendation.includes('❌')) return 'recommendation-bad'
  if (recommendation.includes('⚠️')) return 'recommendation-warning'
  return 'recommendation-normal'
}
</script>

<style scoped>
/* 重置父级容器样式 */
:deep(.app-content) {
  height: 100vh !important;
  overflow: hidden !important;
  padding: 0 !important;
}

:deep(.page-container) {
  height: 100vh !important;
  overflow: hidden !important;
  padding: 0 !important;
  margin: 0 !important;
  max-width: none !important;
}

/* 主容器 - 使用flex布局 */
/* 布局分配：标题60px + 聊天内容(剩余) + 处理进度120px(条件显示) + 输入框80px = 100vh */
.pricing-agent-page {
  height: calc(100vh - 176px);
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
  position: relative;
}

/* 确保flex子元素正确工作 */
.pricing-agent-page > * {
  box-sizing: border-box;
}

.chat-header {
  flex: 0 0 60px; /* 固定高度60px */
  padding: 12px 24px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
  display: flex;
  align-items: center;
}

.chat-header h3 {
  margin: 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.chat-window {
  flex: 1 1 0; /* 占据剩余所有空间 */
  overflow-y: auto;
  padding: 16px 24px;
  min-height: 0; /* 重要：允许flex子元素收缩 */
}

.msg {
  display: flex;
  margin: 12px 0;
}

.msg.user {
  justify-content: flex-end;
}

.bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-wrap: break-word;
}

.bubble.user {
  background: #e6f4ff;
  color: #1890ff;
  border-bottom-right-radius: 4px;
}

.bubble.ai {
  background: #f5f5f5;
  color: #333;
  border-bottom-left-radius: 4px;
}

.materials-display,
.pricing-results-display {
  margin-top: 12px;
  width: 100%;
}

/* 表格样式优化 */
:deep(.ant-table) {
  margin-bottom: 0;
  width: 100%;
}

:deep(.ant-table-wrapper) {
  width: 100%;
}

.materials-header,
.results-header {
  margin-bottom: 12px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.materials-header h4,
.results-header h4 {
  margin: 0;
  color: #1890ff;
  font-size: 16px;
}

.materials-header p {
  margin: 4px 0 8px 0;
  color: #666;
  font-size: 14px;
}

.processing-display {
  flex: 0 0 120px; /* 固定高度120px */
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin: 16px 0;
}

.processing-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: #666;
  font-size: 14px;
}

.input-bar {
  flex: 0 0 80px; /* 固定高度80px */
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

/* 三个点闪烁动画 */
.typing-animation {
  display: flex;
  align-items: center;
  gap: 4px;
}

.typing-dots {
  display: flex;
  gap: 2px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #1890ff;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.3;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 建议样式 */
.recommendation-good {
  color: #52c41a;
  font-weight: 500;
}

.recommendation-bad {
  color: #ff4d4f;
  font-weight: 500;
}

.recommendation-warning {
  color: #faad14;
  font-weight: 500;
}

.recommendation-normal {
  color: #666;
}

/* 表格样式优化 */
:deep(.ant-table-thead > tr > th) {
  background: #fafafa;
  font-weight: 600;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background: #f5f5f5;
}

/* 建议列单元格样式 */
:deep(.ant-table-tbody > tr > td) {
  white-space: normal;
  word-wrap: break-word;
  line-height: 1.4;
  vertical-align: top;
}

:deep(.ant-table-tbody > tr > td .recommendation-good),
:deep(.ant-table-tbody > tr > td .recommendation-warning),
:deep(.ant-table-tbody > tr > td .recommendation-normal) {
  white-space: normal;
  word-wrap: break-word;
  word-break: break-all;
  line-height: 1.4;
  display: inline-block;
  max-width: 280px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .pricing-agent-page {
    padding: 8px;
  }

  .agent-info {
    flex-direction: column;
    text-align: center;
  }

  .materials-header,
  .results-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}

/* 动画效果 */
.chat-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.chat-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

/* 按钮样式 */
:deep(.ant-btn-primary) {
  background: #1677ff;
  border-color: #1677ff;
  box-shadow: 0 2px 4px rgba(22, 119, 255, 0.2);
}

:deep(.ant-btn-primary:hover) {
  background: #4096ff;
  border-color: #4096ff;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(22, 119, 255, 0.3);
}

/* 步骤条样式 */
:deep(.ant-steps-item-process .ant-steps-item-icon) {
  background: #1677ff;
  border-color: #1677ff;
}

:deep(.ant-steps-item-finish .ant-steps-item-icon) {
  background: #52c41a;
  border-color: #52c41a;
}

/* 滚动条样式 */
.chat-window::-webkit-scrollbar {
  width: 6px;
}

.chat-window::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.chat-window::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.chat-window::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>
