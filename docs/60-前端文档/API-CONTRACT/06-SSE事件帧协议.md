# 三、SSE 事件帧协议

> 一句话: SSE 端点范围、帧格式、五类事件载荷(B4 落地后新增 error)、帧解析规则、边界情况与请求超时
> 体系: 前端文档 · API-CONTRACT · 协议分片
> 上游: [README](./README.md)
> 下游: [07-后端改造清单.md](./07-后端改造清单.md)
> 细节见: [手册索引](./README.md)

## 三、SSE 事件帧协议

### 3.1 端点范围

三个端点共用同一套协议,由 `chat.py` 的 `_sse_run()` 统一产出:

- `POST /chat`(text 驱动)
- `POST /chat/confirm`(resume=bool 驱动)
- `POST /chat/answer`(resume=str 驱动)
- `POST /chat/plan`(resume=str 驱动,'y' 执行/其他取消,§2.1.9)

响应头:`Content-Type: text/event-stream`。

### 3.2 帧格式

每一帧严格是:

```
data: {"<事件类型>": <载荷>}\n\n
```

即 **单行 `data:` 前缀 + 一个单键 JSON 对象 + 一个空行**。服务端 `json.dumps(..., ensure_ascii=False)`,**中文不转义**,UTF-8 明文。

**关键实现细节(现状)**:`gen()` 先跑完整个 `run_turn`(同步阻塞、回调把帧 append 进 `events` 列表),最后 `yield from events` 一次性吐出。**首字节延迟等于整轮执行时间**——打字机效果在"本轮结束"后才开始播放。B4 改造(Queue + worker 线程真流式)落地前,loading 指示器必须在 `fetch` 发起后立即显示;落地后前端解析器零改动(本就是逐帧消费设计)。

### 3.3 五类事件(B4 落地后新增 error)

#### token — 增量文本

```json
{"token": "WebSocket "}
```

| 属性 | 值 |
|---|---|
| 载荷类型 | `string` |
| 语义 | 追加到当前回答的**增量**片段,不是完整句子 |
| 来源 | `run_turn(on_token=...)`,只对 `langgraph_node in {"answer","ask"}` 的 `AIMessageChunk` 触发 |
| 数量/顺序 | 0..N,与其他事件**交错**(route 可出现在 token 之间) |

**渲染规则**:必须字符串累加(`current.content += payload.token`),不能 replace。

#### route — 路由轨迹

```json
{"route": {"next": "dispatch", "question": null, "tasks": [{"agent": "research", "task": "调研 WebSocket 与 SSE 的差异", "reason": "需要联网获取最新资料"}, {"agent": "retriever", "task": "从知识库检索已有笔记", "reason": "本地知识库可能有相关记录"}]}}
```

载荷即 `Route` 契约的 dict 形式:

| 字段 | 类型 | 说明 |
|---|---|---|
| `next` | `"answer"` \| `"ask"` | `"memory"` \| `"dispatch"` \| `"plan"` | 下一跳决策(plan_0.1:进入计划起草) |
| `question` | `string \| null` | `next=ask` 时才有值 |
| `tasks` | `Task[] \| null` | `next=dispatch` 时才有值;Task = `{agent: "retriever"\|"research"\|"executor", task, reason}` |

一轮内**可多帧**,通常在 token 之前。渲染成可折叠"执行轨迹"面板,`question`/`tasks` 判空。

**注意**:`route` 事件**不含子智能体 ResultSummary**。异步派发架构下子任务结果在**下一轮**回灌,本流内无法得知"已完成"——**2026-09-18 起由轮询补上**:派发后按 §2.1.7 轮询 `GET /chat/tasks`,全批完成即发起 §2.1.8 的自动汇总轮(汇总正文经 token 帧流入同一 store,用户无需再问)。原"批次卡只显示派发清单"的开放项已落地为自动汇总,不再需要批次卡。

#### interrupt — 挂起载荷【B3 落地后:对象信封】

**落地后形状(本文档采用)**:

```json
{"interrupt": {"kind": "ask", "text": "你的服务端要部署在什么环境?"}}
```

```json
{"interrupt": {"kind": "memory", "text": "用户偏好中文回复"}}
```

```json
{"interrupt": {"kind": "plan", "text": "## 调研计划\n- ☐ s1 …"}}
```

| 字段 | 说明 |
|---|---|
| `kind` | `"ask"`(ask 节点问询,恢复走 `POST /chat/answer`)\| `"memory"`(memory 写入提案,恢复走 `POST /chat/confirm`)\| `"plan"`(调研计划确认,恢复走 `POST /chat/plan`,§2.1.9)\| `"unknown"`(兜底,禁用输入) |
| `text` | 问题文本 / 提案原文 / 计划快照(Markdown 列表) |

后端实现(`_interrupt_envelope`,改动局限 `chat.py` 一个函数):

```python
def _interrupt_envelope(updates) -> dict:
    """规范化成自描述信封:question/proposal 是不同 key,前端靠 key 猜类型,
    猜错不会报错且会把 approved=True 当答案写进对话。补显式 kind。"""
    first = updates[0].value if updates else {}
    if "proposal" in first:
        return {"kind": "memory", "text": first["proposal"]}
    if "question" in first:
        return {"kind": "ask", "text": first["question"]}
    return {"kind": "unknown", "text": str(first)}
```

**配套加固**:`_require_interrupt(graph, config, expect)` 校验挂起类型,不符 400(两个恢复端点本来就有一次 `get_state`,替换而非新增,无性能损失)。

**中断后的状态**:图保持挂起,`thread_id` 不变,流关闭。**挂起轮没有 `usage` 帧,是正常的,不是错误**。挂起态经 B1 的 `pending_interrupt` 字段可在刷新后恢复。

#### usage — 收尾统计

```json
{"usage": {"thread_id": "sess-a1b2c3d4", "calls": 3, "input_tokens": 4821, "output_tokens": 763}}
```

**重要**:`calls`/`input_tokens`/`output_tokens` 来自 `UsageTracker` **进程内单例**,是跨会话累计值,**不是本轮消耗**。前端做相邻快照差分显示本轮值。

**`usage` 只在 `final` 是 AIMessage 时才发**,以下情况**不会**有:① 本轮挂起;② `GraphRecursionError` 兜底路径(B4 落地前该路径连 token 都没有,表现为空回答);③ 其他异常(连接直接断)。**前端不能把"收到 usage"当流结束信号,必须以连接关闭为准。**

#### error — 异常帧【待后端落地 B4】

```json
{"error": {"message": "ValueError: ...", "code": "recursion_limit"}}
```

B4 落地后:`gen()` 内 try/except 包住 `run_turn`,异常发 error 帧后正常关流;`GraphRecursionError` 兜底消息打 `taskforce_error=recursion_limit` 标记,转为 `{"code": "recursion_limit"}` 的 error 帧。落地前,前端按"连接关闭但无 usage 且无 interrupt"推断为 `broken` 态。

### 3.4 帧解析规则

用 `fetch` + `ReadableStream`,**不要用 `EventSource`**(只支持 GET,三个端点都是 POST)。完整实现见 ARCHITECTURE.md §4.2 `sse.ts`,关键点:

1. **必须 `TextDecoder` 逐块解码且 `{stream: true}`**——中文一个字 3 字节,网络分片可能劈开它,朴素解码出乱码(本项目输出全中文,必踩)。
. **帧按 `\n\n` 切分,残帧留在 buffer**;代理可能把 `\n\n` 变成 `\r\n\r\n`,切分前先归一化 CRLF。
3. **`JSON.parse` 单帧 try/catch 隔离**,一帧坏了丢弃计数,不中断整条流。
4. **非 2xx 时 body 是普通 JSON 不是 SSE**(如 400 挂起校验在返回 StreamingResponse 之前抛出),必须按 `res.ok` 分支,不能直接进流解析。

### 3.5 边界情况

| 场景 | 后端行为 | 客户端表现与应对 |
|---|---|---|
| **半帧** | 无特殊处理 | buffer + `indexOf('\n\n')` 自动处理 |
| **多字节字符被切断** | 无特殊处理 | `TextDecoder({stream:true})` 自动处理 |
| **用户中止(AbortController)** | 后端同步 generator 继续跑完(无法感知断开),**服务端任务不会被取消** | `AbortError` 捕获后保留已渲染文本,标记"已停止接收;服务端可能仍完成了部分动作" |
| **网络断开/后端崩溃** | 无 error 事件,连接直接关闭(B4 前) | 检查"是否收到过 usage/interrupt",都没有则判 `broken`,提示并允许重试 |
| **本轮挂起** | 发完 interrupt 帧后正常关流 | 进挂起 UI;**无 usage 帧是正常的** |
| **GraphRecursionError** | 返回常量 AIMessage,不走 token 流(B4 前) | 空回答 + 无 usage;B4 后转 error 帧 |
| **恢复端点 400** | 返回 StreamingResponse **之前**抛 HTTPException | 响应是普通 JSON;按业务提示(挂起可能已在别处恢复),清挂起卡 |

**推荐的流状态机**:

```
idle → connecting → streaming ─┬→ completed   (连接关闭且有 token 或 usage)
                               ├→ suspended   (收到 interrupt 帧)
                               ├→ aborted     (AbortError)
                               └→ broken/failed(连接关闭:无 usage、无 interrupt;B4 后由 error 帧确定为 failed)
```

### 3.6 请求超时设置

| 端点 | 建议超时 | 理由 |
|---|---|---|
| `/chat*`(SSE) | **不设总超时**;静默看门狗 120s(每收到任意帧重置) | 首轮要惰性装配图 + MCP,可能几十秒;长回答含联网调研更久 |
| `/mcp/servers/{name}/test` | 30s | 后端内部 timeout 10s,留余量 |
| `/knowledge/upload` | 120s | 20MB 文件 + embedding |
| 其他 | 10~15s | 普通 CRUD |
