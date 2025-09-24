<template>
  <div class="chat-page">
    <a-card title="报工对话查询">
      <div class="chat-window">
        <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
          <div v-if="m.role==='user'" class="bubble user">{{ m.content }}</div>
          <div v-else class="bubble ai">
            <div v-if="m.type==='text'">{{ m.content }}</div>
            <div v-else-if="m.type==='table'">
              <a-table :columns="columns" :data-source="m.rows" :pagination="false" row-key="id" size="small" />
            </div>
          </div>
        </div>
      </div>
      <div class="input-bar">
        <a-input
          v-model:value="input"
          placeholder="例如：查询AI智能助手项目的报工情况 / 查询王五9月的报工"
          @pressEnter="onSend"
        />
        <a-button type="primary" :loading="loading" @click="onSend">发送</a-button>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import apiClient from '../utils/axios'
import { message } from 'ant-design-vue'

type ChatRow = any

const input = ref('')
const loading = ref(false)
const messages = reactive<Array<{role:'user'|'ai', content:string, type?:'text'|'table', rows?:ChatRow[]}>>([
  { role: 'ai', content: '你好，我是报工智能体。直接用自然语言问我，例如：“查询AI智能助手项目的报工情况”。', type: 'text' }
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

const onSend = async () => {
  const q = input.value.trim()
  if (!q) return
  messages.push({ role: 'user', content: q })
  input.value = ''
  loading.value = true
  try {
    const { data } = await apiClient.post('/api/work-reports/ai-query', { query: q, size: 20 })
    if (data.success) {
      const rows = data.data?.data || []
      if (rows.length === 0) {
        messages.push({ role: 'ai', content: '未找到相关报工记录，可尝试更换关键词。', type: 'text' })
      } else {
        messages.push({ role: 'ai', content: '为你找到如下报工记录：', type: 'text' })
        messages.push({ role: 'ai', content: '', type: 'table', rows })
      }
    } else {
      message.error('查询失败')
    }
  } catch (e: any) {
    message.error('查询失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.chat-page { padding: 16px; }
.chat-window { max-height: 60vh; overflow-y: auto; padding: 8px 0; }
.msg { display: flex; margin: 8px 0; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 80%; padding: 8px 12px; border-radius: 8px; line-height: 1.6; }
.bubble.user { background: #e6f4ff; }
.bubble.ai { background: #f5f5f5; }
.input-bar { display: flex; gap: 8px; margin-top: 12px; }
</style>

