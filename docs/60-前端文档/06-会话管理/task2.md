# Task 2: chat store 骨架

> 模块: `06-会话管理`
> 前置 task: task1
> 模块依赖: 04
> 状态: ✅ 已完成

## 目标

`useChatStore` 按会话分组的数据结构就位,动作函数留空壳,模块 07 填充。

## 前置准备

- [ ] task1 已完成并通过验收
- [ ] ARCHITECTURE §5.2 store 骨架已通读

## 实现步骤

1. **`src/stores/chat.ts`**(用户誊写骨架):
   - 文件: `dev/front/src/stores/chat.ts`
   - 详情: `threads` / `currentThreadId` / `threadMeta` / `itemsByThread` / `turnByThread` / `pendingByThread` 六个 ref + computed;`beginTurn/appendToken/flushTokens/pushRoute/setPending/attachUsage/endTurn/failTurn/resolvePending` 空实现占位;`switchThread(id)` 与 `loadThreads()`(调 B2 端点 + 本地标题融合)先实现
2. **ThreadList 切换联动**:`switchThread` 更新当前 id 并触发 task3 的回填

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/stores/chat.ts` | 新增 | 骨架,空壳动作 |
| `dev/front/src/utils/id.ts` | 不变 | currentThreadId 初始化用 newThreadId |

## 验收标准

- [x] `loadThreads()` 拉到 meta 列表并按最近活跃排序
- [x] 切换会话时 computed(items/turn/pending)正确切换
- [x] 未实现动作被调用时 console.warn 而非报错

> 验收说明:排序沿用后端 `ORDER BY last_checkpoint DESC`;本地新建但无 checkpoint 的会话由 `sessionList` 置顶(否则它不在这份后端数据里)。computed 切换与空壳 warn 由 `stores/chat.test.ts` 覆盖;真实浏览器中列表 47 条按最近活跃排列(探针实测)。
