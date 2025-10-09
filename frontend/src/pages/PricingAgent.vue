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
          <div v-if="m.type === 'text'" v-html="renderMarkdown(m.content)"></div>
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
          <!-- 批量核价聊天气泡：内置上传/预览/执行/导出/审批 -->
          <div v-else-if="m.type === 'batch'" class="batch-display">
            <div class="results-header">
              <h4>🗂 批量核价助手</h4>
            </div>
            <a-space direction="vertical" style="width: 100%">
              <a-upload :show-upload-list="false" :before-upload="() => false" @change="onBatchFileChange">
                <a-button type="primary">选择Excel文件（.xlsx）</a-button>
              </a-upload>
              <div v-if="batchFileName">已选择：{{ batchFileName }}</div>
              <a-space>
                <a-button type="primary" :disabled="!batchFile" @click="batchUpload">上传并预览</a-button>
                <a-button :disabled="!batchTraceId" @click="batchRun">执行核价</a-button>
                <a-button :disabled="!batchTraceId" @click="batchRefresh">刷新结果</a-button>
                <a-button :disabled="!batchTraceId" @click="batchExport">导出CSV</a-button>
                <a-button :disabled="!batchTraceId" @click="batchApprove">提交领导确认</a-button>
              </a-space>

              <a-alert v-if="batchTraceId" type="success" show-icon>
                <template #message>
                  任务 TraceID: <code>{{ batchTraceId }}</code>，共 {{ batchTotalRows }} 行
                </template>
              </a-alert>

              <a-table v-if="batchPreviewRows.length" :data-source="batchPreviewRows" :columns="batchPreviewColumns" :pagination="false" size="small" />

              <a-table v-if="batchResults.rows.length" :data-source="batchResults.rows" :columns="batchResultColumns" :pagination="{ current: batchPage, pageSize: batchPageSize, total: batchResults.total, onChange: onBatchPage }" row-key="id" size="small" />
            </a-space>
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
import { marked } from 'marked'

// 物料数据接口
interface MaterialData {
  id: string
  material_code: string      // 物料编码
  material_name: string      // 物料名称
  specification: string     // 规格型号
  quantity: number         // 数量
  unit: string            // 单位
  complexity: string      // 复杂度等级
  process_requirements: string // 工艺要求（字符串格式）
  estimated_price?: number  // 预估价格
  status?: string         // 状态
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
const messages = reactive<Array<{ role: 'user' | 'ai', content: string, type?: 'text' | 'typing' | 'materials' | 'pricing_results' | 'batch', materials?: MaterialData[], results?: PricingResult[] }>>([
  { role: 'ai', content: '你好，我是 AI 核价智能体。请告诉我你需要核价的物料信息。', type: 'text' }
])

// 表格列定义
const materialColumns = [
  { title: '物料编码', dataIndex: 'material_code', key: 'material_code', width: 120 },
  { title: '物料名称', dataIndex: 'material_name', key: 'material_name', width: 150 },
  { title: '规格型号', dataIndex: 'specification', key: 'specification', width: 120 },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
  { title: '单位', dataIndex: 'unit', key: 'unit', width: 60 },
  { title: '复杂度', dataIndex: 'complexity', key: 'complexity', width: 80 },
  { title: '工艺要求', dataIndex: 'process_requirements', key: 'process_requirements', width: 150 },
  { title: '预估价格', dataIndex: 'estimated_price', key: 'estimated_price', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 }
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

// Markdown渲染函数
const renderMarkdown = (content: string): string => {
  if (!content) return ''
  const result = marked(content, {
    breaks: true,
    gfm: true
  })
  return typeof result === 'string' ? result : result.toString()
}

// 发送消息
const onSend = async () => {
  const q = input.value.trim()
  if (!q) return

  messages.push({ role: 'user', content: q })
  input.value = ''
  loading.value = true
  
  // 移动端收起软键盘
  if (window.innerWidth <= 991) {
    const inputElement = document.querySelector('.ant-input') as HTMLInputElement
    if (inputElement) {
      inputElement.blur()
    }
  }

  try {
    // 若识别到“批量核价”意图，进入批量流程气泡
    if (/批量|批量核价|excel|xlsx|导入|上传/.test(q)) {
      const typingIndex = messages.length
      messages.push({ role: 'ai', content: '正在准备批量核价流程', type: 'typing' })
      await sleep(400)
      messages.splice(typingIndex, 1)
      messages.push({ role: 'ai', content: '请上传Excel文件开始批量核价。', type: 'batch' })
      await nextTick(); scrollToBottom()
      return
    }

    // 显示AI思考中动画
    const typingIndex = messages.length
    messages.push({ role: 'ai', content: '正在思考', type: 'typing' })
    
    // 调用后端AI查询接口
    const { data } = await apiClient.post('/api/pricing/ai-query', { query: q })
    
    if (data.success) {
      // 移除思考中动画
      messages.splice(typingIndex, 1)
      
      const explanation: string | undefined = data.data?.explanation
      const rows: MaterialData[] = data.data?.rows || []
      
      if (explanation) {
        messages.push({ role: 'ai', content: explanation, type: 'text' })
      }
      
      if (rows.length > 0) {
        messages.push({ role: 'ai', content: '', type: 'materials', materials: rows })
      } else if (!explanation) {
        messages.push({ role: 'ai', content: '未找到相关物料数据，请尝试其他关键词或检查物料名称。', type: 'text' })
      }
    } else {
      messages.splice(typingIndex, 1)
      message.error('查询失败')
    }
  } catch (error: any) {
    // 异常时也移除动画
    const last = messages[messages.length - 1]
    if (last?.type === 'typing') messages.pop()
    message.error('查询失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
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
      material_code: material.material_code,
      material_name: material.material_name,
      specification: material.specification,
      quantity: material.quantity,
      unit: material.unit,
      complexity: material.complexity,
      process_requirements: material.process_requirements
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

// ========= 批量核价（聊天内） =========
const batchFile = ref<File | null>(null)
const batchFileName = ref('')
const batchTraceId = ref('')
const batchTotalRows = ref(0)
const batchPreviewRows = ref<any[]>([])
const batchPreviewColumns = ref<any[]>([])
const batchResults = ref<{ total: number; rows: any[] }>({ total: 0, rows: [] })
const batchPage = ref(1)
const batchPageSize = ref(10)

function onBatchFileChange(info: any) {
  const f = info.file?.originFileObj as File
  if (f) {
    batchFile.value = f
    batchFileName.value = f.name
  }
}

async function batchUpload() {
  if (!batchFile.value) return
  const form = new FormData()
  form.append('file', batchFile.value)
  form.append('task_name', '批量核价')
  const { data } = await apiClient.post('/api/pricing/batch/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  batchTraceId.value = data.trace_id
  batchTotalRows.value = data.total_rows
  batchPreviewRows.value = data.preview_rows
  batchPreviewColumns.value = Object.keys(batchPreviewRows.value[0] || {}).map(k => ({ title: k, dataIndex: k }))
}

async function batchRun() {
  if (!batchTraceId.value) return
  await apiClient.post(`/api/pricing/batch/${batchTraceId.value}/run`)
  await batchRefresh()
}

async function batchRefresh() {
  if (!batchTraceId.value) return
  const { data } = await apiClient.get(`/api/pricing/batch/${batchTraceId.value}/results`, { params: { status: 'all', pn: batchPage.value, ps: batchPageSize.value } })
  batchResults.value = data
}

function onBatchPage(p: number, ps: number) {
  batchPage.value = p
  batchPageSize.value = ps
  batchRefresh()
}

async function batchExport() {
  if (!batchTraceId.value) return
  const res = await fetch(`/api/pricing/batch/${batchTraceId.value}/export?format=csv`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${batchTraceId.value}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function batchApprove() {
  if (!batchTraceId.value) return
  await apiClient.post(`/api/pricing/batch/${batchTraceId.value}/approve`, { approve: true })
}

const batchResultColumns = [
  { title: '物料编码', dataIndex: 'material_code', key: 'material_code', width: 120 },
  { title: '物料名称', dataIndex: 'material_name', key: 'material_name', width: 150 },
  { title: '规格型号', dataIndex: 'specification', key: 'specification', width: 120 },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
  { title: '单位', dataIndex: 'uom', key: 'uom', width: 60 },
  { title: '核算价(元)', dataIndex: 'estimated_price', key: 'estimated_price', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '备注', dataIndex: 'reason_or_notes', key: 'reason_or_notes', width: 200 }
]

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
  flex: 0 0 112px; /* 稍微减小 */
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  margin: 12px 0;
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
  flex: 0 0 64px; /* 更紧凑 */
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
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
    padding: 6px;
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

/* 对齐报工智能体的移动端边距与高度策略 */
@media (max-width: 991px) {
  .chat-header { padding: 12px; }
  .chat-window { padding: 8px 12px; }
  .input-bar { flex: 0 0 56px; padding: 8px 12px; }
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

/* Markdown样式 */
.bubble.ai :deep(h1),
.bubble.ai :deep(h2),
.bubble.ai :deep(h3),
.bubble.ai :deep(h4),
.bubble.ai :deep(h5),
.bubble.ai :deep(h6) {
  margin: 8px 0 4px 0;
  font-weight: 600;
  color: #333;
}

.bubble.ai :deep(p) {
  margin: 4px 0;
  line-height: 1.6;
}

.bubble.ai :deep(ul),
.bubble.ai :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.bubble.ai :deep(li) {
  margin: 2px 0;
  line-height: 1.5;
}

.bubble.ai :deep(strong) {
  font-weight: 600;
  color: #1890ff;
}

.bubble.ai :deep(em) {
  font-style: italic;
  color: #666;
}

.bubble.ai :deep(code) {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.bubble.ai :deep(pre) {
  background: #f5f5f5;
  padding: 8px 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

.bubble.ai :deep(blockquote) {
  border-left: 3px solid #1890ff;
  padding-left: 12px;
  margin: 8px 0;
  color: #666;
  font-style: italic;
}
</style>
