# Task 1: hash 路由与四个空视图

> 模块: `03-应用外壳与路由`
> 前置 task: 无
> 模块依赖: 02
> 状态: ✅ 已完成

## 目标

四条顶层路由(hash 模式)挂上四个懒加载空视图,KeepAlive 生效。

## 前置准备

- [ ] 模块 02 全部验收通过

## 实现步骤

1. **`src/router/index.ts`**(用户誊写):
   - 文件: `dev/front/src/router/index.ts`
   - 详情: `createWebHashHistory`;`/chat/:threadId?`、`/knowledge`、`/memory`、`/settings` 四条,全部 `() => import(...)` 懒加载,默认重定向 `/chat`
2. **四个空视图**:
   - 文件: `dev/front/src/views/ChatView.vue` / `KnowledgeView.vue` / `MemoryView.vue` / `SettingsView.vue`
   - 详情: 各只含视图标题占位
3. **main.ts 装配 router**,App.vue 的 `<router-view>` 外包 `<KeepAlive>`:
   - 文件: `dev/front/src/main.ts`、`src/App.vue`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/router/index.ts` | 新增 | 用户誊写 |
| `dev/front/src/views/*.vue`(4 个) | 新增 | 占位 |
| `dev/front/src/main.ts` / `App.vue` | 修改 | 装配 |

## 验收标准

- [x] `http://localhost:5173/#/chat` 等四条路由可切换,浏览器前进/后退可用
- [x] 刷新 `#/memory` 直达记忆视图(hash 特性)
- [x] `vue-tsc --noEmit` 零错误
