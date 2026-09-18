/**
 * 路由表:hash 模式 + 4 条顶层路由懒加载(ARCHITECTURE §1.2)。
 * 必须 hash 模式:生产形态是 FastAPI 同源挂载 SPA,history 模式下前端路径
 * 会与后端 /memory 等真实端点撞车;hash 下服务端永远只看到 /。
 */
import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHashHistory } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/chat' },
  { path: '/chat/:threadId?', name: 'chat', component: () => import('@/views/ChatView.vue') },
  { path: '/knowledge', name: 'knowledge', component: () => import('@/views/KnowledgeView.vue') },
  { path: '/memory', name: 'memory', component: () => import('@/views/MemoryView.vue') },
  // 设置页分四节独立展示:节名走路由参数(侧栏节列表切换,刷新/深链直达)
  {
    path: '/settings/:section(mcp|skills|health|models)?',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
  },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router