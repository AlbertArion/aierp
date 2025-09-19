import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 说明：Vite配置，包含跨域代理
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3127',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:3127',
        changeOrigin: true
      }
    }
  }
})


