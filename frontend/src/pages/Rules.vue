<template>
  <div>
    <a-card title="规则管理">
      <a-space>
        <a-button type="primary" @click="load">刷新</a-button>
        <a-button @click="create">新增规则</a-button>
        <a-button @click="simulate">模拟事件触发</a-button>
      </a-space>
      <a-divider />
      <a-table :dataSource="items" :columns="columns" rowKey="_id" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import axios from 'axios'

const items = ref<any[]>([])
const columns = [
  { title: '名称', dataIndex: 'name' },
  { title: '启用', dataIndex: 'enabled' },
  { title: '条件', dataIndex: ['condition', 'field'] },
  { 
    title: '操作', 
    key: 'action',
    customRender: ({ record }: any) => {
      return [
        h('a-button', { size: 'small', onClick: () => edit(record) }, '编辑'),
        h('a-button', { size: 'small', danger: true, onClick: () => remove(record) }, '删除')
      ]
    }
  }
]

const load = async () => {
  const { data } = await axios.get('/api/process/rules')
  items.value = data.items
}

const create = async () => {
  const rule = {
    name: '库存延迟告警',
    enabled: true,
    description: '当对账延迟分钟数>30触发',
    condition: { field: 'delay_minutes', op: 'gt', value: 30, level: 'warning', solution: '自动重试同步' }
  }
  await axios.post('/api/process/rules', rule)
  await load()
}

const edit = async (rec: any) => {
  const patch = { ...rec, enabled: !rec.enabled }
  await axios.put(`/api/process/rules/${rec._id}`, patch)
  await load()
}

const remove = async (rec: any) => {
  await axios.delete(`/api/process/rules/${rec._id}`)
  await load()
}

const simulate = async () => {
  await axios.post('/api/process/events', { source: 'orders-sync', delay_minutes: 45 })
}

onMounted(load)
</script>


