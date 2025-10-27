<template>
  <div class="sap-work-reports">
    <div class="header">
      <h1>📊 SAP报工数据查询</h1>
      <p>基于SAP系统的报工数据智能查询平台</p>
    </div>

    <!-- 搜索区域 -->
    <div class="search-section">
      <div class="search-form">
        <div class="form-row">
          <div class="form-group">
            <label>关键字搜索</label>
            <input 
              v-model="searchForm.keyword" 
              type="text" 
              placeholder="输入订单号、创建人等信息"
              @keyup.enter="search"
            />
          </div>
          <div class="form-group">
            <label>订单号</label>
            <input 
              v-model="searchForm.aufnr" 
              type="text" 
              placeholder="输入订单号"
            />
          </div>
          <div class="form-group">
            <label>工厂</label>
            <input 
              v-model="searchForm.werks" 
              type="text" 
              placeholder="输入工厂代码"
            />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>开始日期</label>
            <input 
              v-model="searchForm.start_date" 
              type="date"
            />
          </div>
          <div class="form-group">
            <label>结束日期</label>
            <input 
              v-model="searchForm.end_date" 
              type="date"
            />
          </div>
          <div class="form-group">
            <button @click="search" class="search-btn" :disabled="loading">
              {{ loading ? '搜索中...' : '🔍 搜索' }}
            </button>
            <button @click="resetSearch" class="reset-btn">
              🔄 重置
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="stats-section" v-if="statistics">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-number">{{ statistics.total_records || 0 }}</div>
          <div class="stat-label">总记录数</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">{{ statistics.aufk || 0 }}</div>
          <div class="stat-label">订单数</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">{{ statistics.afpo || 0 }}</div>
          <div class="stat-label">订单项目数</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">{{ statistics.makt || 0 }}</div>
          <div class="stat-label">物料数</div>
        </div>
      </div>
    </div>

    <!-- 搜索结果 -->
    <div class="results-section" v-if="searchResults">
      <div class="results-header">
        <h3>搜索结果</h3>
        <div class="results-info">
          共找到 <strong>{{ searchResults.total }}</strong> 条记录，
          第 <strong>{{ searchResults.page }}</strong> 页，
          共 <strong>{{ searchResults.pages }}</strong> 页
        </div>
      </div>

      <div class="results-table">
        <table>
          <thead>
            <tr>
              <th>订单号</th>
              <th>订单类型</th>
              <th>工厂</th>
              <th>创建人</th>
              <th>创建日期</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in searchResults.records" :key="record.id">
              <td>{{ record.aufnr }}</td>
              <td>{{ record.auart }}</td>
              <td>{{ record.werks }}</td>
              <td>{{ record.ernam }}</td>
              <td>{{ formatDate(record.erdat) }}</td>
              <td>
                <span class="status-badge" v-if="record.jest_items && record.jest_items.length > 0">
                  {{ record.jest_items[0].stat }}
                </span>
              </td>
              <td>
                <button @click="viewDetails(record)" class="view-btn">
                  👁️ 查看详情
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="searchResults.pages > 1">
        <button 
          @click="changePage(searchResults.page - 1)" 
          :disabled="searchResults.page <= 1"
          class="page-btn"
        >
          上一页
        </button>
        <span class="page-info">
          第 {{ searchResults.page }} 页 / 共 {{ searchResults.pages }} 页
        </span>
        <button 
          @click="changePage(searchResults.page + 1)" 
          :disabled="searchResults.page >= searchResults.pages"
          class="page-btn"
        >
          下一页
        </button>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div class="modal" v-if="selectedRecord" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>订单详情 - {{ selectedRecord.aufnr }}</h3>
          <button @click="closeModal" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-section">
            <h4>基本信息</h4>
            <div class="detail-grid">
              <div class="detail-item">
                <label>订单号:</label>
                <span>{{ selectedRecord.aufnr }}</span>
              </div>
              <div class="detail-item">
                <label>订单类型:</label>
                <span>{{ selectedRecord.auart }}</span>
              </div>
              <div class="detail-item">
                <label>工厂:</label>
                <span>{{ selectedRecord.werks }}</span>
              </div>
              <div class="detail-item">
                <label>创建人:</label>
                <span>{{ selectedRecord.ernam }}</span>
              </div>
              <div class="detail-item">
                <label>创建日期:</label>
                <span>{{ formatDate(selectedRecord.erdat) }}</span>
              </div>
              <div class="detail-item">
                <label>修改人:</label>
                <span>{{ selectedRecord.aenam }}</span>
              </div>
              <div class="detail-item">
                <label>修改日期:</label>
                <span>{{ formatDate(selectedRecord.aedat) }}</span>
              </div>
            </div>
          </div>

          <div class="detail-section" v-if="selectedRecord.afpo_items && selectedRecord.afpo_items.length > 0">
            <h4>订单项目 ({{ selectedRecord.afpo_items.length }} 项)</h4>
            <div class="items-table">
              <table>
                <thead>
                  <tr>
                    <th>项目号</th>
                    <th>物料号</th>
                    <th>计划数量</th>
                    <th>已确认数量</th>
                    <th>计量单位</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in selectedRecord.afpo_items" :key="item.posnr">
                    <td>{{ item.posnr }}</td>
                    <td>{{ item.matnr }}</td>
                    <td>{{ item.psmng }}</td>
                    <td>{{ item.wemng }}</td>
                    <td>{{ item.meins }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="detail-section" v-if="selectedRecord.jest_items && selectedRecord.jest_items.length > 0">
            <h4>状态信息 ({{ selectedRecord.jest_items.length }} 个)</h4>
            <div class="status-list">
              <span 
                v-for="status in selectedRecord.jest_items" 
                :key="status.stat"
                class="status-tag"
              >
                {{ status.stat }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

// 响应式数据
const loading = ref(false)
const searchForm = ref({
  keyword: '',
  aufnr: '',
  werks: '',
  start_date: '',
  end_date: ''
})
const searchResults = ref(null)
const statistics = ref(null)
const selectedRecord = ref(null)

// API基础URL
const API_BASE = '/api/v1/sap-work-reports'

// 搜索功能
const search = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchForm.value.keyword) params.append('keyword', searchForm.value.keyword)
    if (searchForm.value.aufnr) params.append('aufnr', searchForm.value.aufnr)
    if (searchForm.value.werks) params.append('werks', searchForm.value.werks)
    if (searchForm.value.start_date) params.append('start_date', searchForm.value.start_date)
    if (searchForm.value.end_date) params.append('end_date', searchForm.value.end_date)
    params.append('page', '1')
    params.append('size', '20')

    const response = await axios.get(`${API_BASE}/search?${params}`)
    searchResults.value = response.data.data
  } catch (error) {
    console.error('搜索失败:', error)
    alert('搜索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = {
    keyword: '',
    aufnr: '',
    werks: '',
    start_date: '',
    end_date: ''
  }
  searchResults.value = null
}

// 分页
const changePage = async (page: number) => {
  if (page < 1 || page > searchResults.value.pages) return
  
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchForm.value.keyword) params.append('keyword', searchForm.value.keyword)
    if (searchForm.value.aufnr) params.append('aufnr', searchForm.value.aufnr)
    if (searchForm.value.werks) params.append('werks', searchForm.value.werks)
    if (searchForm.value.start_date) params.append('start_date', searchForm.value.start_date)
    if (searchForm.value.end_date) params.append('end_date', searchForm.value.end_date)
    params.append('page', page.toString())
    params.append('size', '20')

    const response = await axios.get(`${API_BASE}/search?${params}`)
    searchResults.value = response.data.data
  } catch (error) {
    console.error('分页失败:', error)
    alert('分页失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 查看详情
const viewDetails = (record: any) => {
  selectedRecord.value = record
}

// 关闭弹窗
const closeModal = () => {
  selectedRecord.value = null
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN')
  } catch {
    return dateStr
  }
}

// 获取统计信息
const loadStatistics = async () => {
  try {
    const response = await axios.get(`${API_BASE}/statistics`)
    statistics.value = response.data.data
  } catch (error) {
    console.error('获取统计信息失败:', error)
  }
}

// 组件挂载时加载统计信息
onMounted(() => {
  loadStatistics()
})
</script>

<style scoped>
.sap-work-reports {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  color: #2c3e50;
  margin-bottom: 10px;
}

.header p {
  color: #7f8c8d;
  font-size: 16px;
}

.search-section {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 30px;
}

.search-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-row {
  display: flex;
  gap: 15px;
  align-items: end;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 500;
  margin-bottom: 5px;
  color: #2c3e50;
}

.form-group input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.search-btn, .reset-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.search-btn {
  background: #3498db;
  color: white;
}

.search-btn:hover:not(:disabled) {
  background: #2980b9;
}

.search-btn:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.reset-btn {
  background: #95a5a6;
  color: white;
}

.reset-btn:hover {
  background: #7f8c8d;
}

.stats-section {
  margin-bottom: 30px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  text-align: center;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: #3498db;
  margin-bottom: 5px;
}

.stat-label {
  color: #7f8c8d;
  font-size: 14px;
}

.results-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
}

.results-header {
  padding: 20px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.results-header h3 {
  margin: 0;
  color: #2c3e50;
}

.results-info {
  color: #7f8c8d;
  font-size: 14px;
}

.results-table {
  overflow-x: auto;
}

.results-table table {
  width: 100%;
  border-collapse: collapse;
}

.results-table th,
.results-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.results-table th {
  background: #f8f9fa;
  font-weight: 500;
  color: #2c3e50;
}

.results-table tr:hover {
  background: #f8f9fa;
}

.status-badge {
  background: #e74c3c;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.view-btn {
  background: #27ae60;
  color: white;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.view-btn:hover {
  background: #229954;
}

.pagination {
  padding: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 15px;
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.page-btn:hover:not(:disabled) {
  background: #f8f9fa;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  color: #7f8c8d;
  font-size: 14px;
}

.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 800px;
  max-height: 80vh;
  overflow-y: auto;
  width: 90%;
}

.modal-header {
  padding: 20px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  color: #2c3e50;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #7f8c8d;
}

.close-btn:hover {
  color: #2c3e50;
}

.modal-body {
  padding: 20px;
}

.detail-section {
  margin-bottom: 30px;
}

.detail-section h4 {
  color: #2c3e50;
  margin-bottom: 15px;
  padding-bottom: 5px;
  border-bottom: 2px solid #3498db;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.detail-item label {
  font-weight: 500;
  color: #7f8c8d;
  font-size: 14px;
}

.detail-item span {
  color: #2c3e50;
  font-size: 16px;
}

.items-table {
  overflow-x: auto;
}

.items-table table {
  width: 100%;
  border-collapse: collapse;
}

.items-table th,
.items-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.items-table th {
  background: #f8f9fa;
  font-weight: 500;
  color: #2c3e50;
}

.status-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-tag {
  background: #3498db;
  color: white;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 14px;
}

@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
  }
  
  .results-header {
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }
  
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
