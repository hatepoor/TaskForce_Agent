# 挂起交互

> 编号: `08`
> 英文标识: `hitl-interrupt`
> 状态: ✅ 已完成
> 最后更新: 2026-09-16

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [07-对话流](../07-对话流/develop.md) | useChatStream、InterruptItem 占位渲染 | `submitAnswer`、`submitConfirm`、`resolvePending` |
| [01-后端契约改造](../01-后端契约改造/develop.md) task3 | B3 信封 `{kind, text}` 与类型校验 | `interrupt` 帧形状 |

---

## 概述

HITL 两类挂起的完整交互:ask 问询卡(内联输入恢复)与 memory 确认卡(提案预览 + 确认/忽略),含已解决态折叠、400 失效处理、unknown 兜底。

## 功能清单

- **InterruptCard 容器**:按 `kind` 分派 Ask / Memory / unknown 三种卡
- **ask 卡**:问题文本 + 输入框(自动聚焦)→ `POST /chat/answer`
- **memory 卡**:提案引用块预览 + 「忽略」(默认焦点)/「记入记忆」→ `POST /chat/confirm`
- **状态机**:waiting → submitting → resolved(折叠一行)/ failed(400 失效)
- **挂起期约束**:Composer 禁用 + 卡片强制滚入视野

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `InterruptCard.vue`(+Ask/Memory 子卡) | 组件 | 消费 chat store 的 pending 与 InterruptItem |
| 挂起恢复动作 | — | 复用 `useChatStream`,不新增 SSE 调用点 |

## 模块开发规范

### 本模块关键约束

- **恢复端点按 kind 选,绝不混用**(坑 2);unknown 卡不提供任何恢复入口,只给"新开会话"
- memory 卡默认焦点在「忽略」,回车不误触写入
- 提交瞬间即 disabled,堵重复点击(坑 10);400 映射业务提示"该挂起已失效"并刷新会话状态
- 已解决态折叠为单行历史(`✓ 已补充回答 · …` / `⊘ 未记入长期记忆`),不残留交互控件
- 恢复响应也是 SSE 流,新内容追加到**同一轮次**(挂起不结束轮次)
