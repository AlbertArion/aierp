<template>
  <div class="page-container batch-pricing">
    <a-card title="批量核价" :bordered="false">
      <a-space direction="vertical" style="width: 100%">
        <a-upload
          :show-upload-list="false"
          :before-upload="() => false"
          :accept="'.xlsx,.xls'"
          :max-count="1"
          @change="onFileChange"
        >
          <a-button type="primary">选择Excel文件（.xlsx）</a-button>
        </a-upload>
        <div v-if="fileName">已选择：{{ fileName }}</div>
        <a-button type="primary" :disabled="!file" @click="upload">上传并预览</a-button>

        <a-alert v-if="traceId" type="success" show-icon>
          <template #message>
            任务已创建 TraceID: <code>{{ traceId }}</code>，共 {{ totalRows }} 行
          </template>
        </a-alert>

        <a-table v-if="previewRows.length" :data-source="previewRows" :columns="previewColumns" :pagination="false" size="small" />

        <a-space>
          <a-button type="primary" :disabled="!traceId" @click="run">执行核价</a-button>
          <a-button :disabled="!traceId" @click="refreshResults">刷新结果</a-button>
          <a-button :disabled="!traceId" @click="exportCsv">导出CSV</a-button>
          <a-button :disabled="!traceId" @click="approve">提交领导确认</a-button>
        </a-space>

        <a-table
          v-if="results.rows.length"
          :data-source="results.rows"
          :columns="resultColumns"
          :pagination="{ current: page, pageSize: pageSize, total: results.total, onChange: onPage }"
          row-key="id"
          size="small"
        />
      </a-space>
    </a-card>
  </div>
  
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import axios from '../utils/axios'

const file = ref<File | null>(null)
const fileName = ref('')
const traceId = ref('')
const totalRows = ref(0)
const previewRows = ref<any[]>([])
const previewColumns = ref<any[]>([])
const results = ref<{ total: number; rows: any[] }>({ total: 0, rows: [] })
const page = ref(1)
const pageSize = ref(10)

function onFileChange(info: any) {
  // 兼容多种事件结构
  const candidate = info?.file?.originFileObj || info?.file || info
  if (candidate && candidate.name) {
    file.value = candidate as File
    fileName.value = (candidate as File).name
    console.log('[BatchPricing] selected file:', fileName.value)
  } else if (info?.target?.files?.[0]) {
    file.value = info.target.files[0]
    fileName.value = info.target.files[0].name
    console.log('[BatchPricing] selected file via input:', fileName.value)
  } else {
    console.warn('[BatchPricing] onFileChange: 未获取到文件对象', info)
  }
}

async function upload() {
  if (!file.value) return
  const form = new FormData()
  form.append('file', file.value)
  form.append('task_name', '批量核价')
  const { data } = await axios.post('/api/pricing/batch/upload', form)
  traceId.value = data.trace_id
  totalRows.value = data.total_rows
  previewRows.value = data.preview_rows
  previewColumns.value = Object.keys(previewRows.value[0] || {}).map(k => ({ title: k, dataIndex: k }))
}

async function run() {
  if (!traceId.value) return
  await axios.post(`/api/pricing/batch/${traceId.value}/run`)
  await refreshResults()
}

async function refreshResults() {
  if (!traceId.value) return
  const { data } = await axios.get(`/api/pricing/batch/${traceId.value}/results`, { params: { status: 'all', pn: page.value, ps: pageSize.value } })
  results.value = data
}

function onPage(p: number, ps: number) {
  page.value = p
  pageSize.value = ps
  refreshResults()
}

async function exportCsv() {
  if (!traceId.value) return
  const res = await fetch(`/api/pricing/batch/${traceId.value}/export?format=csv`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${traceId.value}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function approve() {
  if (!traceId.value) return
  await axios.post(`/api/pricing/batch/${traceId.value}/approve`, { approve: true })
}
</script>

<style scoped>
.batch-pricing {
  padding: 16px;
}
</style>


