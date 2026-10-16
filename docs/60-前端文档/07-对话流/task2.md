# Task 2: 消息渲染组件

> 模块: `07-对话流`
> 前置 task: task1
> 模块依赖: 05 + 06
> 状态: ✅ 已完成

## 目标

ChatView 装配完整消息列表,四类 ChatItem 正确渲染,流式与结束两态切换。

## 前置准备

- [ ] task1 已完成并通过验收
- [ ] UI-DESIGN §3.1/§3.2 已通读

## 实现步骤

1. **`src/utils/markdown.ts`**:marked + dompurify 封装 + LRU 缓存(用户誊写)
   - 文件: `dev/front/src/utils/markdown.ts`
2. **消息组件**(用户誊写,视觉参照 UI-DESIGN §3.2):
   - 文件: `dev/front/src/components/chat/` 下 `MessageList.vue`、`TurnBlock.vue`、`UserBubble.vue`、`AssistantMessage.vue`(含 MarkdownBody)、`RouteTrail.vue`、`UsageBadge.vue`
   - 详情: AssistantMessage 两态(streaming → pre-wrap 纯文本 + 光标;结束 → Markdown);RouteTrail 聚合本轮 route 事件、默认折叠、`next` 中文映射、agent 身份色圆点
3. **ChatView 装配** + 空态(EmptyState 三示例问句点击填入)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/utils/markdown.ts` | 新增 | |
| `dev/front/src/components/chat/*.vue`(6 个) | 新增 | 用户誊写 |
| `dev/front/src/views/ChatView.vue` | 修改 | 装配 |

## 验收标准

- [x] 逐字流式可见(B4 后),结束后光标消失、usage 角标显示本轮增量
- [x] route 轨迹默认一行、可展开,身份色正确
- [x] Markdown(代码块/表格)在回答结束后正确渲染,流式期间不解析
- [x] 长回答渲染不卡顿(rAF 生效)

> 验收说明:探针实测「流式期为 pre-wrap 纯文本(带光标)→ 结束后转 Markdown」的切换、用量角标为**本轮增量**、轨迹条默认折叠(aria-expanded=false)。
>
> 三处偏差:① **轨迹条的展开态即"派发清单"**(agent 身份色 + 任务 + 理由),不再单开 `SubagentBatchCard`——07 任务清单未列该组件,且异步派发架构下流内拿不到"已完成",单开卡只能显示"已派发",信息与轨迹条重复;② 展开态点击断言并入模块 08 探针(与挂起卡同批实测);③ 长回答的流畅度为**实现 + 定性观察**(rAF 批量写入 + 流式期不解析 Markdown),未做量化帧率测量。
>
> `MessageList` 还补了一条设计未写明的规则:空 AI 占位遇到 route/interrupt 事件即收回(`closeOrDropPlaceholder`),避免轨迹条前留一条空气泡。
