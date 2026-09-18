# 后端契约改造

> 编号: `01`
> 英文标识: `backend-contract-updates`
> 状态: ⬜ 未开始
> 最后更新: 2026-09-16

## 前置依赖

无(基于已完成的模块 11 API 层)。

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| 无 | 模块 11 的六 router 与 `agent/service.py` 已就绪 | 见 `docs/dev/11-api-finalize/DEV.md` |

---

## 概述

为前端补齐后端缺口:历史消息回填、会话元数据、interrupt 类型信封、SSE 真流式与 error 帧。全部改动不违反全同步红线,不修改 `agent/contracts/` 共享契约。方案细节唯一事实源:[API-CONTRACT.md](../API-CONTRACT.md) §四。

## 功能清单

- **B1 历史消息回填**:新增 `GET /chat/threads/{thread_id}/messages`,读 checkpointer state,过滤内部消息,附挂起态。
- **B2 会话元数据**:新增 `list_session_meta()` 纯 SQL 函数 + `GET /chat/threads/meta` 端点;不改 `list_session_ids()`。
- **B3 interrupt 信封与类型校验**:`_sse_run` 载荷改 `{kind, text}` 对象信封;`/chat/confirm`、`/chat/answer` 加挂起类型校验返 400。
- **B4 SSE 真流式 + error 帧**:`_sse_run` 改 `queue.Queue` + worker 线程;异常发 error 帧;`GraphRecursionError` 打 `taskforce_error` 标记。
- **B5 锁与竞态**:`_get_app()` 加 `threading.Lock`;`UsageTracker.record()` 加锁;`usage.record()` 加 `err is None` 条件。

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `GET /chat/threads/{thread_id}/messages` | HTTP 端点 | `{thread_id, messages, pending_interrupt}` |
| `GET /chat/threads/meta` | HTTP 端点 | `{threads: [{thread_id, last_checkpoint, checkpoints}]}` |
| `interrupt` SSE 帧 | 协议变更 | 数组 → `{kind: "ask"\|"memory"\|"unknown", text}` 对象信封 |
| `error` SSE 帧 | 新增 | `{message, code?}`,`code: "recursion_limit"` |

## 模块开发规范

### 本模块关键约束

- **教学模式硬性分工**:业务代码由 Claude 给完整全文 + 改动点清单,用户亲手誊写;**测试代码(`tests/test_api_history.py` 等)由 Claude 负责编写**。
- 禁止 async/await;`graph.stream` 同步 API;SSE 保持同步 generator + `def` 端点。
- B3/B4 属 API 层帧形状变更,**动手前先在 `docs/dev/ROADMAP.md §7` 登记**。
- 改 `agent/service.py`(recursion 标记)需在模块 01 文档记一笔返回值语义扩展。
- 每个 task 完成后跑对应测试文件 + `uv run pytest -q` 全量回归。

## 设计决策

| 决策项 | 选项 | 最终选择 | 原因 |
|--------|------|----------|------|
| interrupt 帧形状 | 数组外壳加字段 / 对象信封 | 对象信封 `{kind, text}` | 前端未开工无兼容包袱;协议自描述 |
| 真流式实现 | async / Queue+Thread | Queue + worker 线程 | 全同步红线;不触碰图与契约 |
| 会话标题 | 后端生成 / 前端本地 | 前端 localStorage | 列表接口保持轻量,单用户够用 |
