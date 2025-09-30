<template>
  <div class="work-agent-page">
    <div class="chat-header">
      <h3>💬 AI 报工智能体</h3>
    </div>
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
          <div v-else-if="m.type === 'table'" class="table-wrapper">
            <a-table
              :columns="columns"
              :data-source="m.rows"
              :pagination="false"
              row-key="id"
              size="small"
              :scroll="{ x: 720 }"
              class="chat-table"
            />
      </div>
        </div>
      </div>
    </div>
    <div class="input-bar">
      <a-input v-model:value="input" placeholder="例如：查询AI智能助手项目的报工情况 / 查询王五9月的报工" @pressEnter="onSend" />
      <a-button type="primary" :loading="loading" @click="onSend">发送</a-button>
      </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { reactive, ref, computed } from 'vue'
import apiClient from '../utils/axios'
import { marked } from 'marked'

type ChatRow = any

const input = ref('')
const loading = ref(false)
const messages = reactive<Array<{ role: 'user' | 'ai', content: string, type?: 'text' | 'table' | 'typing', rows?: ChatRow[] }>>([
  { role: 'ai', content: '你好，我是 AI 报工智能体。直接用自然语言问我，例如：“查询AI智能助手项目的报工情况”。', type: 'text' }
])

const columns = [
  { title: '员工姓名', dataIndex: 'employee_name', key: 'employee_name' },
  { title: '项目名称', dataIndex: 'project_name', key: 'project_name' },
  { title: '部门', dataIndex: 'department_name', key: 'department_name' },
  { title: '报工日期', dataIndex: 'report_date', key: 'report_date' },
  { title: '工作时长', dataIndex: 'work_hours', key: 'work_hours' },
  { title: '工作内容', dataIndex: 'work_content', key: 'work_content', ellipsis: true },
  { title: '工作地点', dataIndex: 'work_location', key: 'work_location' }
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
    const typingIndex = messages.length
    messages.push({ role: 'ai', content: '正在思考', type: 'typing' })
    // 强制清除缓存，添加随机参数
    const timestamp = Date.now()
    const random = Math.random().toString(36).substring(7)
    const { data } = await apiClient.post(`/api/work-reports/ai-query?_t=${timestamp}&_r=${random}`, { query: q, size: 20 })
    console.log('API响应数据:', data) // 调试信息
    console.log('请求时间戳:', timestamp) // 调试信息
    if (data.success) {
      messages.splice(typingIndex, 1)
      const explanation: string | undefined = data.data?.explanation
      const rows: ChatRow[] = data.data?.rows || []
      console.log('解析结果:', { explanation, rowsCount: rows.length }) // 调试信息
      if (explanation) {
        messages.push({ role: 'ai', content: explanation, type: 'text' })
      }
      if (rows.length > 0) {
        messages.push({ role: 'ai', content: '', type: 'table', rows })
      } else if (!explanation) {
        messages.push({ role: 'ai', content: '未找到相关报工记录，可尝试更换关键词。', type: 'text' })
      }
    } else {
      messages.splice(typingIndex, 1)
      message.error('查询失败')
    }
  } catch (e: any) {
    const last = messages[messages.length - 1]
    if (last?.type === 'typing') messages.pop()
    message.error('查询失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
::deep(.app-content) { height: 100vh !important; overflow: hidden !important; padding: 0 !important; }
::deep(.page-container) { height: 100vh !important; overflow: hidden !important; padding: 0 !important; margin: 0 !important; max-width: none !important; }

.work-agent-page { height: calc(100vh - 176px); display: flex; flex-direction: column; background: white; overflow: hidden; position: relative; }
.work-agent-page > * { box-sizing: border-box; }

.chat-header { flex: 0 0 60px; padding: 12px 24px; border-bottom: 1px solid #f0f0f0; background: #fafafa; display:flex; align-items:center; }
.chat-header h3 { margin: 0; color: #333; font-size: 16px; font-weight: 600; }

.chat-window { flex: 1 1 0; overflow-y: auto; padding: 16px 24px; min-height: 0; }
.msg { display: flex; margin: 12px 0; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; word-wrap: break-word; }
.bubble.user { background: #e6f4ff; color: #1890ff; border-bottom-right-radius: 4px; }
.bubble.ai { background: #f5f5f5; color: #333; border-bottom-left-radius: 4px; }

.table-wrapper { width: 100%; overflow-x: auto; }
.table-wrapper::-webkit-scrollbar { height: 6px; }
.table-wrapper::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 3px; }
.table-wrapper::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 3px; }

.input-bar { flex: 0 0 64px; display: flex; gap: 12px; align-items: center; padding: 12px 16px; background: white; border-top: 1px solid #f0f0f0; }

/* typing 动画 */
.typing-animation { display: flex; align-items: center; gap: 6px; }
.typing-dots { display: flex; gap: 3px; }
.typing-dots span { width: 6px; height: 6px; border-radius: 50%; background-color: #1890ff; animation: typing 1.4s infinite ease-in-out; }
.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
.typing-dots span:nth-child(3) { animation-delay: 0s; }
@keyframes typing {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
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

@media (max-width: 991px) {
  .chat-window { padding: 8px; }
  .input-bar { flex: 0 0 56px; padding: 8px 12px; }
}
</style>
