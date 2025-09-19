<template>
  <a-layout class="app-layout">
    <a-layout-header class="app-header">
      <div class="brand">
        <div class="brand-mark" />
        <div class="brand-name">{{ t('brand') }}</div>
      </div>
      <div class="header-right">
        <a-switch v-model:checked="dark" checked-children="Dark" un-checked-children="Light" />
        <a-tag v-if="backendOk === true" color="green">后端正常</a-tag>
        <a-tag v-else-if="backendOk === false" color="red">后端未就绪</a-tag>
      </div>
    </a-layout-header>
    <a-layout class="app-main">
      <a-layout-sider :collapsed="collapsed" :collapsible="true" :trigger="null" width="200" class="app-sider">
        <div class="sider-trigger" @click="collapsed = !collapsed">
          <a-button type="text" size="small">
            <template #icon>
              <LeftOutlined v-if="!collapsed" />
              <RightOutlined v-else />
            </template>
          </a-button>
        </div>
        <a-menu theme="dark" mode="inline" class="app-menu">
          <a-menu-item key="1" @click="go('/integration')">
            <template #icon>
              <DatabaseOutlined />
            </template>
            <span v-if="!collapsed">{{ t('menu.integration') }}</span>
          </a-menu-item>
          <a-menu-item key="2" @click="go('/predict')">
            <template #icon>
              <BarChartOutlined />
            </template>
            <span v-if="!collapsed">{{ t('menu.predict') }}</span>
          </a-menu-item>
          <a-menu-item key="3" @click="go('/orders')">
            <template #icon>
              <ShoppingCartOutlined />
            </template>
            <span v-if="!collapsed">{{ t('menu.orders') }}</span>
          </a-menu-item>
          <a-menu-item key="4" @click="go('/rules')">
            <template #icon>
              <SettingOutlined />
            </template>
            <span v-if="!collapsed">{{ t('menu.rules') }}</span>
          </a-menu-item>
        </a-menu>
      </a-layout-sider>
      <a-layout-content class="app-content">
        <div class="page-container">
          <router-view />
        </div>
      </a-layout-content>
    </a-layout>
    <a-layout-footer class="app-footer">© 2025 AI ERP</a-layout-footer>
  </a-layout>
  
</template>

<script setup lang="ts">
import * as VueRouter from 'vue-router'
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import apiClient from './utils/axios'
import { LeftOutlined, RightOutlined, DatabaseOutlined, BarChartOutlined, ShoppingCartOutlined, SettingOutlined } from '@ant-design/icons-vue'
const router = (VueRouter as any).useRouter()
const go = (path: string) => router.push(path)
const { t } = useI18n()

const backendOk = ref<boolean | null>(null)
const collapsed = ref(false)
const dark = ref(false)

const applyTheme = (isDark: boolean) => {
  const theme = isDark ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme)
  console.log('Theme switched to:', theme) // 调试日志
}

// 监听 dark 值变化
watch(dark, (newValue) => {
  applyTheme(newValue)
})
onMounted(async () => {
  try {
    const { data } = await apiClient.get('/health')
    backendOk.value = data?.status === 'ok'
  } catch {
    backendOk.value = false
  }
  // 初始化主题
  applyTheme(dark.value)
})
</script>

<style>
/* 全局主题变量 */
:root {
  --header-bg: #0b2540;
  --brand-name-color: #fff;
  --content-bg: #f5f7fb;
  --menu-selected-bg: rgba(22, 119, 255, .18);
  --sider-shadow: rgba(0, 0, 0, 0.15);
  --text-color: rgba(0, 0, 0, 0.85);
}

[data-theme="dark"] {
  --header-bg: #0b2540;
  --brand-name-color: #e5e7eb;
  --content-bg: #0f172a;
  --menu-selected-bg: rgba(22, 119, 255, .28);
  --sider-shadow: rgba(0, 0, 0, 0.35);
  --text-color: rgba(255, 255, 255, 0.85);
}

/* 暗色主题下的 Ant Design 组件 */
[data-theme="dark"] .ant-layout {
  background: var(--content-bg) !important;
}

[data-theme="dark"] .ant-layout-content {
  background: var(--content-bg) !important;
  color: var(--text-color) !important;
}

[data-theme="dark"] .ant-layout-sider {
  background: #0b2540 !important;
}

[data-theme="dark"] .ant-menu-dark {
  background: #0b2540 !important;
}

[data-theme="dark"] .ant-menu-dark .ant-menu-item {
  color: #fff !important;
}

[data-theme="dark"] .ant-menu-dark .ant-menu-item:hover {
  color: #fff !important;
  background: var(--menu-selected-bg) !important;
}

[data-theme="dark"] .ant-menu-dark .ant-menu-item-selected {
  color: #fff !important;
  background: var(--menu-selected-bg) !important;
}

[data-theme="dark"] .ant-card {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.2) !important;
  transition: all 0.3s ease !important;
}

[data-theme="dark"] .ant-card:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.3) !important;
  border-color: rgba(22, 119, 255, 0.3) !important;
}

[data-theme="dark"] .ant-card-head {
  background: rgba(255, 255, 255, 0.02) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 12px 12px 0 0 !important;
}

[data-theme="dark"] .ant-card-head-title {
  color: #fff !important;
  font-weight: 600 !important;
  font-size: 16px !important;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3) !important;
}

[data-theme="dark"] .ant-card-body {
  color: var(--text-color) !important;
  background: rgba(255, 255, 255, 0.01) !important;
  border-radius: 0 0 12px 12px !important;
}

[data-theme="dark"] .ant-input,
[data-theme="dark"] .ant-select-selector {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  color: var(--text-color) !important;
  border-radius: 8px !important;
  transition: all 0.3s ease !important;
  backdrop-filter: blur(10px) !important;
}

[data-theme="dark"] .ant-input:hover,
[data-theme="dark"] .ant-select-selector:hover {
  border-color: rgba(22, 119, 255, 0.5) !important;
  background: rgba(255, 255, 255, 0.08) !important;
}

[data-theme="dark"] .ant-input:focus,
[data-theme="dark"] .ant-select-focused .ant-select-selector {
  border-color: #1677ff !important;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2) !important;
  background: rgba(255, 255, 255, 0.1) !important;
}

[data-theme="dark"] .ant-btn {
  color: var(--text-color) !important;
  border-radius: 8px !important;
  transition: all 0.3s ease !important;
  font-weight: 500 !important;
}

[data-theme="dark"] .ant-btn-primary {
  background: linear-gradient(135deg, #1677ff 0%, #4096ff 100%) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.3) !important;
}

[data-theme="dark"] .ant-btn-primary:hover {
  background: linear-gradient(135deg, #4096ff 0%, #1677ff 100%) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.4) !important;
}

[data-theme="dark"] .ant-btn:not(.ant-btn-primary) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  color: var(--text-color) !important;
}

[data-theme="dark"] .ant-btn:not(.ant-btn-primary):hover {
  background: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(255, 255, 255, 0.25) !important;
  transform: translateY(-1px) !important;
}

[data-theme="dark"] .ant-tag {
  color: #fff !important;
}

[data-theme="dark"] .ant-tag-green {
  background: #52c41a !important;
  color: #fff !important;
}

[data-theme="dark"] .ant-tag-red {
  background: #ff4d4f !important;
  color: #fff !important;
}

[data-theme="dark"] .ant-upload {
  color: var(--text-color) !important;
}

[data-theme="dark"] .ant-upload-text {
  color: var(--text-color) !important;
}

[data-theme="dark"] .ant-upload-drag-text {
  color: var(--text-color) !important;
}

[data-theme="dark"] .ant-form-item-label > label {
  color: #e2e8f0 !important;
  font-weight: 500 !important;
  font-size: 14px !important;
}

[data-theme="dark"] .ant-form-item {
  margin-bottom: 20px !important;
}

[data-theme="dark"] .ant-form-item-label {
  padding-bottom: 4px !important;
}

[data-theme="dark"] .ant-select-selection-item {
  color: var(--text-color) !important;
}

[data-theme="dark"] .ant-select-selection-placeholder {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-select-arrow {
  color: rgba(255, 255, 255, 0.65) !important;
}

[data-theme="dark"] .ant-select:hover .ant-select-arrow {
  color: rgba(255, 255, 255, 0.85) !important;
}

[data-theme="dark"] .ant-select-focused .ant-select-arrow {
  color: #1677ff !important;
}

/* 优化深色模式下的表格样式 */
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

/* 优化深色模式下的空状态 */
[data-theme="dark"] .ant-empty {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-empty-description {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-empty-icon {
  color: rgba(255, 255, 255, 0.25) !important;
}

/* 优化深色模式下的分割线 */
[data-theme="dark"] .ant-divider {
  border-color: rgba(255, 255, 255, 0.1) !important;
}

/* 优化深色模式下的空间组件 */
[data-theme="dark"] .ant-space {
  color: #e2e8f0 !important;
}

/* 优化深色模式下的输入框占位符 */
[data-theme="dark"] .ant-input::placeholder {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-input-number::placeholder {
  color: rgba(255, 255, 255, 0.45) !important;
}

[data-theme="dark"] .ant-textarea::placeholder {
  color: rgba(255, 255, 255, 0.45) !important;
}
</style>

<style scoped>

.app-layout { 
  height: 100vh; 
  display: flex; 
  flex-direction: column; 
  overflow: hidden;
}
.app-header { 
  display:flex; 
  align-items:center; 
  justify-content:space-between; 
  background: var(--header-bg); 
  height: 64px;
  flex-shrink: 0;
  padding: 0 24px;
}
.brand { display:flex; align-items:center; gap:10px; }
.brand-mark { width:10px; height:10px; border-radius:2px; background:#1677ff; box-shadow:0 0 12px rgba(22,119,255,.6); }
.brand-name { color: var(--brand-name-color); font-weight:700; letter-spacing:.5px; }

.header-right { 
  display: flex; 
  align-items: center; 
  gap: 16px; 
  z-index: 1000;
  position: relative;
}

.app-main { 
  flex: 1; 
  display: flex; 
  overflow: hidden;
}
.app-sider {
  flex-shrink: 0;
  height: 100%;
  overflow-y: auto;
  box-shadow: 2px 0 8px var(--sider-shadow);
  z-index: 9;
}
.app-menu :deep(.ant-menu-item) { 
  margin:4px 8px; 
  border-radius:6px; 
  display: flex;
  align-items: center;
}
.app-menu :deep(.ant-menu-item-selected) { 
  background: var(--menu-selected-bg); 
}
.app-menu :deep(.ant-menu-item-icon) {
  font-size: 16px;
  margin-right: 8px;
}

.app-content { 
  flex: 1;
  padding:24px; 
  background: var(--content-bg); 
  color: var(--text-color);
  overflow-y: auto;
  height: 100%;
}
.page-container { max-width:1200px; margin:0 auto; }

.app-footer { 
  text-align:center; 
  background: #0b2540; /* 始终与顶部保持一致的深蓝色 */
  border-top: 1px solid rgba(255, 255, 255, 0.1); /* 始终使用浅色边框 */
  color: #fff; /* 始终使用白色文字 */
  height: 64px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sider-trigger {
  position: absolute;
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
  z-index: 10;
}

.sider-trigger :deep(.ant-btn) {
  color: rgba(255, 255, 255, 0.85);
  border: none;
  background: transparent;
  box-shadow: none;
}

.sider-trigger :deep(.ant-btn:hover) {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}
</style>


