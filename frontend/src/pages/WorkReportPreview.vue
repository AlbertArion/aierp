<!-- frontend/src/pages/WorkReportAgent.vue -->
<template>
  <div class="work-report-agent">
    <a-card title="报工查询" :bordered="false">
      <!-- 搜索区域 -->
      <div class="search-section">
        <a-row :gutter="16">
          <a-col :span="8">
            <a-input
              v-model:value="searchForm.keyword"
              placeholder="输入关键字搜索（员工姓名、项目名称、工作内容等）"
              @pressEnter="handleSearch"
              allowClear
            >
              <template #prefix>
                <SearchOutlined />
              </template>
            </a-input>
          </a-col>
          <a-col :span="4">
            <a-input
              v-model:value="searchForm.employee_name"
              placeholder="员工姓名"
              allowClear
            />
          </a-col>
          <a-col :span="4">
            <a-input
              v-model:value="searchForm.project_name"
              placeholder="项目名称"
              allowClear
            />
          </a-col>
          <a-col :span="4">
            <a-select
              v-model:value="searchForm.status"
              placeholder="状态"
              allowClear
              style="width: 100%"
            >
              <a-select-option value="pending">待审核</a-select-option>
              <a-select-option value="approved">已通过</a-select-option>
              <a-select-option value="rejected">已拒绝</a-select-option>
            </a-select>
          </a-col>
          <a-col :span="4">
            <a-space>
              <a-button type="primary" @click="handleSearch" :loading="loading">
                <SearchOutlined /> 搜索
              </a-button>
              <a-button @click="handleReset">
                <ReloadOutlined /> 重置
              </a-button>
            </a-space>
          </a-col>
        </a-row>
        
        <!-- 高级搜索 -->
        <a-collapse v-model:activeKey="advancedSearchKey" ghost>
          <a-collapse-panel key="advanced" header="高级搜索">
            <a-row :gutter="16">
              <a-col :span="6">
                <a-range-picker
                  v-model:value="dateRange"
                  :placeholder="['开始日期', '结束日期']"
                />
              </a-col>
              <a-col :span="6">
                <a-input
                  v-model:value="searchForm.department_name"
                  placeholder="部门名称"
                  allowClear
                />
              </a-col>
              <a-col :span="6">
                <a-button type="primary" @click="handleAdvancedSearch">
                  高级搜索
                </a-button>
              </a-col>
            </a-row>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <a-divider />

      <!-- 统计信息 -->
      <div class="statistics-section">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic title="总报工记录" :value="statistics.total_reports" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="总工作时长" :value="statistics.total_hours" suffix="小时" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="平均工作时长" :value="statistics.avg_hours" suffix="小时" :precision="2" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="搜索结果" :value="searchResult.total" />
          </a-col>
        </a-row>
      </div>

      <a-divider />

      <!-- 结果展示 -->
      <div class="results-section">
        <div class="table-header">
          <a-space>
            <a-button @click="handleExport" :loading="exportLoading">
              <DownloadOutlined /> 导出数据
            </a-button>
            <a-button @click="handleImport">
              <UploadOutlined /> 导入数据
            </a-button>
            <a-button type="primary" @click="showCreateModal">
              <PlusOutlined /> 新增报工
            </a-button>
          </a-space>
        </div>

        <a-table
          :dataSource="searchResult.data"
          :columns="columns"
          :loading="loading"
          :pagination="pagination"
          rowKey="id"
          :scroll="{ x: 1200 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'work_hours'">
              {{ record.work_hours }}小时
            </template>
            <template v-else-if="column.key === 'report_date'">
              {{ formatDate(record.report_date) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button size="small" @click="handleView(record)">查看</a-button>
                <a-button size="small" type="primary" @click="handleEdit(record)">编辑</a-button>
                <a-button size="small" danger @click="handleDelete(record)">删除</a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>
    </a-card>

    <!-- 数据导入模态框 -->
    <a-modal
      v-model:open="importVisible"
      title="导入报工数据"
      @ok="handleImportConfirm"
      :confirmLoading="importLoading"
      width="600px"
    >
      <a-upload-dragger
        v-model:fileList="fileList"
        :beforeUpload="beforeUpload"
        accept=".xlsx,.xls"
        :multiple="false"
        @remove="handleFileRemove"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p class="ant-upload-hint">支持 .xlsx 和 .xls 格式</p>
      </a-upload-dragger>
      
      <div style="margin-top: 16px;">
        <a-alert
          message="导入说明"
          description="请确保Excel文件包含以下列：员工姓名、项目名称、部门名称、报工日期、工作时长、工作内容等字段。"
          type="info"
          show-icon
        />
      </div>
    </a-modal>

    <!-- 创建/编辑报工模态框 -->
    <a-modal
      v-model:open="formVisible"
      :title="isEdit ? '编辑报工记录' : '新增报工记录'"
      @ok="handleFormSubmit"
      :confirmLoading="formLoading"
      width="800px"
    >
      <a-form
        :model="formData"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 16 }"
        :rules="formRules"
        ref="formRef"
      >
        <a-form-item label="员工姓名" name="employee_name">
          <a-input v-model:value="formData.employee_name" placeholder="请输入员工姓名" />
        </a-form-item>
        <a-form-item label="项目名称" name="project_name">
          <a-input v-model:value="formData.project_name" placeholder="请输入项目名称" />
        </a-form-item>
        <a-form-item label="部门名称" name="department_name">
          <a-input v-model:value="formData.department_name" placeholder="请输入部门名称" />
        </a-form-item>
        <a-form-item label="报工日期" name="report_date">
          <a-date-picker v-model:value="formData.report_date" style="width: 100%" />
        </a-form-item>
        <a-form-item label="工作时长" name="work_hours">
          <a-input-number
            v-model:value="formData.work_hours"
            :min="0"
            :max="24"
            :precision="2"
            style="width: 100%"
            placeholder="请输入工作时长"
          />
        </a-form-item>
        <a-form-item label="工作内容" name="work_content">
          <a-textarea
            v-model:value="formData.work_content"
            :rows="4"
            placeholder="请输入工作内容"
          />
        </a-form-item>
        <a-form-item label="工作地点" name="work_location">
          <a-input v-model:value="formData.work_location" placeholder="请输入工作地点" />
        </a-form-item>
        <a-form-item label="状态" name="status">
          <a-select v-model:value="formData.status" placeholder="请选择状态">
            <a-select-option value="pending">待审核</a-select-option>
            <a-select-option value="approved">已通过</a-select-option>
            <a-select-option value="rejected">已拒绝</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 查看详情模态框 -->
    <a-modal
      v-model:open="viewVisible"
      title="报工记录详情"
      :footer="null"
      width="800px"
    >
      <a-descriptions :column="2" bordered v-if="viewData">
        <a-descriptions-item label="员工姓名">{{ viewData.employee_name }}</a-descriptions-item>
        <a-descriptions-item label="项目名称">{{ viewData.project_name }}</a-descriptions-item>
        <a-descriptions-item label="部门名称">{{ viewData.department_name }}</a-descriptions-item>
        <a-descriptions-item label="报工日期">{{ formatDate(viewData.report_date) }}</a-descriptions-item>
        <a-descriptions-item label="工作时长">{{ viewData.work_hours }}小时</a-descriptions-item>
        <a-descriptions-item label="工作地点">{{ viewData.work_location }}</a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(viewData.status)">
            {{ getStatusText(viewData.status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ formatDateTime(viewData.created_at) }}</a-descriptions-item>
        <a-descriptions-item label="工作内容" :span="2">
          <div style="white-space: pre-wrap;">{{ viewData.work_content }}</div>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { 
  SearchOutlined, 
  ReloadOutlined, 
  DownloadOutlined, 
  UploadOutlined,
  InboxOutlined,
  PlusOutlined
} from '@ant-design/icons-vue'
import apiClient from '../utils/axios'
import dayjs, { Dayjs } from 'dayjs'

// 响应式数据
const loading = ref(false)
const exportLoading = ref(false)
const importLoading = ref(false)
const formLoading = ref(false)
const importVisible = ref(false)
const formVisible = ref(false)
const viewVisible = ref(false)
const isEdit = ref(false)
const advancedSearchKey = ref([])
const fileList = ref<any[]>([])
const formRef = ref()

// 搜索表单
const searchForm = reactive({
  keyword: '',
  employee_name: '',
  project_name: '',
  department_name: '',
  status: undefined
})

const dateRange = ref<[Dayjs, Dayjs] | []>([])

// 搜索结果
const searchResult = reactive({
  data: [],
  total: 0,
  page: 1,
  size: 20
})

// 统计信息
const statistics = reactive({
  total_reports: 0,
  total_hours: 0,
  avg_hours: 0
})

// 表单数据
const formData = reactive({
  employee_name: '',
  project_name: '',
  department_name: '',
  report_date: null as Dayjs | null,
  work_hours: null as number | null,
  work_content: '',
  work_location: '',
  status: 'pending'
})

// 表单验证规则
const formRules = {
  employee_name: [{ required: true, message: '请输入员工姓名', trigger: 'blur' }],
  project_name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  department_name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
  report_date: [{ required: true, message: '请选择报工日期', trigger: 'change' }],
  work_hours: [{ required: true, message: '请输入工作时长', trigger: 'blur' }]
}

// 查看数据
interface ViewData {
  employee_name: string
  project_name: string
  department_name: string
  report_date: string
  work_hours: number
  work_location: string
  status: string
  created_at: string
  work_content: string
}
const viewData = ref<ViewData | null>(null)

// 表格列定义
const columns = [
  {
    title: '员工姓名',
    dataIndex: 'employee_name',
    key: 'employee_name',
    width: 100,
    fixed: 'left'
  },
  {
    title: '项目名称',
    dataIndex: 'project_name',
    key: 'project_name',
    width: 150
  },
  {
    title: '部门',
    dataIndex: 'department_name',
    key: 'department_name',
    width: 100
  },
  {
    title: '报工日期',
    dataIndex: 'report_date',
    key: 'report_date',
    width: 120
  },
  {
    title: '工作时长',
    dataIndex: 'work_hours',
    key: 'work_hours',
    width: 100
  },
  {
    title: '工作内容',
    dataIndex: 'work_content',
    key: 'work_content',
    width: 200,
    ellipsis: true
  },
  {
    title: '工作地点',
    dataIndex: 'work_location',
    key: 'work_location',
    width: 120
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 80
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    fixed: 'right'
  }
]

// 分页配置
const pagination = computed(() => ({
  current: searchResult.page,
  pageSize: searchResult.size,
  total: searchResult.total,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`,
  onChange: (page: number, size: number) => {
    searchResult.page = page
    searchResult.size = size
    handleSearch()
  }
}))

// 方法
const handleSearch = async () => {
  loading.value = true
  try {
    const params = {
      ...searchForm,
      start_date: (dateRange.value as [Dayjs, Dayjs])?.[0]?.format('YYYY-MM-DD'),
      end_date: (dateRange.value as [Dayjs, Dayjs])?.[1]?.format('YYYY-MM-DD'),
      page: searchResult.page,
      size: searchResult.size
    }
    
    console.log('搜索参数:', params)
    const { data } = await apiClient.get('/api/work-reports/search', { params })
    console.log('搜索结果:', data)
    
    if (data.success) {
      searchResult.data = data.data.data
      searchResult.total = data.data.total
    }
  } catch (error: any) {
    console.error('搜索失败:', error)
    console.error('错误详情:', error.response?.data || error.message)
    message.error('搜索失败: ' + (error.response?.data?.detail || error.message))
    // 设置空数据避免显示错误
    searchResult.data = []
    searchResult.total = 0
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  Object.assign(searchForm, {
    keyword: '',
    employee_name: '',
    project_name: '',
    department_name: '',
    status: undefined
  })
  dateRange.value = []
  searchResult.page = 1
  handleSearch()
}

const handleAdvancedSearch = () => {
  advancedSearchKey.value = []
  handleSearch()
}

const handleExport = async () => {
  exportLoading.value = true
  try {
    const params = {
      keyword: searchForm.keyword,
      start_date: (dateRange.value as [Dayjs, Dayjs])?.[0]?.format('YYYY-MM-DD'),
      end_date: (dateRange.value as [Dayjs, Dayjs])?.[1]?.format('YYYY-MM-DD')
    }
    
    const { data } = await apiClient.get('/api/work-reports/export', { params })
    if (data.success) {
      // 导出Excel文件
      const csvContent = convertToCSV(data.data)
      downloadCSV(csvContent, `报工数据_${dayjs().format('YYYY-MM-DD')}.csv`)
      message.success('导出成功')
    }
  } catch (error: any) {
    message.error('导出失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    exportLoading.value = false
  }
}

const convertToCSV = (data: any[]) => {
  if (!data.length) return ''
  
  const headers = Object.keys(data[0])
  const csvRows = [
    headers.join(','),
    ...data.map(row => 
      headers.map(header => {
        const value = row[header]
        return typeof value === 'string' ? `"${value}"` : value
      }).join(',')
    )
  ]
  
  return csvRows.join('\n')
}

const downloadCSV = (content: string, filename: string) => {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const handleImport = () => {
  importVisible.value = true
}

const beforeUpload = (file: File) => {
  const isExcel = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                  file.type === 'application/vnd.ms-excel'
  if (!isExcel) {
    message.error('只能上传 Excel 文件!')
    return false
  }
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过 10MB!')
    return false
  }
  return false // 阻止自动上传
}

const handleFileRemove = () => {
  fileList.value = []
}

const handleImportConfirm = async () => {
  if (fileList.value.length === 0) {
    message.error('请选择要上传的文件')
    return
  }
  
  importLoading.value = true
  try {
    const file = fileList.value[0]
    const formData = new FormData()
    formData.append('file', (file as any).originFileObj)
    
    const { data: result } = await apiClient.post('/api/work-reports/upload-excel', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    if (result.success) {
      message.success(`成功导入 ${result.count} 条记录`)
      importVisible.value = false
      fileList.value = []
      await loadStatistics()
      await handleSearch()
    }
  } catch (error: any) {
    message.error('导入失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    importLoading.value = false
  }
}

const showCreateModal = () => {
  isEdit.value = false
  resetForm()
  formVisible.value = true
}

const handleView = async (record: any) => {
  try {
    const { data } = await apiClient.get(`/api/work-reports/${record.id}`)
    if (data.success) {
      viewData.value = data.data
      viewVisible.value = true
    }
  } catch (error: any) {
    message.error('获取详情失败: ' + (error.response?.data?.detail || error.message))
  }
}

const handleEdit = (record: any) => {
  isEdit.value = true
  Object.assign(formData, {
    employee_name: record.employee_name || '',
    project_name: record.project_name || '',
    department_name: record.department_name || '',
    report_date: record.report_date ? dayjs(record.report_date) : null,
    work_hours: record.work_hours || null,
    work_content: record.work_content || '',
    work_location: record.work_location || '',
    status: record.status || 'pending'
  })
  formVisible.value = true
}

const handleDelete = (record: any) => {
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除这条报工记录吗？',
    onOk: async () => {
      try {
        const { data } = await apiClient.delete(`/api/work-reports/${record.id}`)
        if (data.success) {
          message.success('删除成功')
          await handleSearch()
          await loadStatistics()
        }
      } catch (error: any) {
        message.error('删除失败: ' + (error.response?.data?.detail || error.message))
      }
    }
  })
}

const handleFormSubmit = async () => {
  try {
    await formRef.value.validate()
    
    formLoading.value = true
    
    const submitData = {
      employee_name: formData.employee_name,
      project_name: formData.project_name,
      department_name: formData.department_name,
      report_date: formData.report_date?.format('YYYY-MM-DD'),
      work_hours: formData.work_hours,
      work_content: formData.work_content,
      work_location: formData.work_location,
      status: formData.status
    }
    
    if (isEdit.value) {
      // 编辑逻辑 - 这里需要获取当前记录的ID
      message.info('编辑功能需要完善，请联系开发人员')
    } else {
      // 创建逻辑
      const { data } = await apiClient.post('/api/work-reports/', submitData)
      if (data.success) {
        message.success('创建成功')
        formVisible.value = false
        await handleSearch()
        await loadStatistics()
      }
    }
  } catch (error: any) {
    if (error.errorFields) {
      message.error('请检查表单填写')
    } else {
      message.error('提交失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    formLoading.value = false
  }
}

const resetForm = () => {
  Object.assign(formData, {
    employee_name: '',
    project_name: '',
    department_name: '',
    report_date: null,
    work_hours: null,
    work_content: '',
    work_location: '',
    status: 'pending'
  })
}

const getStatusColor = (status: string) => {
  const colors: { [key: string]: string } = {
    pending: 'orange',
    approved: 'green',
    rejected: 'red'
  }
  return colors[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: { [key: string]: string } = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝'
  }
  return texts[status] || status
}

const formatDate = (date: string | Date) => {
  if (!date) return ''
  return dayjs(date).format('YYYY-MM-DD')
}

const formatDateTime = (date: string | Date) => {
  if (!date) return ''
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

const loadStatistics = async () => {
  try {
    console.log('开始加载统计信息...')
    const { data } = await apiClient.get('/api/work-reports/statistics')
    console.log('统计信息响应:', data)
    if (data.success) {
      Object.assign(statistics, data.data)
      console.log('统计信息加载成功:', statistics)
    }
  } catch (error: any) {
    console.error('加载统计信息失败:', error)
    console.error('错误详情:', error.response?.data || error.message)
    // 设置默认值避免显示错误
    Object.assign(statistics, {
      total_reports: 0,
      total_hours: 0,
      avg_hours: 0
    })
  }
}

// 生命周期
onMounted(() => {
  loadStatistics()
  handleSearch()
})
</script>

<style scoped>
.work-report-agent {
  padding: 24px;
}

.search-section {
  margin-bottom: 24px;
}

.statistics-section {
  margin-bottom: 24px;
}

.table-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
