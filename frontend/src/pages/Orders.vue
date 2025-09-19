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
import axios from 'axios'

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
  const { data } = await axios.get('/api/orders/search', { params: { keyword: keyword.value, page: 1, size: 10 } })
  items.value = data.items
}

const update = async () => {
  await axios.put('/api/orders/update', { order_id: orderId.value, field: field.value, value: value.value })
}
</script>


