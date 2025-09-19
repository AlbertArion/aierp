<template>
  <div style="max-width:360px;margin:48px auto">
    <a-card title="登录">
      <a-form @submit.prevent>
        <a-form-item label="用户名">
          <a-input v-model:value="username" />
        </a-form-item>
        <a-form-item label="密码">
          <a-input-password v-model:value="password" />
        </a-form-item>
        <a-space>
          <a-button type="primary" :loading="loading" @click="doLogin">登录</a-button>
          <a-button @click="fillAdmin">填充admin</a-button>
          <a-button @click="fillOps">填充ops</a-button>
        </a-space>
      </a-form>
    </a-card>
  </div>
  
</template>

<script setup lang="ts">
import { ref } from 'vue'
import apiClient from '../utils/axios'
import * as VueRouter from 'vue-router'

const router = (VueRouter as any).useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

const fillAdmin = () => {
  username.value = 'admin'
  password.value = 'admin123'
}
const fillOps = () => {
  username.value = 'ops'
  password.value = 'ops123'
}

const doLogin = async () => {
  loading.value = true
  try {
    const { data } = await apiClient.post('/api/auth/login', { username: username.value, password: password.value })
    localStorage.setItem('token', data.token)
    localStorage.setItem('role', data.user?.roles?.[0] || '')
    // Token已通过apiClient拦截器自动处理
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

