<template>
  <div>
    <a-card title="订单检索">
      <a-space>
        <a-input v-model:value="keyword" placeholder="订单号/客户名" style="width:260px" />
        <a-button type="primary" @click="search">搜索</a-button>
      </a-space>
      <a-divider />
      <a-table :dataSource="items" :columns="columns" rowKey="id" :pagination="false" />
    </a-card>

    <a-card title="订单修改" style="margin-top:16px">
      <a-space>
        <a-input v-model:value="orderId" placeholder="订单ID" style="width:200px" />
        <a-input v-model:value="field" placeholder="字段" style="width:160px" />
        <a-input v-model:value="value" placeholder="值" style="width:200px" />
        <a-button @click="update">提交修改</a-button>
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import apiClient from '../utils/axios'

const keyword = ref('')
const items = ref<any[]>([])
const columns = [
  { title: 'ID', dataIndex: 'id' },
  { title: '客户', dataIndex: 'customer' },
  { title: '金额', dataIndex: 'amount' }
]

const orderId = ref('')
const field = ref('status')
const value = ref('approved')

const search = async () => {
  const { data } = await apiClient.get('/api/orders/search', { params: { keyword: keyword.value, page: 1, size: 10 } })
  items.value = data.items
}

const update = async () => {
  await apiClient.put('/api/orders/update', { order_id: orderId.value, field: field.value, value: value.value })
}
</script>

<style scoped>
/* 深色模式下的Orders页面优化 */
[data-theme="dark"] .ant-input::placeholder {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-input {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  color: #e2e8f0 !important;
  border-radius: 8px !important;
  transition: all 0.3s ease !important;
}

[data-theme="dark"] .ant-input:hover {
  border-color: rgba(22, 119, 255, 0.5) !important;
  background: rgba(255, 255, 255, 0.08) !important;
}

[data-theme="dark"] .ant-input:focus {
  border-color: #1677ff !important;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2) !important;
  background: rgba(255, 255, 255, 0.1) !important;
}

[data-theme="dark"] .ant-table {
  background: transparent !important;
  color: #e2e8f0 !important;
}

[data-theme="dark"] .ant-table-thead > tr > th {
  background: rgba(255, 255, 255, 0.05) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: #e2e8f0 !important;
  font-weight: 600 !important;
}

[data-theme="dark"] .ant-table-tbody > tr > td {
  background: transparent !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
  color: #cbd5e1 !important;
}

[data-theme="dark"] .ant-table-tbody > tr:hover > td {
  background: rgba(22, 119, 255, 0.1) !important;
}

[data-theme="dark"] .ant-table-tbody > tr.ant-table-row-selected > td {
  background: rgba(22, 119, 255, 0.15) !important;
}

[data-theme="dark"] .ant-empty {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-empty-description {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-divider {
  border-color: rgba(255, 255, 255, 0.1) !important;
}

[data-theme="dark"] .ant-space {
  color: #e2e8f0 !important;
}

/* 优化按钮在深色模式下的显示 */
[data-theme="dark"] .ant-btn {
  border-radius: 8px !important;
  font-weight: 500 !important;
  transition: all 0.3s ease !important;
}

[data-theme="dark"] .ant-btn:not(.ant-btn-primary) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  color: #e2e8f0 !important;
}

[data-theme="dark"] .ant-btn:not(.ant-btn-primary):hover {
  background: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(255, 255, 255, 0.25) !important;
  color: #fff !important;
  transform: translateY(-1px) !important;
}

/* 优化卡片间距和布局 */
[data-theme="dark"] .ant-card {
  margin-bottom: 16px !important;
}

[data-theme="dark"] .ant-card:last-child {
  margin-bottom: 0 !important;
}
</style>


