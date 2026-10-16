# 二、端点全表 · Chat 资源

> 一句话: Chat 资源:发起对话与三类挂起恢复(confirm / answer / plan)、线程列表 / 元数据 / 历史回填、任务 peek 与自动汇总、删除会话
> 体系: 前端文档 · API-CONTRACT · 端点分片
> 上游: [README](./README.md)
> 下游: [02-端点-知识库.md](./02-端点-知识库.md)
> 细节见: [手册索引](./README.md)

### 2.1 Chat 资源

#### 2.1.1 `POST /chat` — 发起一轮对话(SSE)

请求体(`ChatRequest`):

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `thread_id` | `string` | 否 | `""` | 会话线程 id。**前端必须自己生成**(格式 `sess-{uuid}`,见 ARCHITECTURE 坑 3:后端列表过滤 `LIKE 'sess-%'`),不要依赖服务端新建——新 id 只出现在流末 `usage` 事件里 |
| `text` | `string` | **是** | — | 用户输入文本 |

```json
{ "thread_id": "sess-a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d", "text": "帮我查一下 WebSocket 和 SSE 的区别" }
```

响应:`text/event-stream`,事件协议见 §三。

错误码:422(`text` 缺失或非字符串)。

#### 2.1.2 `POST /chat/confirm` — memory 确认挂起恢复(SSE)

请求体(`ConfirmRequest`):

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `thread_id` | `string` | **是** | 必填,不接受空串 |
| `approved` | `boolean` | **是** | `true` 写入记忆,`false` 跳过 |

```json
{ "thread_id": "sess-a1b2c3d4", "approved": true }
```

响应:同 `POST /chat` 的 SSE 协议。

错误码:

| 码 | 条件 | detail 原文 |
|---|---|---|
| 400 | 无挂起 | `该会话没有待处理的挂起` |
| 400 | 挂起类型不匹配(B3 落地后,如当前是 ask 挂起却调 confirm) | `挂起类型不匹配:期望 memory,实际 ask` |
| 422 | 缺字段 | — |

#### 2.1.3 `POST /chat/answer` — ask 问询挂起恢复(SSE)

请求体(`AnswerRequest`):

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `thread_id` | `string` | **是** | 必填 |
| `text` | `string` | **是** | 用户自由文本回答 |

```json
{ "thread_id": "sess-a1b2c3d4", "text": "面向浏览器端,要求自动重连" }
```

响应/错误码:同 `/chat/confirm`。

> **语义红线**:两个恢复端点不可混用。B3 落地前后端**不校验挂起类型**——往 `/chat/confirm` 传一个 ask 挂起,后端会把 `approved`(bool)作为 `resume` 送进图,ask 节点拿到 `True` 会把 `"[用户回答]:True"` 写进对话,数据被污染且无一行错误日志。B3 的 `_require_interrupt` 校验是兜底,前端仍必须按 `interrupt.kind` 选端点。

#### 2.1.4 `GET /chat/threads` — 会话线程 id 列表(现有,保持)

响应(`list_session_ids` 直查 `checkpoints` 表 DISTINCT):

```json
{ "threads": ["sess-a1b2c3d4-...", "sess-e5f6a7b8-..."] }
```

**无标题、无更新时间**。前端展示用 §2.1.5 的元数据端点,本端点保留(REPL `/list_session` 依赖,不动)。

#### 2.1.5 `GET /chat/threads/meta` — 会话元数据【待后端落地 B2】

建议实现(`settings/db/checkpointer.py` 追加,纯 SQL 不反序列化 checkpoint;`checkpoint_id` 是 UUIDv6 风格单调递增字符串,`max()` 即最近写入):

```python
def list_session_meta(saver, limit: int = 50) -> list[dict]:
    """会话元数据:最近 checkpoint + 数量。轻量,不碰 msgpack。"""
    with saver.conn.connection() as conn:
        rows = conn.execute(
            "SELECT thread_id, max(checkpoint_id) AS last_cp, count(*) AS n"
            " FROM checkpoints WHERE thread_id LIKE 'sess-%'"
            " GROUP BY thread_id ORDER BY last_cp DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [{"thread_id": r[0], "last_checkpoint": r[1], "checkpoints": r[2]} for r in rows]
```

响应:

```json
{
  "threads": [
    { "thread_id": "sess-a1b2c3d4", "last_checkpoint": "1ef7f0a2-...", "checkpoints": 12 }
  ]
}
```

**标题不在此端点做**:由前端取首条用户输入截 20 字存 localStorage(零后端成本)。

#### 2.1.6 `GET /chat/threads/{thread_id}/messages` — 历史消息回填【待后端落地 B1】

响应:

```json
{
  "thread_id": "sess-a1b2c3d4",
  "messages": [
    { "role": "user", "content": "帮我对比 pgvector 和 FAISS" },
    { "role": "assistant", "content": "两款都是向量检索方案…" }
  ],
  "pending_interrupt": { "kind": "ask", "text": "你的服务端要部署在什么环境?" }
}
```

- `pending_interrupt` 无挂起时为 `null`;有挂起时形状与 SSE `interrupt` 帧**同信封**(`{kind, text}`),前端复用同一套渲染。
- 后端实现要点(详细代码见改造清单 §3.1):读 `graph.get_state(config).values["messages"]`;**过滤内部消息**——`[用户回答]:` 前缀(ask 节点合成)、`子智能体结果已回收` 前缀(fan-in 合成)与 `(系统通知)` 前缀(自动汇总触发语)不输出;ToolMessage/SystemMessage/tool_calls 全部跳过。

#### 2.1.7 `GET /chat/tasks` — 后台任务 peek【2026-09-18 落地】

查询参数 `thread_id`(必填)。响应:

```json
{ "pending": 1, "done": 2 }
```

| 字段 | 说明 |
|---|---|
| `pending` | 该会话未完成的后台任务数;**全批完成的判据是 `pending === 0`** |
| `done` | 已完成但**尚未被汇总轮消费**的结果数(> 0 才值得发起汇总) |

- **非消费**:本端点只读计数,结果仍留给主图在汇总轮里 `drain_done()`(peek 的设计动机就是这个——`has_done` 会看不能拿)。
- 前端用法:派发后按 3s 轮询;`pending === 0 && done > 0` 且当前没有流式轮次时发起 §2.1.8;`pending === 0 && done === 0` 说明结果已被别的轮次消费(用户在完成前先问了),清位收工。

#### 2.1.8 `POST /chat/summary` — 后台任务自动汇总轮(SSE)【2026-09-18 落地】

请求体:

```json
{ "thread_id": "sess-a1b2c3d4" }
```

- 以 `agent.service.AUTO_NOTICE`(`(系统通知)后台子智能体任务已完成,请直接汇总结果。`)作为本轮输入跑 `run_turn`——与 REPL 的自动汇总 watcher 共用同一触发语与同一条业务层,**事件帧与 `/chat` 完全一致**(token/route/usage/error),前端用同一套 handler 消费即可。
- 无待汇总结果时返回 **400**(`该会话没有待汇总的后台任务结果`),防止空转一轮。
- 触发语不进对话记录:历史回填按 `(系统通知)` 前缀过滤(§2.1.6)。
- 语义对齐 REPL:用户轮优先(前端在流式期间不发),结果被消费后不重复汇总。

#### 2.1.9 `POST /chat/plan` — plan 计划确认挂起恢复(SSE)【2026-09-27 落地】

请求体(与 `/chat/answer` 同形):

```json
{ "thread_id": "sess-a1b2c3d4", "text": "y" }
```

- plan_0.1(ADR-0012)的计划确认挂起恢复:`text='y'` 开始执行,其他任意文本取消——与 REPL 回复语义一致。
- 批准后 supervisor 确定性推进:按依赖分批异步派发,本流内先出 route 帧(派发清单),后续结果经 §2.1.7 轮询 + §2.1.8 自动汇总轮回收。
- 挂起类型校验同 `/chat/confirm`(`_require_interrupt(..., "plan")`),无挂起或类型不符返回 **400**。

#### 2.1.10 `DELETE /chat/threads/{thread_id}` — 删除会话【2026-09-27 落地】

响应:

```json
{ "ok": true, "thread_id": "sess-a1b2c3d4" }
```

- 后端语义:PostgresSaver 的 `delete_thread`(checkpoints/checkpoint_blobs/checkpoint_writes 三表)+ `TaskManager.discard`(清该线程任务台账,未消费结果一并丢弃)。
- **400**(`该会话有正在执行的后台任务,完成后再删除`):该线程 `pending > 0` 时拒删——清了台账,跑完的结果无处回收、计划推进悬空。
- **幂等**:不存在的会话(本地新建还没 checkpoint)同样返回 ok,前端无分支差异。
- 前端配合:本地元数据/消息缓存/挂起态同步删除;删当前会话切到剩余最近一个,没有则新建;该会话流式进行中前端先行拒删(不发请求)。
