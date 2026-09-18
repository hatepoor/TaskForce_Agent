# 会话管理 开发进度

> 编号: `06`
> 依赖模块: 04 + 01(task1~3)
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | thread_id 生成与本地元数据 | ✅ | 无 |
| [task2](./task2.md) | chat store 骨架 | ✅ | task1 |
| [task3](./task3.md) | 会话列表与历史回填 | ✅ | task2 + 模块01(task1~3) |

## 进度日志

### 2026-09-16

- ⬜ task1~task3: 未开始
- 备注:task3 硬依赖后端 B1/B2/B3 落地

### 2026-09-17

- ✅ task1: `utils/id.ts`(`sess-` 前缀 + crypto.randomUUID 降级)、`utils/time.ts`(fmtRelative)、`composables/useLocalStore.ts`(版本信封 v1 + 全链路容错 + `tf.threads` / `tf.currentThreadId` 读写)
- ✅ task2: `stores/chat.ts` 骨架 — 六个 ByThread 分组 ref + items/turn/pending/isStreaming/loadingHistory/sessionList computed;已实现 `newThread / switchThread / loadThreads / ensureHydrated / hydrateFromServer / touchThread / setThreadTitle`,轮次动作(beginTurn~resolvePending)空壳 console.warn 留给模块 07
- ✅ task3: `components/chat/ThreadList.vue` + `SessionItem.vue`(新建/切换/高亮/相对时间);ContextPanel 按路由注入会话列表;ChatView 装配(深链 + URL 同步 + EmptyState 空态 + 历史最小渲染);`loadThreads` 对无 `sess-` 前缀 id 打 warn
- 单测:`utils/id.test.ts`(5)、`utils/time.test.ts`(4)、`composables/useLocalStore.test.ts`(8)、`stores/chat.test.ts`(14,含排序/前缀 warn/回填映射/并发回填竞态/不串台/持久化/空壳动作)
- 验收证据:npx vue-tsc --noEmit 零错误;npm run build 通过;npm test 59/59(模块 06 新增 31 条);headless Edge 探针 20/20 于真实后端(8001)— 47 条会话列表、新建 3 条刷新后仍在且当前项高亮、14 条历史与 B1 逐条一致且无 `[用户回答]:` 泄漏、切走再切回内容一致、pending=ask 会话占位恢复、零未捕获 JS 异常
- 备注:临时探针(`tf-probe-06.mjs`,CDP 驱动 headless Edge)用后已删;本轮业务代码按用户指示由 Claude 落盘(非常规教学模式)
- 备注:测试机 8000 端口无服务(用户后端在 8001,dev proxy 已指向它);探针期间自起的 8000 uvicorn 请求挂起未响应,已关闭,不影响本模块验收