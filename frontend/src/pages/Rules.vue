<template>
  <div>
    <a-card title="规则管理">
      <a-space>
        <a-button type="primary" @click="load">刷新</a-button>
        <a-button @click="create">新增规则</a-button>
        <a-button @click="createDroolsRule">新增Drools规则</a-button>
        <a-button @click="simulate">模拟事件触发</a-button>
        <a-button @click="showAnalytics">规则分析</a-button>
        <a-button @click="showAlerts">告警管理</a-button>
      </a-space>
      <a-divider />
      
      <!-- 规则列表 -->
      <a-table :dataSource="items" :columns="columns" rowKey="_id" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" @click="edit(record)">编辑</a-button>
              <a-button size="small" @click="analyzePerformance(record)">性能分析</a-button>
              <a-button size="small" @click="autoOptimize(record)" v-if="record.type === 'drools'">AI优化</a-button>
              <a-button size="small" danger @click="remove(record)">删除</a-button>
            </a-space>
          </template>
          <template v-else-if="column.key === 'type'">
            <a-tag :color="record.type === 'drools' ? 'blue' : 'green'">
              {{ record.type === 'drools' ? 'Drools规则' : '简单规则' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.enabled ? 'green' : 'red'">
              {{ record.enabled ? '启用' : '禁用' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 规则分析模态框 -->
    <a-modal v-model:open="analyticsVisible" title="规则分析" width="800px">
      <div v-if="selectedRule">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="规则ID">{{ selectedRule._id }}</a-descriptions-item>
          <a-descriptions-item label="规则名称">{{ selectedRule.name }}</a-descriptions-item>
          <a-descriptions-item label="总执行次数">{{ analyticsData?.total_executions || 0 }}</a-descriptions-item>
          <a-descriptions-item label="成功率">{{ (analyticsData?.success_rate * 100 || 0).toFixed(1) }}%</a-descriptions-item>
          <a-descriptions-item label="平均执行时间">{{ analyticsData?.avg_time || 0 }}ms</a-descriptions-item>
          <a-descriptions-item label="误报率">{{ (analyticsData?.false_positive_rate * 100 || 0).toFixed(1) }}%</a-descriptions-item>
        </a-descriptions>
        
        <a-divider />
        <h4>性能趋势</h4>
        <div class="performance-chart" style="height: 300px;"></div>
        
        <a-divider />
        <h4>优化建议</h4>
        <a-list :dataSource="analyticsData?.recommendations || []">
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta>
                <template #title>
                  <a-tag :color="item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'orange' : 'green'">
                    {{ item.priority }}
                  </a-tag>
                  {{ item.description }}
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </div>
    </a-modal>

    <!-- 告警管理模态框 -->
    <a-modal v-model:open="alertsVisible" title="分级告警管理" width="1000px">
      <a-tabs v-model:activeKey="activeAlertTab">
        <a-tab-pane key="statistics" tab="告警统计">
          <a-row :gutter="16">
            <a-col :span="6" v-for="(count, level) in alertStats.by_level" :key="level">
              <a-statistic :title="level" :value="count" :valueStyle="{ color: getAlertColor(level) }" />
            </a-col>
          </a-row>
          <a-divider />
          <div class="alert-trend-chart" style="height: 300px;"></div>
        </a-tab-pane>
        
        <a-tab-pane key="levels" tab="告警级别">
          <a-table :dataSource="alertLevels" :columns="alertLevelColumns" :pagination="false" />
        </a-tab-pane>
        
        <a-tab-pane key="policies" tab="升级策略">
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="默认策略">
              <pre>{{ JSON.stringify(escalationPolicies.default, null, 2) }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="业务关键策略">
              <pre>{{ JSON.stringify(escalationPolicies.business_critical, null, 2) }}</pre>
            </a-descriptions-item>
          </a-descriptions>
        </a-tab-pane>
      </a-tabs>
    </a-modal>

    <!-- Drools规则创建模态框 -->
    <a-modal v-model:open="droolsRuleVisible" title="创建Drools规则" width="800px">
      <a-form :model="droolsRuleForm" layout="vertical">
        <a-form-item label="规则ID">
          <a-input v-model:value="droolsRuleForm.id" placeholder="例如: inventory_low_stock" />
        </a-form-item>
        <a-form-item label="规则名称">
          <a-input v-model:value="droolsRuleForm.name" placeholder="例如: 库存不足告警规则" />
        </a-form-item>
        <a-form-item label="规则内容 (DRL格式)">
          <a-textarea 
            v-model:value="droolsRuleForm.content" 
            :rows="12" 
            placeholder="package com.aierp.rules;

import java.util.Map;

rule &quot;inventory_low_stock&quot;
    when
        $fact: Map() from entry-point &quot;events&quot;
        eval($fact.get(&quot;stock_quantity&quot;) != null && $fact.get(&quot;stock_quantity&quot;) < 10)
    then
        System.out.println(&quot;库存不足告警: &quot; + $fact.get(&quot;source&quot;));
        // 发送告警
end"
          />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="droolsRuleVisible = false">取消</a-button>
          <a-button type="primary" @click="createDroolsRuleConfirm">创建</a-button>
        </a-space>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, nextTick } from 'vue'
import apiClient from '../utils/axios'
import * as echarts from 'echarts'

const items = ref<any[]>([])
const analyticsVisible = ref(false)
const alertsVisible = ref(false)
const droolsRuleVisible = ref(false)
const selectedRule = ref<any>(null)
const analyticsData = ref<any>(null)
const alertStats = ref<any>({})
const alertLevels = ref<any[]>([])
const escalationPolicies = ref<any>({})
const activeAlertTab = ref('statistics')

const columns = [
  { title: '名称', dataIndex: 'name' },
  { title: '类型', key: 'type' },
  { title: '状态', key: 'status' },
  { title: '条件', dataIndex: ['condition', 'field'] },
  { 
    title: '操作', 
    key: 'actions'
  }
]

const alertLevelColumns = [
  { title: '级别', dataIndex: 'name' },
  { title: '值', dataIndex: 'value' },
  { title: '描述', dataIndex: 'description' }
]

const droolsRuleForm = ref({
  id: '',
  name: '',
  content: ''
})

const load = async () => {
  const { data } = await apiClient.get('/api/process/rules')
  items.value = data.items
}

const create = async () => {
  const rule = {
    name: '库存延迟告警',
    enabled: true,
    description: '当对账延迟分钟数>30触发',
    condition: { field: 'delay_minutes', op: 'gt', value: 30, level: 'warning', solution: '自动重试同步' }
  }
  await apiClient.post('/api/process/rules', rule)
  await load()
}

const createDroolsRule = () => {
  droolsRuleVisible.value = true
}

const createDroolsRuleConfirm = async () => {
  try {
    await apiClient.post('/api/process/drools/rules', {
      id: droolsRuleForm.value.id,
      content: droolsRuleForm.value.content,
      type: 'drl'
    })
    
    // 创建对应的规则记录
    const rule = {
      name: droolsRuleForm.value.name,
      enabled: true,
      type: 'drools',
      description: 'Drools规则引擎规则',
      condition: { field: 'drools', op: 'eq', value: droolsRuleForm.value.id }
    }
    await apiClient.post('/api/process/rules', rule)
    
    droolsRuleVisible.value = false
    droolsRuleForm.value = { id: '', name: '', content: '' }
    await load()
  } catch (error) {
    console.error('创建Drools规则失败:', error)
  }
}

const edit = async (rec: any) => {
  const patch = { ...rec, enabled: !rec.enabled }
  await apiClient.put(`/api/process/rules/${rec._id}`, patch)
  await load()
}

const remove = async (rec: any) => {
  await apiClient.delete(`/api/process/rules/${rec._id}`)
  await load()
}

const simulate = async () => {
  await apiClient.post('/api/process/events', { source: 'orders-sync', delay_minutes: 45 })
}

const analyzePerformance = async (record: any) => {
  selectedRule.value = record
  try {
    const { data } = await apiClient.get(`/api/process/ai/rules/${record._id}/performance`)
    analyticsData.value = data.analysis
    analyticsVisible.value = true
    
    await nextTick()
    renderPerformanceChart()
  } catch (error) {
    console.error('获取性能分析失败:', error)
  }
}

const autoOptimize = async (record: any) => {
  try {
    const { data } = await apiClient.post(`/api/process/ai/rules/${record._id}/auto-optimize`)
    if (data.success) {
      console.log('规则优化完成:', data.optimization)
      await load()
    }
  } catch (error) {
    console.error('自动优化失败:', error)
  }
}

const showAnalytics = () => {
  analyticsVisible.value = true
}

const showAlerts = async () => {
  try {
    // 获取告警统计
    const { data: statsData } = await apiClient.get('/api/process/alerts/statistics')
    alertStats.value = statsData.statistics
    
    // 获取告警级别
    const { data: levelsData } = await apiClient.get('/api/process/alerts/levels')
    alertLevels.value = levelsData.levels.map((level: any) => ({
      name: level.name,
      value: level.value,
      description: `告警级别: ${level.name}`
    }))
    
    // 获取升级策略
    const { data: policiesData } = await apiClient.get('/api/process/alerts/escalation-policies')
    escalationPolicies.value = policiesData.policies
    
    alertsVisible.value = true
    
    await nextTick()
    renderAlertTrendChart()
  } catch (error) {
    console.error('获取告警数据失败:', error)
  }
}

const getAlertColor = (level: string) => {
  const colors: any = {
    info: '#1890ff',
    warning: '#faad14',
    error: '#f5222d',
    critical: '#722ed1',
    emergency: '#eb2f96'
  }
  return colors[level] || '#d9d9d9'
}

const renderPerformanceChart = () => {
  const chartDom = document.querySelector('.performance-chart')
  if (!chartDom || !analyticsData.value) return
  
  const chart = echarts.init(chartDom as HTMLElement)
  const option = {
    title: { text: '规则执行趋势' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['执行次数', '成功率'] },
    xAxis: { 
      type: 'category',
      data: ['1天前', '2天前', '3天前', '4天前', '5天前']
    },
    yAxis: [
      { type: 'value', name: '执行次数' },
      { type: 'value', name: '成功率(%)', max: 100 }
    ],
    series: [
      {
        name: '执行次数',
        type: 'line',
        data: analyticsData.value.execution_times || [10, 15, 8, 12, 18]
      },
      {
        name: '成功率',
        type: 'line',
        yAxisIndex: 1,
        data: (analyticsData.value.success_rates || [0.9, 0.85, 0.92, 0.88, 0.86]).map((r: number) => r * 100)
      }
    ]
  }
  chart.setOption(option)
}

const renderAlertTrendChart = () => {
  const chartDom = document.querySelector('.alert-trend-chart')
  if (!chartDom || !alertStats.value) return
  
  const chart = echarts.init(chartDom as HTMLElement)
  const option = {
    title: { text: '告警趋势分析' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['告警数量', '解决数量'] },
    xAxis: { 
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '告警数量',
        type: 'bar',
        data: [23, 18, 25, 21, 19, 15, 12]
      },
      {
        name: '解决数量',
        type: 'bar',
        data: [20, 16, 22, 19, 17, 14, 11]
      }
    ]
  }
  chart.setOption(option)
}

onMounted(load)
</script>


