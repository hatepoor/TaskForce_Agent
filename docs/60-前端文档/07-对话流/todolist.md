# 对话流 开发进度

> 编号: `07`
> 依赖模块: 05 + 06 + 01(task4)
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | 轮次机制与 useChatStream | ✅ | 模块05+06 |
| [task2](./task2.md) | 消息渲染组件 | ✅ | task1 |
| [task3](./task3.md) | 错误态与滚动策略 | ✅ | task2 |

## 进度日志

### 2026-09-16

- ⬜ task1~task3: 未开始
- 备注:核心模块,B4 落地与否决定 task3 错误判定实现细节

### 2026-09-17

- ✅ task1: store 轮次动作实现化(`pushUser/beginTurn/appendToken/flushTokens/pushRoute/setPending/attachUsage/endTurn/abortTurn/failTurn/noteTurn/resolvePending` + `turnHasOutput`);新增 `composables/useChatStream.ts`(send/resend/answer/confirm/abort,唯一调 sseFetch 处);`components/chat/Composer.vue`(Enter/Shift+Enter/输入法组合态/停止接收)
- ✅ task2: `utils/markdown.ts`(marked 18 + dompurify 3.4 + LRU 50);`MessageList/TurnBlock/UserBubble/AssistantMessage/RouteTrail/UsageBadge` 六组件;ChatView 装配 + 空态三示例问句(点击填入不发送)
- ✅ task3: `ErrorNotice.vue` 三形态;`MessageList` 贴底六规则与回底胶囊;Composer 完整化(1s「正在初始化智能体…」、失败保留草稿、流中禁用)
- 依赖新增:`marked@^18.0.13`、`dompurify@^3.4.15`(ARCHITECTURE §1.1 既定选型)
- 验收证据:vue-tsc 零错误、build 通过、vitest 77/77(07 新增 18 条:轮次动作 12 + useChatStream 6);headless Edge 探针 18/18 于真实后端 + 真实模型(流式纯文本→Markdown、用量角标本轮增量、轨迹条默认折叠、断网错误条 + 草稿保留 + 重试不重复插气泡、停止接收灰字提示、零未捕获异常)
- 备注:临时探针与诊断脚本用后已删
- 备注:设计偏差两处(已在 task 文档登记)——① 轨迹条的展开只看 agent/任务/理由,不再单开 SubagentBatchCard(07 任务清单未列该组件,异步派发下也拿不到"已完成");②「停止接收」后不再把文本回填输入框,改由错误条的「重试」承担(回填会诱导重发、污染后端上下文)
- 设计补强:`closeOrDropPlaceholder` —— 空 AI 占位只是加载指示,遇 route/interrupt 事件即收回,不留空气泡(轨迹条自带呼吸点承担"进行中"语义)