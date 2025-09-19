<template>
  <div>
    <!-- 模型状态卡片 -->
    <a-card title="模型状态" style="margin-bottom: 16px;">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-statistic title="模型类型" :value="modelStatus.model_type || '未训练'" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="训练状态" :value="modelStatus.predictor_ready ? '已训练' : '未训练'" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="序列长度" :value="modelStatus.sequence_length || 0" />
        </a-col>
        <a-col :span="6">
          <a-tag :color="modelStatus.predictor_ready ? 'green' : 'red'">
            {{ modelStatus.predictor_ready ? '就绪' : '未就绪' }}
          </a-tag>
        </a-col>
      </a-row>
      <div style="margin-top: 16px;">
        <a-button type="primary" @click="loadModelStatus" :loading="statusLoading">刷新状态</a-button>
      </div>
    </a-card>

    <!-- 模型训练卡片 -->
    <a-card title="模型训练" style="margin-bottom: 16px;">
      <a-form layout="vertical">
        <a-form-item label="训练数据">
          <a-textarea 
            v-model:value="trainForm.seriesInput" 
            placeholder="每行一个数值，如：&#10;100&#10;120&#10;130&#10;140&#10;150"
            :rows="6"
          />
        </a-form-item>
        
        <a-row :gutter="16">
          <a-col :span="6">
            <a-form-item label="测试集比例">
              <a-slider v-model:value="trainForm.testSize" :min="0.1" :max="0.5" :step="0.05" />
              <span>{{ (trainForm.testSize * 100).toFixed(0) }}%</span>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="训练轮数">
              <a-input-number v-model:value="trainForm.epochs" :min="10" :max="500" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="批次大小">
              <a-input-number v-model:value="trainForm.batchSize" :min="8" :max="128" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="序列长度">
              <a-input-number v-model:value="trainForm.sequenceLength" :min="6" :max="24" />
            </a-form-item>
          </a-col>
        </a-row>
        
        <a-form-item>
          <a-button type="primary" @click="trainModel" :loading="training">开始训练</a-button>
          <a-button style="margin-left: 8px;" @click="evaluateModel" :loading="evaluating">评估模型</a-button>
        </a-form-item>
      </a-form>
      
      <!-- 训练结果 -->
      <div v-if="trainingResult" style="margin-top: 16px;">
        <a-alert 
          :type="trainingResult.metrics?.is_accurate ? 'success' : 'warning'"
          :message="`训练${trainingResult.metrics?.is_accurate ? '成功' : '完成'} - 误差率: ${trainingResult.metrics?.mape?.toFixed(2) || 'N/A'}%`"
          show-icon
        />
        <div style="margin-top: 12px;">
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; max-height: 300px; overflow: auto;">{{ JSON.stringify(trainingResult, null, 2) }}</pre>
        </div>
      </div>
    </a-card>

    <!-- 指标预测卡片 -->
    <a-card title="指标预测 (LSTM)" style="margin-bottom: 16px;">
      <a-form layout="vertical">
        <a-form-item label="历史序列">
          <a-textarea 
            v-model:value="predictForm.seriesInput" 
            placeholder="每行一个数值，如：&#10;100&#10;120&#10;130&#10;140&#10;150"
            :rows="4"
          />
        </a-form-item>
        
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="预测月数">
              <a-input-number v-model:value="predictForm.horizonMonths" :min="1" :max="6" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="使用LSTM">
              <a-switch v-model:checked="predictForm.useLstm" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item>
              <a-button type="primary" @click="predict" :loading="predicting">预测</a-button>
              <a-button style="margin-left: 8px;" @click="batchPredict" :loading="batchPredicting">批量预测</a-button>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
      
      <!-- 预测结果 -->
      <div v-if="forecastResult" style="margin-top: 16px;">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic title="预测值" :value="forecastResult.forecast?.[0] || 0" :precision="2" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="置信度" :value="(forecastResult.confidence * 100).toFixed(1)" suffix="%" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="预测时间" :value="forecastResult.prediction_time_ms" suffix="ms" />
          </a-col>
          <a-col :span="6">
            <a-tag :color="forecastResult.is_accurate ? 'green' : 'orange'">
              {{ forecastResult.is_accurate ? '高精度' : '中等精度' }}
            </a-tag>
          </a-col>
        </a-row>
        <div style="margin-top: 12px;">
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; max-height: 300px; overflow: auto;">{{ JSON.stringify(forecastResult, null, 2) }}</pre>
        </div>
      </div>
    </a-card>

    <!-- 外部因素修正卡片 -->
    <a-card title="外部因素修正 (LLM)" style="margin-bottom: 16px;">
      <a-form layout="vertical">
        <a-form-item label="基础预测">
          <a-textarea 
            v-model:value="correctionForm.baseForecastInput" 
            placeholder="每行一个数值，如：&#10;100&#10;120&#10;130"
            :rows="3"
          />
        </a-form-item>
        
        <a-form-item label="外部因素">
          <a-textarea 
            v-model:value="correctionForm.textFactors" 
            placeholder="描述外部因素，如：9月有促销活动，预计销量增长20%"
            :rows="3"
          />
        </a-form-item>
        
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="置信度阈值">
              <a-slider v-model:value="correctionForm.confidenceThreshold" :min="0" :max="1" :step="0.1" />
              <span>{{ (correctionForm.confidenceThreshold * 100).toFixed(0) }}%</span>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item>
              <a-button type="primary" @click="correctPrediction" :loading="correcting">修正预测</a-button>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
      
      <!-- 修正结果 -->
      <div v-if="correctionResult" style="margin-top: 16px;">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic title="修正幅度" :value="correctionResult.change_percentage?.toFixed(2) || 0" suffix="%" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="修正后置信度" :value="(correctionResult.confidence * 100).toFixed(1)" suffix="%" />
          </a-col>
          <a-col :span="6">
            <a-tag :color="correctionResult.confidence > 0.8 ? 'green' : 'orange'">
              {{ correctionResult.confidence > 0.8 ? '高置信度' : '中等置信度' }}
            </a-tag>
          </a-col>
          <a-col :span="6">
            <a-button type="link" @click="showExplanation = !showExplanation">
              {{ showExplanation ? '隐藏' : '显示' }}解释
            </a-button>
          </a-col>
        </a-row>
        
        <div v-if="showExplanation && correctionResult.explanation" style="margin-top: 12px;">
          <a-alert :message="correctionResult.explanation" type="info" show-icon />
        </div>
        
        <div style="margin-top: 12px;">
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; max-height: 300px; overflow: auto;">{{ JSON.stringify(correctionResult, null, 2) }}</pre>
        </div>
      </div>
    </a-card>

    <!-- 预测对比图表 -->
    <a-card title="预测对比图表" style="margin-bottom: 16px;">
      <div ref="chartRef" style="height: 400px;"></div>
      <div style="margin-top: 16px;">
        <a-button @click="exportChart" :loading="exporting">导出图表</a-button>
        <a-button style="margin-left: 8px;" @click="refreshChart">刷新图表</a-button>
      </div>
    </a-card>

    <!-- 批量预测结果 -->
    <a-card title="批量预测结果" v-if="batchResults.length > 0">
      <a-table 
        :columns="batchColumns" 
        :data-source="batchResults" 
        :pagination="{ pageSize: 5 }"
        size="small"
      />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { message } from 'ant-design-vue'

// 模型状态
const modelStatus = ref<any>({})
const statusLoading = ref(false)

// 训练表单
const trainForm = ref({
  seriesInput: '100\n120\n130\n140\n150\n160\n170\n180\n190\n200\n210\n220',
  testSize: 0.2,
  epochs: 100,
  batchSize: 32,
  sequenceLength: 12
})
const training = ref(false)
const evaluating = ref(false)
const trainingResult = ref<any>(null)

// 预测表单
const predictForm = ref({
  seriesInput: '100\n120\n130\n140\n150\n160\n170\n180\n190\n200\n210\n220',
  horizonMonths: 3,
  useLstm: true
})
const predicting = ref(false)
const batchPredicting = ref(false)
const forecastResult = ref<any>(null)

// 修正表单
const correctionForm = ref({
  baseForecastInput: '100\n120\n130',
  textFactors: '9月有促销活动，预计销量增长20%',
  confidenceThreshold: 0.8
})
const correcting = ref(false)
const correctionResult = ref<any>(null)
const showExplanation = ref(false)

// 批量预测
const batchResults = ref<any[]>([])
const batchColumns = [
  { title: '序号', dataIndex: 'index', key: 'index' },
  { title: '预测值', dataIndex: 'forecast', key: 'forecast', render: (text: any) => text?.[0]?.toFixed(2) || 'N/A' },
  { title: '预测月数', dataIndex: 'horizon_months', key: 'horizon_months' },
  { title: '数据点数', dataIndex: 'data_points', key: 'data_points' },
  { title: '状态', dataIndex: 'error', key: 'status', render: (text: any) => text ? '失败' : '成功' }
]

// 图表
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const exporting = ref(false)

// 加载模型状态
const loadModelStatus = async () => {
  try {
    statusLoading.value = true
    const { data } = await axios.get('/api/predict/model-status')
    modelStatus.value = data
  } catch (error: any) {
    message.error('加载模型状态失败')
    console.error('Load model status failed:', error)
  } finally {
    statusLoading.value = false
  }
}

// 训练模型
const trainModel = async () => {
  try {
    const series = trainForm.value.seriesInput.split('\n')
      .map(v => parseFloat(v.trim()))
      .filter(v => !isNaN(v))
    
    if (series.length < 12) {
      message.error('训练数据不足，至少需要12个数据点')
      return
    }
    
    training.value = true
    const { data } = await axios.post('/api/predict/train', {
      series,
      test_size: trainForm.value.testSize,
      epochs: trainForm.value.epochs,
      batch_size: trainForm.value.batchSize,
      sequence_length: trainForm.value.sequenceLength
    })
    
    trainingResult.value = data
    message.success('模型训练完成')
    
    // 刷新模型状态
    await loadModelStatus()
    
  } catch (error: any) {
    message.error('模型训练失败')
    console.error('Train model failed:', error)
  } finally {
    training.value = false
  }
}

// 评估模型
const evaluateModel = async () => {
  try {
    const series = trainForm.value.seriesInput.split('\n')
      .map(v => parseFloat(v.trim()))
      .filter(v => !isNaN(v))
    
    if (series.length < 12) {
      message.error('评估数据不足，至少需要12个数据点')
      return
    }
    
    evaluating.value = true
    const { data } = await axios.post('/api/predict/evaluate', {
      series,
      test_size: trainForm.value.testSize
    })
    
    trainingResult.value = data
    message.success('模型评估完成')
    
  } catch (error: any) {
    message.error('模型评估失败')
    console.error('Evaluate model failed:', error)
  } finally {
    evaluating.value = false
  }
}

// 预测
const predict = async () => {
  try {
    const series = predictForm.value.seriesInput.split('\n')
      .map(v => parseFloat(v.trim()))
      .filter(v => !isNaN(v))
    
    if (series.length < 12) {
      message.error('历史数据不足，至少需要12个数据点')
      return
    }
    
    predicting.value = true
    const { data } = await axios.post('/api/predict/indicators', {
      series,
      horizon_months: predictForm.value.horizonMonths,
      use_lstm: predictForm.value.useLstm
    })
    
    forecastResult.value = data
    message.success('预测完成')
    
    // 更新修正表单的基础预测
    correctionForm.value.baseForecastInput = data.forecast?.join('\n') || ''
    
  } catch (error: any) {
    message.error('预测失败')
    console.error('Predict failed:', error)
  } finally {
    predicting.value = false
  }
}

// 批量预测
const batchPredict = async () => {
  try {
    const series = predictForm.value.seriesInput.split('\n')
      .map(v => parseFloat(v.trim()))
      .filter(v => !isNaN(v))
    
    if (series.length < 12) {
      message.error('历史数据不足，至少需要12个数据点')
      return
    }
    
    // 创建多个预测请求
    const requests = []
    for (let i = 1; i <= 3; i++) {
      requests.push({
        series: series.slice(0, -i * 2), // 使用不同的历史数据长度
        horizon_months: predictForm.value.horizonMonths,
        use_lstm: predictForm.value.useLstm
      })
    }
    
    batchPredicting.value = true
    const { data } = await axios.post('/api/predict/batch-predict', requests)
    
    batchResults.value = data.batch_results
    message.success(`批量预测完成，成功 ${data.successful}/${data.total_processed} 个`)
    
  } catch (error: any) {
    message.error('批量预测失败')
    console.error('Batch predict failed:', error)
  } finally {
    batchPredicting.value = false
  }
}

// 修正预测
const correctPrediction = async () => {
  try {
    const baseForecast = correctionForm.value.baseForecastInput.split('\n')
      .map(v => parseFloat(v.trim()))
      .filter(v => !isNaN(v))
    
    if (baseForecast.length === 0) {
      message.error('基础预测数据不能为空')
      return
    }
    
    correcting.value = true
    const { data } = await axios.post('/api/predict/with-factors', {
      base_forecast: baseForecast,
      text_factors: correctionForm.value.textFactors,
      confidence_threshold: correctionForm.value.confidenceThreshold
    })
    
    correctionResult.value = data
    message.success('预测修正完成')
    
  } catch (error: any) {
    message.error('预测修正失败')
    console.error('Correct prediction failed:', error)
  } finally {
    correcting.value = false
  }
}

// 渲染图表
const renderChart = () => {
  if (!chartRef.value) return
  
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  
  const baseForecast = forecastResult.value?.forecast || []
  const correctedForecast = correctionResult.value?.corrected_forecast || []
  const actuals = trainingResult.value?.actuals || []
  
  const months = Math.max(baseForecast.length, correctedForecast.length, actuals.length)
  const xAxisData = Array.from({ length: months }, (_, i) => `M${i + 1}`)
  
  const series = []
  
  if (actuals.length > 0) {
    series.push({
      name: '实际值',
      type: 'line',
      data: actuals,
      itemStyle: { color: '#ff4d4f' }
    })
  }
  
  if (baseForecast.length > 0) {
    series.push({
      name: 'LSTM预测',
      type: 'line',
      data: baseForecast,
      itemStyle: { color: '#1890ff' }
    })
  }
  
  if (correctedForecast.length > 0) {
    series.push({
      name: 'LLM修正',
      type: 'line',
      data: correctedForecast,
      itemStyle: { color: '#52c41a' }
    })
  }
  
  chart.setOption({
    title: {
      text: '预测对比图表',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let result = `月份: ${params[0].axisValue}<br/>`
        params.forEach((param: any) => {
          result += `${param.seriesName}: ${param.value.toFixed(2)}<br/>`
        })
        return result
      }
    },
    legend: {
      data: series.map(s => s.name),
      top: 30
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData
    },
    yAxis: {
      type: 'value'
    },
    series
  })
}

// 导出图表
const exportChart = async () => {
  if (!chart) return
  
  try {
    exporting.value = true
    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff'
    })
    
    const a = document.createElement('a')
    a.href = url
    a.download = `forecast_${new Date().toISOString().slice(0, 10)}.png`
    a.click()
    
    message.success('图表导出成功')
  } catch (error) {
    message.error('图表导出失败')
  } finally {
    exporting.value = false
  }
}

// 刷新图表
const refreshChart = () => {
  renderChart()
}

// 监听数据变化，自动更新图表
watch([forecastResult, correctionResult, trainingResult], () => {
  nextTick(() => {
    renderChart()
  })
})

// 组件挂载时加载模型状态
onMounted(() => {
  loadModelStatus()
  nextTick(() => {
    renderChart()
  })
  window.addEventListener('resize', () => chart?.resize())
})

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
  window.removeEventListener('resize', () => chart?.resize())
})
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

[data-theme="dark"] .ant-card {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

[data-theme="dark"] .ant-statistic-title {
  color: #e2e8f0 !important;
}

[data-theme="dark"] .ant-statistic-content {
  color: #fff !important;
}
</style>