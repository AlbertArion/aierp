<template>
  <div>
    <!-- 数据同步卡片 -->
    <a-card title="数据同步" style="margin-bottom: 16px;">
      <a-form layout="inline" @submit.prevent>
        <a-form-item label="数据源">
          <a-select v-model:value="syncForm.source" style="width: 160px">
            <a-select-option value="SAP">SAP</a-select-option>
            <a-select-option value="UFIDA">用友</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="同步表">
          <a-select 
            v-model:value="syncForm.tables" 
            mode="multiple" 
            style="width: 200px"
            placeholder="选择要同步的表"
          >
            <a-select-option value="sales">销售数据</a-select-option>
            <a-select-option value="finance">财务数据</a-select-option>
            <a-select-option value="inventory">库存数据</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-checkbox v-model:checked="syncForm.useDatax">使用DataX</a-checkbox>
        </a-form-item>
        <a-form-item>
          <a-checkbox v-model:checked="syncForm.realTime">实时同步</a-checkbox>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="syncing" @click="startSync">开始同步</a-button>
        </a-form-item>
      </a-form>
      
      <!-- 同步结果 -->
      <div v-if="syncResult" style="margin-top: 16px;">
        <a-alert 
          :type="syncResult.status === 'success' ? 'success' : 'error'"
          :message="`同步${syncResult.status === 'success' ? '成功' : '失败'}`"
          :description="syncResult.error_message || `同步了 ${syncResult.synced || syncResult.tables?.length || 0} 个表`"
          show-icon
        />
        <div style="margin-top: 12px;">
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; max-height: 300px; overflow: auto;">{{ JSON.stringify(syncResult, null, 2) }}</pre>
        </div>
      </div>
    </a-card>

    <!-- 字段映射卡片 -->
    <a-card title="字段映射生成" style="margin-bottom: 16px;">
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="源字段">
            <a-textarea 
              v-model:value="mappingForm.sourceFields" 
              placeholder="每行一个字段名，如：&#10;vbeln&#10;kunnr&#10;netwr"
              :rows="6"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="目标字段">
            <a-textarea 
              v-model:value="mappingForm.targetFields" 
              placeholder="每行一个字段名，如：&#10;order_no&#10;customer_code&#10;amount"
              :rows="6"
            />
          </a-form-item>
        </a-col>
      </a-row>
      
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="源系统">
            <a-input v-model:value="mappingForm.sourceSystem" placeholder="如：SAP" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="目标系统">
            <a-input v-model:value="mappingForm.targetSystem" placeholder="如：Snowflake" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item>
            <a-button type="primary" :loading="mappingLoading" @click="generateMapping">生成映射</a-button>
          </a-form-item>
        </a-col>
      </a-row>
      
      <!-- 映射结果 -->
      <div v-if="mappingResult" style="margin-top: 16px;">
        <a-tabs>
          <a-tab-pane key="mappings" tab="字段映射">
            <div v-for="(mapping, sourceField) in mappingResult.mappings" :key="sourceField" style="margin-bottom: 12px;">
              <a-card size="small">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <strong>{{ sourceField }}</strong> → <strong>{{ mapping.target_field }}</strong>
                    <a-tag :color="mapping.confidence > 0.8 ? 'green' : mapping.confidence > 0.6 ? 'orange' : 'red'">
                      置信度: {{ (mapping.confidence * 100).toFixed(1) }}%
                    </a-tag>
                  </div>
                  <div>
                    <a-tooltip :title="mapping.reason">
                      <a-button type="text" size="small">详情</a-button>
                    </a-tooltip>
                  </div>
                </div>
                <div v-if="mapping.transformation" style="margin-top: 8px; color: #666;">
                  转换规则: {{ mapping.transformation }}
                </div>
              </a-card>
            </div>
          </a-tab-pane>
          
          <a-tab-pane key="analysis" tab="字段分析">
            <div v-if="mappingResult.field_analysis">
              <h4>源字段分析</h4>
              <p>{{ mappingResult.field_analysis.source_analysis }}</p>
              <h4>目标字段分析</h4>
              <p>{{ mappingResult.field_analysis.target_analysis }}</p>
              <h4>映射策略建议</h4>
              <p>{{ mappingResult.field_analysis.mapping_strategy }}</p>
            </div>
          </a-tab-pane>
          
          <a-tab-pane key="validation" tab="验证结果">
            <div v-if="mappingResult.validation">
              <a-alert 
                :type="mappingResult.validation.valid ? 'success' : 'error'"
                :message="mappingResult.validation.valid ? '映射验证通过' : '映射验证失败'"
                show-icon
              />
              <div v-if="mappingResult.validation.errors?.length" style="margin-top: 12px;">
                <h4>错误:</h4>
                <ul>
                  <li v-for="error in mappingResult.validation.errors" :key="error">{{ error }}</li>
                </ul>
              </div>
              <div v-if="mappingResult.validation.warnings?.length" style="margin-top: 12px;">
                <h4>警告:</h4>
                <ul>
                  <li v-for="warning in mappingResult.validation.warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-card>

    <!-- 流处理监控卡片 -->
    <a-card title="流处理监控" style="margin-bottom: 16px;">
      <a-row :gutter="16">
        <a-col :span="12">
          <a-button type="primary" @click="loadStreamMetrics" :loading="metricsLoading">刷新指标</a-button>
        </a-col>
        <a-col :span="12">
          <a-tag :color="streamMetrics.stream_running ? 'green' : 'red'">
            {{ streamMetrics.stream_running ? '流处理运行中' : '流处理已停止' }}
          </a-tag>
        </a-col>
      </a-row>
      
      <div v-if="streamMetrics.performance_metrics" style="margin-top: 16px;">
        <h4>性能指标</h4>
        <div v-for="(metrics, processType) in streamMetrics.performance_metrics" :key="processType" style="margin-bottom: 12px;">
          <a-card size="small">
            <div style="display: flex; justify-content: space-between;">
              <span><strong>{{ processType }}</strong></span>
              <span>平均吞吐量: {{ (metrics.reduce((a, b) => a + b, 0) / metrics.length).toFixed(2) }} records/s</span>
            </div>
          </a-card>
        </div>
      </div>
      
      <div v-if="streamMetrics.recent_alerts?.length" style="margin-top: 16px;">
        <h4>最近告警</h4>
        <a-timeline>
          <a-timeline-item 
            v-for="alert in streamMetrics.recent_alerts" 
            :key="alert.alert_id"
            :color="alert.level === 'error' ? 'red' : alert.level === 'warning' ? 'orange' : 'blue'"
          >
            <div>
              <strong>{{ alert.message }}</strong>
              <div style="color: #666; font-size: 12px;">
                {{ new Date(alert.timestamp * 1000).toLocaleString() }} - {{ alert.process_type }}
              </div>
              <div v-if="alert.resolution" style="margin-top: 4px; color: #1890ff;">
                解决方案: {{ alert.resolution }}
              </div>
            </div>
          </a-timeline-item>
        </a-timeline>
      </div>
    </a-card>

    <!-- 非结构化数据解析卡片 -->
    <a-card title="非结构化数据解析">
      <a-upload-dragger
        :file-list="fileList"
        :before-upload="beforeUpload"
        :remove="removeFile"
        accept=".pdf,.xlsx,.xls"
      >
        <p class="ant-upload-drag-icon">
          <inbox-outlined></inbox-outlined>
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p class="ant-upload-hint">支持 PDF、Excel 文件</p>
      </a-upload-dragger>
      
      <div style="margin-top: 16px;">
        <a-button type="primary" :loading="parsing" @click="parse" :disabled="!fileList.length">解析文件</a-button>
      </div>
      
      <a-divider />
      <div v-if="result" style="max-height:300px;overflow:auto; background: #f5f5f5; padding: 12px; border-radius: 4px;">
        <pre>{{ result }}</pre>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { InboxOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

// 数据同步相关
const syncForm = ref({
  source: 'SAP',
  tables: ['sales', 'finance'],
  useDatax: true,
  realTime: false
})
const syncing = ref(false)
const syncResult = ref<any>(null)

// 字段映射相关
const mappingForm = ref({
  sourceFields: 'vbeln\nkunnr\nnetwr\nwaerk\nerdat',
  targetFields: 'order_no\ncustomer_code\namount\ncurrency\norder_date',
  sourceSystem: 'SAP',
  targetSystem: 'Snowflake'
})
const mappingLoading = ref(false)
const mappingResult = ref<any>(null)

// 流处理监控相关
const metricsLoading = ref(false)
const streamMetrics = ref<any>({})

// 文件解析相关
const fileList = ref<any[]>([])
const result = ref('')
const parsing = ref(false)

// 数据同步
const startSync = async () => {
  try {
    syncing.value = true
    const { data } = await axios.post('/api/data/sync', syncForm.value)
    syncResult.value = data
    message.success('同步任务已启动')
  } catch (error: any) {
    console.error('Sync failed:', error)
    syncResult.value = { error: error.response?.data?.detail || 'Sync failed' }
    message.error('同步失败')
  } finally {
    syncing.value = false
  }
}

// 字段映射生成
const generateMapping = async () => {
  try {
    mappingLoading.value = true
    const sourceFields = mappingForm.value.sourceFields.split('\n').filter(f => f.trim())
    const targetFields = mappingForm.value.targetFields.split('\n').filter(f => f.trim())
    
    const { data } = await axios.post('/api/data/field-mapping', {
      source_fields: sourceFields,
      target_fields: targetFields,
      source_system: mappingForm.value.sourceSystem,
      target_system: mappingForm.value.targetSystem
    })
    
    mappingResult.value = data
    message.success('字段映射生成成功')
  } catch (error: any) {
    console.error('Mapping failed:', error)
    message.error('字段映射生成失败')
  } finally {
    mappingLoading.value = false
  }
}

// 加载流处理指标
const loadStreamMetrics = async () => {
  try {
    metricsLoading.value = true
    const { data } = await axios.get('/api/data/stream-metrics')
    streamMetrics.value = data
  } catch (error: any) {
    console.error('Load metrics failed:', error)
    message.error('加载流处理指标失败')
  } finally {
    metricsLoading.value = false
  }
}

// 文件上传处理
const beforeUpload = (file: any) => {
  fileList.value = [file]
  return false // 阻止自动上传
}

const removeFile = () => {
  fileList.value = []
}

const parse = async () => {
  if (!fileList.value.length) return
  parsing.value = true
  try {
    const form = new FormData()
    form.append('file', fileList.value[0])
    const { data } = await axios.post('/api/data/parse-unstructured', form)
    result.value = JSON.stringify(data, null, 2)
    message.success('文件解析成功')
  } catch (error: any) {
    console.error('Parse failed:', error)
    message.error('文件解析失败')
  } finally {
    parsing.value = false
  }
}

// 组件挂载时加载流处理指标
onMounted(() => {
  loadStreamMetrics()
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
</style>


