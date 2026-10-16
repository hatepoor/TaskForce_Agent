# Task 3: 会话列表与历史回填

> 模块: `06-会话管理`
> 前置 task: task2
> 模块依赖: 04 + 01(task1~3)
> 状态: ✅ 已完成

## 目标

侧栏会话列表可用(新建/切换/标题),切换旧会话能从 B1 端点回填历史与挂起占位。

## 前置准备

- [ ] task2 已完成并通过验收
- [ ] **模块 01 task1~3(B1/B2/B3)已验收**,B1 端点 curl 实测可用

## 实现步骤

1. **`ThreadList.vue` + `SessionItem.vue`**(用户誊写,交互参照 UI-DESIGN §1.1 上下文栏):
   - 文件: `dev/front/src/components/chat/ThreadList.vue`、`SessionItem.vue`
   - 详情: 新建按钮(调 `newThreadId()` 置当前,不请求后端);列表 = meta 排序 + 本地标题;当前项高亮;挂入 ContextPanel
2. **历史回填**:
   - 文件: `dev/front/src/stores/chat.ts`(补 `hydrateFromServer()`)
   - 详情: 切换会话时调 `GET /chat/threads/{id}/messages`;user/assistant 映射为 ChatItem;`pending_interrupt` 非空写 `pendingByThread` + push InterruptItem 占位(status: waiting)
3. **ChatView 侧栏装配**:空态改用 `EmptyState`(文案见 UI-DESIGN §3.4)
4. **前缀断言**:`loadThreads` 对无 `sess-` 前缀的 id console.warn

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/chat/ThreadList.vue` / `SessionItem.vue` | 新增 | 用户誊写 |
| `dev/front/src/stores/chat.ts` | 修改 | hydrateFromServer |
| `dev/front/src/views/ChatView.vue` | 修改 | 装配 |

## 验收标准

- [x] 新建三个会话,刷新后当前会话与列表仍在
- [x] 切换旧会话,历史消息回填正确(内部消息已过滤,无 `[用户回答]:` 冒泡)
- [x] 挂起中的会话切换回来,挂起占位恢复(点不动没关系,卡片在模块 08 实现)
- [x] 会话间消息不串台

> 验收说明:headless Edge 探针(CDP 驱动,真实后端 8001)20/20 通过 —— 新建 3 条后刷新,当前项仍高亮、3 条仍在列表;`sess-5d842656` / `sess-20e5ed3c` 各 14 条历史与 B1 端点逐条一致、无内部合成消息;切走再切回内容一致、两会话内容不同;`sess-dca9d5ee`(pending=ask)切回后占位恢复且文本等于 `pending_interrupt.text`;零未捕获 JS 异常。
>
> 实现说明:ChatView 本轮只做「最小渲染」(纯文本列表 + 挂起占位行),正式气泡 / 轨迹 / 用量组件由模块 07 的 MessageList 替换;空态用 `EmptyState`(标题 + 说明),UI-DESIGN §3.4 的三个示例问句按钮待模块 07 的 Composer 就位后接入(点击填入输入框,当前无输入框可填)。
