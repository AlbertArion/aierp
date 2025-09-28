// 避免TS对vue-router类型解析异常：以命名空间方式引入并降级类型
// 运行时不受影响，待IDE恢复解析后可改回标准导入
// import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import * as VueRouter from 'vue-router'
const createRouter = (VueRouter as any).createRouter as any
const createWebHistory = (VueRouter as any).createWebHistory as any
type RouteRecordRaw = any

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/integration' },
  { path: '/login', component: () => import('../pages/Login.vue') },
  { path: '/integration', component: () => import('../pages/Integration.vue') },
  { path: '/predict', component: () => import('../pages/Predict.vue') },
  { path: '/orders', component: () => import('../pages/Orders.vue'), meta: { requiresAuth: true, role: 'admin' } },
  { path: '/rules', component: () => import('../pages/Rules.vue'), meta: { requiresAuth: true, role: 'admin' } },
        { path: '/work-report-agent', component: () => import('../pages/WorkReportAgent.vue'), meta: { requiresAuth: true, role: 'admin' } },
        { path: '/work-report-chat', component: () => import('../pages/WorkReportChat.vue'), meta: { requiresAuth: true, role: 'admin' } },
        { path: '/pricing-agent', component: () => import('../pages/PricingAgent.vue'), meta: { requiresAuth: true, role: 'admin' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to: any, _from: any, next: any) => {
  if (!to.meta?.requiresAuth) return next()
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  if (!token) return next('/login')
  if (to.meta?.role && role !== to.meta.role) return next('/login')
  next()
})

export default router


