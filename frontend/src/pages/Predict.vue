<template>
  <div>
    <a-card title="指标预测(LSTM)">
      <a-space>
        <a-input v-model:value="seriesInput" placeholder="逗号分隔的历史序列，如 100,120,130" style="width:360px" />
        <a-input-number v-model:value="horizon" :min="1" :max="6" />
        <a-button type="primary" @click="runPredict">预测</a-button>
      </a-space>
      <a-divider />
      <pre>{{ forecast }}</pre>
    </a-card>

    <a-card title="外部因素修正(LLM)" style="margin-top:16px">
      <a-space direction="vertical" style="width:100%">
        <a-textarea v-model:value="factors" rows="3" placeholder="例如：9月有促销活动" />
        <a-button @click="runWithFactors">修正预测</a-button>
        <pre>{{ corrected }}</pre>
      </a-space>
    </a-card>

    <a-card title="预测对比图" style="margin-top:16px">
      <div ref="chartRef" style="height:360px"></div>
      <a-button style="margin-top:8px" @click="exportPng">导出PNG</a-button>
    </a-card>
    <a-card title="训练与评估" style="margin-top:16px">
      <a-space>
        <a-input-number v-model:value="evalHorizon" :min="1" :max="6" />
        <a-button type="primary" :loading="training" @click="trainEval">训练并评估</a-button>
      </a-space>
      <a-divider />
      <pre>{{ trainResult }}</pre>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const seriesInput = ref('100,120,130,150')
const horizon = ref(3)
const forecast = ref<any>(null)
const factors = ref('9月有促销活动')
const corrected = ref<any>(null)
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const runPredict = async () => {
  const series = seriesInput.value.split(',').map(v => Number(v.trim())).filter(v => !Number.isNaN(v))
  const { data } = await axios.post('/api/predict/indicators', { series, horizon_months: horizon.value })
  forecast.value = data
}

const runWithFactors = async () => {
  const base = (forecast.value?.forecast as number[]) || [0, 0, 0]
  const { data } = await axios.post('/api/predict/with-factors', { base_forecast: base, text_factors: factors.value })
  corrected.value = data
}

const renderChart = () => {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const base = (forecast.value?.forecast as number[]) || []
  const corr = (corrected.value?.corrected as number[]) || []
  const months = Math.max(base.length, corr.length)
  const x = Array.from({ length: months }, (_, i) => `M${i + 1}`)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['LSTM预测', 'LLM修正'] },
    xAxis: { type: 'category', data: x },
    yAxis: { type: 'value' },
    series: [
      { name: 'LSTM预测', type: 'line', data: base },
      { name: 'LLM修正', type: 'line', data: corr }
    ]
  })
}

watch([forecast, corrected], () => renderChart())

onMounted(() => {
  renderChart()
  window.addEventListener('resize', () => chart?.resize())
})

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})

const evalHorizon = ref(1)
const training = ref(false)
const trainResult = ref<any>(null)

const trainEval = async () => {
  training.value = true
  try {
    const series = seriesInput.value.split(',').map(v => Number(v.trim())).filter(v => !Number.isNaN(v))
    const { data } = await axios.post('/api/predict/train', { series, eval_horizon: evalHorizon.value })
    trainResult.value = data
  } finally {
    training.value = false
  }
}

const exportPng = () => {
  if (!chart) return
  const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' })
  const a = document.createElement('a')
  a.href = url
  a.download = 'forecast.png'
  a.click()
}
</script>

<style scoped>
/* 暗色主题支持 */
[data-theme="dark"] pre {
  background: #1e293b !important;
  color: var(--text-color) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  padding: 12px !important;
  border-radius: 4px !important;
}

[data-theme="dark"] .chart-container {
  background: #1e293b !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 4px !important;
}
</style>

