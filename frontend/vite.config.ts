import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 说明：Vite配置，包含跨域代理和环境变量支持
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBaseUrl = env.VITE_API_BASE_URL || 'http://localhost:3127'
  
  return {
    plugins: [vue()],
    server: {
      port: 5176,
      proxy: {
        '/api': {
          target: apiBaseUrl,
          changeOrigin: true
        },
        '/health': {
          target: apiBaseUrl,
          changeOrigin: true
        }
      }
    },
    define: {
      __API_BASE_URL__: JSON.stringify(apiBaseUrl)
    }
  }
})


