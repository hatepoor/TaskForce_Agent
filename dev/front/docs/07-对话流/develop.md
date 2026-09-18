# 对话流

> 编号: `07`
> 英文标识: `chat-stream`
> 状态: ✅ 已完成
> 最后更新: 2026-09-16

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [05-SSE传输层](../05-SSE传输层/develop.md) | `sseFetch` 与五事件回调 | `SseHandlers` |
| [06-会话管理](../06-会话管理/develop.md) | `useChatStore` 与会话切换 | `currentThreadId`、`itemsByThread` |
| [01-后端契约改造](../01-后端契约改造/develop.md) task4 | B4 真流式 + error 帧(强烈建议) | token 逐帧、`{"error": {...}}` |

---

## 概述

对话主闭环:发送 → 流式渲染(token/route/usage)→ 错误处理 → 滚动策略。挂起卡的**交互**归模块 08,本模块只负责消息数组中 InterruptItem 的占位渲染与流终止。

## 功能清单

- **轮次机制**:TurnState 生命周期(begin/attachUsage/end/fail)、单飞互斥
- **useChatStream**:领域层组合函数,三入口(send/submitAnswer/submitConfirm)+ abort
- **消息渲染**:UserBubble / AssistantBubble(流式纯文本 → Markdown)/ RouteTrail / UsageBadge
- **性能**:token rAF 缓冲、流式期不解析 Markdown、markdown LRU 缓存
- **错误与状态**:错误条/重试/停止接收、空回答兜底 note、贴底滚动策略

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `useChatStream` | 组合函数 | 唯一调 sseFetch 处;模块 08 的卡片恢复也用它 |
| `MessageList` / `TurnBlock` / `UserBubble` / `AssistantMessage` / `RouteTrail` / `UsageBadge` / `ErrorNotice` / `Composer` | 组件 | ChatView 装配 |
| chat store 动作(实现化) | Pinia | beginTurn~failTurn 由空壳转实现 |

## 模块开发规范

### 本模块关键约束

- token 追加进**非响应式** tokenBuf,rAF 每帧最多刷一次(坑 5)
- `streaming` 期间 pre-wrap 纯文本,结束才 marked(半截语法渲染不出正确结果)
- **单飞轮次**:UI 禁用 + store 早退双守卫;**不自动重试**(坑 4)
- 「停止接收」≠「取消任务」,abort 后留灰色提示(坑 7)
- usage 角标显示**本轮增量**(相邻快照差分),累计值放 tooltip(坑 8)
- 贴底滚动按 UI-DESIGN §6.2 六条规则;Enter 发送必须处理中文输入法组合态(§6.1)
- 一轮结束 token 为空 → 补兜底 note(坑 6)
