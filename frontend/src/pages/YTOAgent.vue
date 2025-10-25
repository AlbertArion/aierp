<template>
  <div class="chat-page">
    <div class="chat-header">
      <h2>AI 报价智能体</h2>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div v-for="(message, index) in messages" :key="index" class="message" :class="message.type">
        <div class="message-content">
          <div v-if="message.type === 'user'" class="user-message">
            <div class="message-text">{{ message.content }}</div>
          </div>
          <div v-else-if="message.type === 'ai'" class="ai-message">
            <div class="message-content-wrapper" :class="{ 'thinking-message': message.isThinking }">
              <div class="message-text" v-html="renderMarkdown(message.content || '')"></div>
              <div v-if="message.isThinking" class="thinking-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
          <div v-else-if="message.type === 'data'" class="data-message">
            <div class="data-header">
              <span class="data-title">{{ message.title }}</span>
              <div class="data-actions">
                <a-button size="small" @click="selectAll" v-if="message.selectable">全选</a-button>
                <a-button size="small" @click="deselectAll" v-if="message.selectable">取消全选</a-button>
                <a-button type="primary" size="small" @click="calculatePrices"
                  v-if="message.calculatable">计算</a-button>
                <a-button type="primary" size="small" @click="generateInvoice"
                  v-if="message.invoiceable">开票</a-button>
              </div>
            </div>
            <div class="data-content">
              <a-table :data-source="message.data" :columns="message.columns" :pagination="false"
                size="small" :scroll="{ x: 1200 }">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'select'">
                    <a-checkbox v-model:checked="record.selected" />
                  </template>
                  <template v-else-if="column.key === 'price'">
                    <span class="price-cell">¥{{ formatPrice(record.price) }}</span>
                  </template>
                  <template v-else-if="column.key === 'status'">
                    <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'invoiceNumber'">
                    <a-button type="link" @click="showInvoiceDetail(record)" class="detail-link">
                      {{ record.invoiceNumber }}
                    </a-button>
                  </template>
                </template>
              </a-table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <div class="input-wrapper">
        <a-input v-model:value="inputMessage" placeholder="请输入指令，例如：查询今日新增物料信息、对今日已发货的销售订单进行开票"
          @press-enter="sendMessage" :loading="isLoading" class="message-input">
          <template #suffix>
            <a-button type="primary" @click="sendMessage" :loading="isLoading" :disabled="!inputMessage.trim()"
              class="send-button">
              发送
            </a-button>
          </template>
        </a-input>
      </div>
      <div class="example-commands">
        <span class="example-label">示例指令：</span>
        <a-tag @click="sendExampleCommand('查询今日新增物料信息')" class="example-tag">查询今日新增物料信息</a-tag>
        <a-tag @click="sendExampleCommand('对今日已发货的销售订单进行开票')" class="example-tag">对今日已发货的销售订单进行开票</a-tag>
        <a-tag @click="sendExampleCommand('计算今日新增物料价格')" class="example-tag">计算今日新增物料价格</a-tag>
      </div>
    </div>

    <!-- 开票详情弹窗 -->
    <a-modal
      v-model:open="detailModalVisible"
      title="开票详情"
      :width="600"
      :footer="null"
      @cancel="closeDetailModal"
    >
      <div v-if="selectedInvoiceDetail" class="invoice-detail">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="发票号">
            <span class="detail-value">{{ selectedInvoiceDetail.invoiceNumber }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="订单号">
            <span class="detail-value">{{ selectedInvoiceDetail.orderNumber }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="客户名称">
            <span class="detail-value">{{ selectedInvoiceDetail.customer }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="开票日期">
            <span class="detail-value">{{ selectedInvoiceDetail.date }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="发票金额">
            <span class="detail-value amount">¥{{ formatPrice(selectedInvoiceDetail.amount) }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="税额">
            <span class="detail-value">¥{{ formatPrice(selectedInvoiceDetail.tax) }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="合计金额" :span="2">
            <span class="detail-value total-amount">¥{{ formatPrice(selectedInvoiceDetail.total) }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="开票状态" :span="2">
            <a-tag :color="getStatusColor(selectedInvoiceDetail.status)" size="large">
              {{ selectedInvoiceDetail.status }}
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>
        
        <div class="detail-actions">
          <a-button type="primary" @click="closeDetailModal">关闭</a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script lang="ts" setup>
import { ref, nextTick, onMounted } from 'vue'
import { marked } from 'marked'

interface Message {
  type: 'user' | 'ai' | 'data'
  content?: string
  title?: string
  data?: any[]
  columns?: any[]
  time: string
  selectable?: boolean
  calculatable?: boolean
  invoiceable?: boolean
  isThinking?: boolean
}

const messages = ref<Message[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement>()

// 弹窗相关状态
const detailModalVisible = ref(false)
const selectedInvoiceDetail = ref<any>(null)

// 初始化演示数据
onMounted(() => {
  addWelcomeMessage()
})

function addWelcomeMessage() {
  messages.value.push({
    type: 'ai',
    content: '欢迎使用 AI 报价智能体！我可以帮您：\n\n1. **查询今日新增物料信息** - 获取最新的物料数据\n2. **计算物料价格** - 基于基配、选配参数自动计算价格\n3. **销售订单开票** - 对已发货订单自动开具发票\n\n请选择您需要的功能，或直接输入指令。',
    time: getCurrentTime()
  })
}

function getCurrentTime() {
  return ''
}

function renderMarkdown(content: string) {
  try {
    const result = marked(content, {
      breaks: true,
      gfm: true
    })
    return typeof result === 'string' ? result : result.toString()
  } catch (e) {
    return content
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isLoading.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  isLoading.value = true

  // 添加用户消息
  messages.value.push({
    type: 'user',
    content: userMessage,
    time: getCurrentTime()
  })

  await nextTick()
  scrollToBottom()

  // 显示AI思考中动画
  messages.value.push({
    type: 'ai',
    content: 'AI正在思考中...',
    time: getCurrentTime(),
    isThinking: true
  })
  
  await nextTick()
  scrollToBottom()

  // 根据查询类型设置不同的加载时间
  const isQueryType = userMessage.includes('查询') || userMessage.includes('物料') || userMessage.includes('开票')
  const loadingTime = isQueryType ? Math.random() * 2000 + 2000 : 1000 // 查询类2-4秒，其他1秒

  setTimeout(async () => {
    // 移除思考中消息
    messages.value = messages.value.filter(msg => !msg.isThinking)
    
    await handleUserQuery(userMessage)
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }, loadingTime)
}

async function sendExampleCommand(command: string) {
  if (isLoading.value) return
  
  inputMessage.value = command
  await sendMessage()
}

async function handleUserQuery(query: string) {
  const lowerQuery = query.toLowerCase()

  if (lowerQuery.includes('查询') && lowerQuery.includes('物料')) {
    await showMaterialData()
  } else if (lowerQuery.includes('开票') || lowerQuery.includes('发票')) {
    await showInvoiceData()
  } else if (lowerQuery.includes('计算') && lowerQuery.includes('价格')) {
    await showPricingData()
  } else {
    await showGeneralResponse()
  }
}

async function showMaterialData() {
  const mockMaterials = [
    {
      key: '1',
      order: '101363571',
      materialCode: '2216130212000580',
      description: 'LY1200E3Y0D71(副油箱)(20)',
      factory: '2216',
      startDate: '2025.01.15',
      selected: false
    },
    {
      key: '2',
      order: '101363572',
      materialCode: '2216130212000581',
      description: 'LY1200E3Y0D72(主油箱)(20)',
      factory: '2216',
      startDate: '2025.01.16',
      selected: false
    },
    {
      key: '3',
      order: '101363573',
      materialCode: '2217130212000582',
      description: 'LY1200E3Y0D73(发动机)(20)',
      factory: '2217',
      startDate: '2025.01.17',
      selected: false
    },
    {
      key: '4',
      order: '101363574',
      materialCode: '2217130212000583',
      description: 'LY1200E3Y0D74(变速箱)(20)',
      factory: '2217',
      startDate: '2025.01.18',
      selected: false
    },
    {
      key: '5',
      order: '101363575',
      materialCode: '2218130212000584',
      description: 'LY1200E3Y0D75(液压系统)(20)',
      factory: '2218',
      startDate: '2025.01.19',
      selected: false
    },
    {
      key: '6',
      order: '101363576',
      materialCode: '2218130212000585',
      description: 'LY1200E3Y0D76(电气系统)(20)',
      factory: '2218',
      startDate: '2025.01.20',
      selected: false
    },
    {
      key: '7',
      order: '101363577',
      materialCode: '2216130212000586',
      description: 'LY1200E3Y0D77(制动系统)(20)',
      factory: '2216',
      startDate: '2025.01.21',
      selected: false
    },
    {
      key: '8',
      order: '101363578',
      materialCode: '2217130212000587',
      description: 'LY1200E3Y0D78(转向系统)(20)',
      factory: '2217',
      startDate: '2025.01.22',
      selected: false
    }
  ]

  messages.value.push({
    type: 'ai',
    content: '已为您查询到今日新增的物料信息，共8条记录。您可以选择需要计算的物料，然后点击"计算"按钮进行价格计算。',
    time: getCurrentTime()
  })

  messages.value.push({
    type: 'data',
    title: '今日新增物料信息',
    data: mockMaterials,
    columns: [
      { title: '选择', key: 'select', width: 60 },
      { title: '订单', dataIndex: 'order', key: 'order', width: 120 },
      { title: '物料编号', dataIndex: 'materialCode', key: 'materialCode', width: 150 },
      { title: '描述', dataIndex: 'description', key: 'description', width: 200 },
      { title: '工厂', dataIndex: 'factory', key: 'factory', width: 80 },
      { title: '基本开始日期', dataIndex: 'startDate', key: 'startDate', width: 120 }
    ],
    selectable: true,
    calculatable: true,
    time: getCurrentTime()
  })

  await nextTick()
  scrollToBottom()
}

async function showPricingData() {
  const mockPricingResults = [
    {
      key: '1',
      factory: '2216',
      sapCode: '2216130212000580',
      description: 'LY1200E3Y0D71(副油箱)(20)',
      model: 'LY1200E3Y0D71',
      finalSalesPrice: 165037.00,
      finalTransferPrice: 219937.00,
      basePrice: 162800.00,
      baseTransferPrice: 217700.00,
      optionalAdjustment: 2237.00,
      airConditioning: 444.00,
      powerOutput: 555.00,
      crawl: 888.00,
      mp3: 350.00,
      selected: false
    },
    {
      key: '2',
      factory: '2216',
      sapCode: '2216130212000581',
      description: 'LY1200E3Y0D72(主油箱)(20)',
      model: 'LY1200E3Y0D72',
      finalSalesPrice: 185037.00,
      finalTransferPrice: 239937.00,
      basePrice: 182800.00,
      baseTransferPrice: 237700.00,
      optionalAdjustment: 3237.00,
      airConditioning: 544.00,
      powerOutput: 655.00,
      crawl: 988.00,
      mp3: 450.00,
      selected: false
    },
    {
      key: '3',
      factory: '2217',
      sapCode: '2217130212000582',
      description: 'LY1200E3Y0D73(发动机)(20)',
      model: 'LY1200E3Y0D73',
      finalSalesPrice: 205037.00,
      finalTransferPrice: 259937.00,
      basePrice: 202800.00,
      baseTransferPrice: 257700.00,
      optionalAdjustment: 4237.00,
      airConditioning: 644.00,
      powerOutput: 755.00,
      crawl: 1088.00,
      mp3: 550.00,
      selected: false
    },
    {
      key: '4',
      factory: '2217',
      sapCode: '2217130212000583',
      description: 'LY1200E3Y0D74(变速箱)(20)',
      model: 'LY1200E3Y0D74',
      finalSalesPrice: 225037.00,
      finalTransferPrice: 279937.00,
      basePrice: 222800.00,
      baseTransferPrice: 277700.00,
      optionalAdjustment: 5237.00,
      airConditioning: 744.00,
      powerOutput: 855.00,
      crawl: 1188.00,
      mp3: 650.00,
      selected: false
    },
    {
      key: '5',
      factory: '2218',
      sapCode: '2218130212000584',
      description: 'LY1200E3Y0D75(液压系统)(20)',
      model: 'LY1200E3Y0D75',
      finalSalesPrice: 245037.00,
      finalTransferPrice: 299937.00,
      basePrice: 242800.00,
      baseTransferPrice: 297700.00,
      optionalAdjustment: 6237.00,
      airConditioning: 844.00,
      powerOutput: 955.00,
      crawl: 1288.00,
      mp3: 750.00,
      selected: false
    },
    {
      key: '6',
      factory: '2218',
      sapCode: '2218130212000585',
      description: 'LY1200E3Y0D76(电气系统)(20)',
      model: 'LY1200E3Y0D76',
      finalSalesPrice: 265037.00,
      finalTransferPrice: 319937.00,
      basePrice: 262800.00,
      baseTransferPrice: 317700.00,
      optionalAdjustment: 7237.00,
      airConditioning: 944.00,
      powerOutput: 1055.00,
      crawl: 1388.00,
      mp3: 850.00,
      selected: false
    }
  ]

  messages.value.push({
    type: 'ai',
    content: '价格计算完成！基于产品的基配、选配参数，已为您计算出详细的销售价格。您可以选择需要开票的项目，然后点击"开票"按钮。',
    time: getCurrentTime()
  })

  messages.value.push({
    type: 'data',
    title: '物料价格计算结果',
    data: mockPricingResults,
    columns: [
      { title: '选择', key: 'select', width: 60 },
      { title: '工厂', dataIndex: 'factory', key: 'factory', width: 80 },
      { title: 'SAP码', dataIndex: 'sapCode', key: 'sapCode', width: 150 },
      { title: '物料描述', dataIndex: 'description', key: 'description', width: 200 },
      { title: '大类机型', dataIndex: 'model', key: 'model', width: 120 },
      { title: '最终销售价', dataIndex: 'finalSalesPrice', key: 'finalSalesPrice', width: 120 },
      { title: '最终转移价', dataIndex: 'finalTransferPrice', key: 'finalTransferPrice', width: 120 },
      { title: '基配出厂价', dataIndex: 'basePrice', key: 'basePrice', width: 120 },
      { title: '基配转移价', dataIndex: 'baseTransferPrice', key: 'baseTransferPrice', width: 120 },
      { title: '选配增减', dataIndex: 'optionalAdjustment', key: 'optionalAdjustment', width: 100 },
      { title: '暖风空调', dataIndex: 'airConditioning', key: 'airConditioning', width: 100 },
      { title: '动力输出', dataIndex: 'powerOutput', key: 'powerOutput', width: 100 },
      { title: '爬', dataIndex: 'crawl', key: 'crawl', width: 80 },
      { title: 'mp3', dataIndex: 'mp3', key: 'mp3', width: 80 }
    ],
    selectable: true,
    invoiceable: true,
    time: getCurrentTime()
  })

  await nextTick()
  scrollToBottom()
}

async function showInvoiceData() {
  // 获取今天的日期
  const today = new Date()
  const todayStr = today.toISOString().split('T')[0] // 格式：YYYY-MM-DD
  
  const mockInvoiceData = [
    {
      key: '1',
      invoiceNumber: 'INV-2025-001',
      orderNumber: '101363571',
      customer: '河南一拖经销商',
      amount: 165037.00,
      tax: 21454.81,
      total: 186491.81,
      status: '已开票',
      date: todayStr
    },
    {
      key: '2',
      invoiceNumber: 'INV-2025-002',
      orderNumber: '101363572',
      customer: '山东一拖经销商',
      amount: 185037.00,
      tax: 24054.81,
      total: 209091.81,
      status: '已开票',
      date: todayStr
    },
    {
      key: '3',
      invoiceNumber: 'INV-2025-003',
      orderNumber: '101363573',
      customer: '江苏一拖经销商',
      amount: 205037.00,
      tax: 26654.81,
      total: 231691.81,
      status: '已开票',
      date: todayStr
    },
    {
      key: '4',
      invoiceNumber: 'INV-2025-004',
      orderNumber: '101363574',
      customer: '广东一拖经销商',
      amount: 225037.00,
      tax: 29254.81,
      total: 254291.81,
      status: '已开票',
      date: todayStr
    },
    {
      key: '5',
      invoiceNumber: 'INV-2025-005',
      orderNumber: '101363575',
      customer: '河北一拖经销商',
      amount: 245037.00,
      tax: 31854.81,
      total: 276891.81,
      status: '已开票',
      date: todayStr
    },
    {
      key: '6',
      invoiceNumber: 'INV-2025-006',
      orderNumber: '101363576',
      customer: '四川一拖经销商',
      amount: 265037.00,
      tax: 34454.81,
      total: 299491.81,
      status: '已开票',
      date: todayStr
    }
  ]

  messages.value.push({
    type: 'ai',
    content: '开票完成！已为今日已发货的销售订单自动开具发票。以下是开票详情：',
    time: getCurrentTime()
  })

  messages.value.push({
    type: 'data',
    title: '销售订单开票结果',
    data: mockInvoiceData,
    columns: [
      { title: '发票号', dataIndex: 'invoiceNumber', key: 'invoiceNumber', width: 120 },
      { title: '订单号', dataIndex: 'orderNumber', key: 'orderNumber', width: 120 },
      { title: '客户', dataIndex: 'customer', key: 'customer', width: 150 },
      { title: '金额', dataIndex: 'amount', key: 'amount', width: 120 },
      { title: '税额', dataIndex: 'tax', key: 'tax', width: 120 },
      { title: '合计', dataIndex: 'total', key: 'total', width: 120 },
      { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
      { title: '开票日期', dataIndex: 'date', key: 'date', width: 120 }
    ],
    selectable: false,
    time: getCurrentTime()
  })

  await nextTick()
  scrollToBottom()
}

async function showGeneralResponse() {
  messages.value.push({
    type: 'ai',
    content: '我是报价智能助手，可以帮您处理以下业务：\n• **物料管理**：查询新增物料信息\n• **价格计算**：基于基配选配自动计算价格\n• **订单开票**：自动开具销售发票\n请告诉我您需要什么帮助？',
    time: getCurrentTime()
  })

  await nextTick()
  scrollToBottom()
}

function selectAll() {
  const lastDataMessage = messages.value.filter(m => m.type === 'data').pop()
  if (lastDataMessage?.data) {
    lastDataMessage.data.forEach((item: any) => {
      item.selected = true
    })
  }
}

function deselectAll() {
  const lastDataMessage = messages.value.filter(m => m.type === 'data').pop()
  if (lastDataMessage?.data) {
    lastDataMessage.data.forEach((item: any) => {
      item.selected = false
    })
  }
}

async function calculatePrices() {
  const selectedItems = getSelectedItems()
  if (selectedItems.length === 0) {
    messages.value.push({
      type: 'ai',
      content: '请先选择需要计算价格的物料！',
      time: getCurrentTime()
    })
    await nextTick()
    scrollToBottom()
    return
  }

  // 显示AI思考中动画
  messages.value.push({
    type: 'ai',
    content: 'AI正在思考中...',
    time: getCurrentTime(),
    isThinking: true
  })
  
  await nextTick()
  scrollToBottom()

  setTimeout(async () => {
    // 移除思考中消息
    messages.value = messages.value.filter(msg => !msg.isThinking)
    
    await showPricingData()
  }, 1500)
}

async function generateInvoice() {
  const selectedItems = getSelectedItems()
  if (selectedItems.length === 0) {
    messages.value.push({
      type: 'ai',
      content: '请先选择需要开票的项目！',
      time: getCurrentTime()
    })
    await nextTick()
    scrollToBottom()
    return
  }

  // 显示AI思考中动画
  messages.value.push({
    type: 'ai',
    content: 'AI正在思考中...',
    time: getCurrentTime(),
    isThinking: true
  })
  
  await nextTick()
  scrollToBottom()

  setTimeout(async () => {
    // 移除思考中消息
    messages.value = messages.value.filter(msg => !msg.isThinking)
    
    await showInvoiceData()
  }, Math.random() * 2000 + 4000) // 4-6秒随机时间
}

function getSelectedItems() {
  const lastDataMessage = messages.value.filter(m => m.type === 'data').pop()
  return lastDataMessage?.data?.filter((item: any) => item.selected) || []
}

function formatPrice(price: number) {
  return price.toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

function getStatusColor(status: string) {
  const colorMap: Record<string, string> = {
    '已开票': 'green',
    '待开票': 'orange',
    '已发货': 'blue',
    '已完成': 'green'
  }
  return colorMap[status] || 'default'
}

// 查看开票详情
function showInvoiceDetail(record: any) {
  selectedInvoiceDetail.value = record
  detailModalVisible.value = true
}

// 关闭详情弹窗
function closeDetailModal() {
  detailModalVisible.value = false
  selectedInvoiceDetail.value = null
}

// 移除不需要的rowSelection配置

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.chat-page {
  height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.chat-header {
  background: white;
  padding: 16px 24px;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.chat-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
}

.message {
  margin-bottom: 16px;
}

.user-message {
  display: flex;
  justify-content: flex-end;
}

.user-message .message-text {
  background: #1890ff;
  color: white;
  padding: 12px 16px;
  border-radius: 18px 18px 4px 18px;
  max-width: 70%;
  word-wrap: break-word;
}

.ai-message {
  display: flex;
  align-items: flex-start;
}

.message-content-wrapper {
  background: white;
  padding: 12px 16px;
  border-radius: 18px 18px 18px 4px;
  max-width: 80%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.message-text {
  line-height: 1.6;
}

.data-message {
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  margin: 16px 0;
}

.data-header {
  background: #f5f5f5;
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e8e8e8;
}

.data-title {
  font-weight: bold;
  font-size: 16px;
}

.data-actions {
  display: flex;
  gap: 8px;
}

.data-content {
  padding: 0;
}

/* 移除时间样式 */

.chat-input {
  background: white;
  padding: 16px 24px;
  border-top: 1px solid #e8e8e8;
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  z-index: 10;
}

.input-wrapper {
  margin-bottom: 12px;
}

.message-input {
  border-radius: 20px;
}

.send-button {
  border-radius: 20px;
  margin-left: 8px;
}

.example-commands {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.example-label {
  font-size: 14px;
  color: #666;
}

.example-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.example-tag:hover {
  background: #1890ff;
  color: white;
}

.price-cell {
  font-weight: bold;
  color: #52c41a;
}

:deep(.ant-table-thead > tr > th) {
  background: #fafafa;
  font-weight: bold;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background: #f0f9ff;
}

:deep(.ant-checkbox-wrapper) {
  margin-right: 0;
}

:deep(.ant-tag) {
  margin: 0;
}

/* AI思考中动画样式 */
.thinking-message {
  position: relative;
}

.thinking-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
}

.thinking-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #1890ff;
  animation: thinking-pulse 1.4s infinite ease-in-out;
}

.thinking-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

.thinking-dots span:nth-child(3) {
  animation-delay: 0s;
}

@keyframes thinking-pulse {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 详情链接样式 */
.detail-link {
  padding: 0;
  height: auto;
  color: #1890ff;
  text-decoration: none;
}

.detail-link:hover {
  color: #40a9ff;
  text-decoration: underline;
}

/* 开票详情弹窗样式 */
.invoice-detail {
  padding: 16px 0;
}

.detail-value {
  font-weight: 500;
  color: #333;
}

.detail-value.amount {
  color: #52c41a;
  font-weight: 600;
}

.detail-value.total-amount {
  color: #1890ff;
  font-weight: 700;
  font-size: 16px;
}

.detail-actions {
  margin-top: 24px;
  text-align: center;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

/* 移除不需要的样式 */
</style>
