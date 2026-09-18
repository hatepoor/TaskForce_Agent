# Task 1: 轮次机制与 useChatStream

> 模块: `07-对话流`
> 前置 task: 无
> 模块依赖: 05 + 06 + 01(task4)
> 状态: ✅ 已完成

## 目标

chat store 的轮次动作实现化 + 领域层组合函数可用,能在控制台观察到完整事件流。

## 前置准备

- [ ] 模块 06 全部验收通过
- [ ] **模块 01 task4(B4/B5)已完成**(B4 未完成也可开发,错误路径按 broken 推断实现)

## 实现步骤

1. **store 动作实现化**(用户誊写,骨架见 ARCHITECTURE §5.2 注释):
   - 文件: `dev/front/src/stores/chat.ts`
   - 详情: `beginTurn`(usageBefore 快照)、`appendToken`(tokenBuf + rAF)、`flushTokens`、`pushRoute`(先 flush,再关当前 assistant 流,push RouteItem)、`setPending`、`attachUsage`(差分)、`endTurn`(空 token 补 note)、`failTurn`
2. **`useChatStream.ts`**(用户誊写,全文见 ARCHITECTURE §4.3):
   - 文件: `dev/front/src/composables/useChatStream.ts`
   - 详情: send / submitAnswer / submitConfirm / abort;isStreaming 早退;onDone 兜底 flush
3. **Composer 最小可用**(本 task 只求能发):textarea + Enter 发送(含中文输入法组合态处理)
   - 文件: `dev/front/src/components/chat/Composer.vue`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/stores/chat.ts` | 修改 | 动作实现化 |
| `dev/front/src/composables/useChatStream.ts` | 新增 | 用户誊写 |
| `dev/front/src/components/chat/Composer.vue` | 新增 | 最小版 |

## 验收标准

- [x] 发一条消息,Vue Devtools 中可见 UserItem → RouteItem → AssistantItem(text 增长)→ usage 差分
- [x] 流式中重复点发送被 store 早退拦截
- [x] abort 后轮次标 aborted,可再发下一条

> 验收说明:三条均由 `stores/chat.test.ts`(12 条轮次动作用例)与 `composables/useChatStream.test.ts`(6 条)覆盖,headless 探针在真实模型下实测流式态与收束。轮次锁定在**发起会话**上(`activeTurnThread`):流中途切走会话,输出仍写回原会话,不污染当前会话。
