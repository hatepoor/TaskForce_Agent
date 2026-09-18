# 会话管理

> 编号: `06`
> 英文标识: `session-management`
> 状态: ✅ 已完成
> 最后更新: 2026-09-16

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [04-API层与类型镜像](../04-API层与类型镜像/develop.md) | `api/chat.ts` 的 threads/threadsMeta/threadMessages | `ThreadMetaRow`、消息回填响应 |
| [01-后端契约改造](../01-后端契约改造/develop.md) task1~3 | B1 历史回填、B2 元数据、B3 信封(挂起态恢复用) | `GET /chat/threads/{id}/messages`、`/chat/threads/meta` |
| [03-应用外壳与路由](../03-应用外壳与路由/develop.md) | ContextPanel 插槽、原子组件 | `EmptyState`、`StatusDot` |

---

## 概述

会话身份与列表:前端自生成 `sess-` 前缀 thread_id、会话列表(后端 meta + 本地标题)、切换会话并回填历史消息与挂起态。本模块建立 `useChatStore` 骨架(消息数据结构供模块 07 使用)。

## 功能清单

- **thread_id 生成**:`newThreadId()` = `sess-` + UUID,含非安全上下文降级
- **本地会话元数据**:localStorage 存 `{threadId: {title, createdAt, lastActiveAt}}`,标题取首条输入前 20 字
- **会话列表**:ThreadList 组件(meta 排序 + 本地标题融合),新建/切换/高亮
- **历史回填**:切换会话调 B1 端点渲染历史;`pending_interrupt` 非空恢复挂起占位(卡片的交互实现在模块 08)
- **chat store 骨架**:`itemsByThread` / `turnByThread` / `pendingByThread` 按会话分组

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `useChatStore` | Pinia | `currentThreadId` / `items` / `pending` / `switchThread()` 等,模块 07/08 依赖 |
| `newThreadId()` | 函数 | 唯一 id 生成入口 |
| `ThreadList.vue` / `SessionItem.vue` | 组件 | 挂入 ContextPanel |

## 模块开发规范

### 本模块关键约束

- **id 必须带 `sess-` 前缀**且**前端生成**(坑 3:裸 UUID 不进列表;usage 帧才带 id 不能等它)
- 新建会话不立即请求后端(后端首次 /chat 才建 checkpoint)
- 挂起态恢复依赖 B1;B1 未落地时不做降级缓存方案(设计已裁决等 B1)
- 对 `/chat/threads` 返回的 id 做前缀断言,漂移 `console.warn` 暴露
