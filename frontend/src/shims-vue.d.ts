/* Vue SFC 类型声明与路由 meta 扩展 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    role?: string
  }
}


