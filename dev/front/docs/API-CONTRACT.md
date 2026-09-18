# TaskForce 前端 API 契约文档

**版本**:v1.1 · **对应后端**:`src/api/main.py` + `src/api/routers/*`(模块 11)· **目标读者**:`dev/front/` 前端工程(Vue 3 + Vite)

> v1.1 修订:① 开发期代理统一为 `/api` 前缀 + rewrite(与 ARCHITECTURE.md 对齐);② interrupt 帧形状按全量设计裁决改为**对象信封**(见 §3.3 与 §四 B3);③ 新端点 `GET /chat/threads/{thread_id}/messages`、`GET /chat/threads/meta` 按 B1/B2 改造方案纳入契约(标注【待后端落地】)。
>
> 本文档所有字段名、示例值均取自后端真实代码,未做任何虚构。凡标注「**字段未在代码中确认**」的,前端不得依赖。

---

## 一、基础约定

### 1.1 BaseURL 与开发期代理

后端无全局前缀,`main.py` 直接把六个 router 挂在应用根上。实际路径为 `/chat`、`/health`、`/knowledge`、`/memory`、`/skills`、`/mcp/servers`。

**BaseURL 由环境变量收口**:`src/api/http.ts` 中 `const BASE = import.meta.env.VITE_API_BASE ?? '/api'`,全项目只此一处拼接,其余模块一律写 `/chat` 这类后端真实路径。

- 开发期(`.env.development`):`VITE_API_BASE=/api`,Vite proxy 负责剥掉前缀;
- 生产期(`.env.production`):`VITE_API_BASE=`(空,同源直连,FastAPI StaticFiles 挂载构建产物)。

```ts
// dev/front/vite.config.ts
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // 后端路由无 /api 前缀,proxy 只负责剥掉它
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
        // SSE 必须防代理层聚合缓冲,否则事件会被攒住一次性下发
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache, no-transform'
          })
        },
      },
    },
  },
})
```

前端代码里所有请求写相对路径(fetch(`${BASE}/chat`))。**不要**在生产构建里保留 `VITE_API_BASE=/api`——后端没有 `/api` 前缀,会全线 404。

> **注意 SSE 与代理**:Vite proxy 基于 http-proxy,默认透传流式响应,但前端 `fetch` 侧**绝不能**经过任何自动 JSON 解析或响应缓冲。
>
> **2026-09-18 更新(端口固定)**:后端端口**固定 `8010`,不再按环境改**(`vite.config.ts` 代理目标、`.env.development`、`api/main.py` 默认值三处一致)。
> 本机 8000 是沙箱 SSH 隧道(`SANDBOX_URL` 指向它),指过去会把前端请求打到沙箱服务上;8010 被占用时先停掉占用进程再起,而不是换端口。上面代码块里的 `target` 以实际 `vite.config.ts` 为准。

### 1.2 统一前缀:建议不改

**结论:保持现状,不加 `/api` 后端前缀。** 理由:六个 router 的 prefix 已在各 `APIRouter(prefix=...)` 中,改全局前缀会碰到模块 11 已验收的代码,收益仅是"好看";Vite proxy 单前缀转发(§1.1)已解决开发期问题;生产同源直连连前缀都不需要。前缀收口落在前端 `VITE_API_BASE` 一个变量上。

### 1.3 错误响应形状

FastAPI 默认 `HTTPException` 序列化为:

```json
{ "detail": "该会话没有待处理的挂起" }
```

Pydantic 请求体校验失败(422)的 `detail` 是**数组**,形状与上面不同:

```json
{
  "detail": [
    { "type": "missing", "loc": ["body", "text"], "msg": "Field required", "input": {}, "url": "https://errors.pydantic.dev/2.5/v/missing" }
  ]
}
```

前端必须写一个统一的错误归一化函数:

```js
// detail 可能是 string 或 object[],统一抽成字符串
function errText(payload, fallback = '请求失败') {
  const d = payload?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map(x => x.msg || JSON.stringify(x)).join('; ')
  return fallback
}
```

**通用错误码语义**

| 状态码 | 触发场景(代码依据) | 前端处理 |
|---|---|---|
| 400 | `/chat/confirm`、`/chat/answer` 无挂起或**挂起类型不匹配**(B3 落地后);`/knowledge/upload` 超 20MB | 提示 `detail`,并刷新挂起状态 |
| 404 | `/mcp/servers/{name}` 删除/测试时服务器不存在;B7 落地后 knowledge 删除不存在 | 提示后刷新列表 |
| 422 | 请求体 schema 不符;`/mcp/servers` 配置 discriminator 解析失败(后端显式抛 422);B8 落地后 MCP name 非法 | 表单字段级报错 |
| 500 | 未捕获异常(如 RAGStore 删除不存在的 doc_id 会抛 `ValueError`,**B7 落地前会变 500**) | 通用错误提示 |

> **已知缺口(B 落地前)**:`DELETE /knowledge/{doc_id}` 删除不存在的文档时,`RAGStore().delete()` 抛 `ValueError(f"文档不存在:{doc_id}")`,router 未捕获,前端收到 500 而非 404。前端过渡处理:删除前不做存在性校验,把 500 也当作"该文档可能已不存在"提示并刷新列表。

### 1.4 请求/响应通用约定

- 全部端点均为**同步 `def`**,无 async。SSE 用同步 generator + `StreamingResponse`,媒体类型 `text/event-stream`。
- 请求体一律 `application/json`,**唯一例外**是 `POST /knowledge/upload`,用 `multipart/form-data`。
- 响应体一律 JSON,**唯一例外**是三个 SSE 端点。
- 后端无任何认证、无 CSRF token、无 rate limit——单用户本地工具,前端不要实现 token 逻辑。
- 无分页:所有列表端点一次性返回全量(`/memory` 硬编码 `limit=100`)。

---

## 二、端点全表(按资源分组)

### 2.0 总览

| # | 方法 | 路径 | 说明 | 响应类型 |
|---|---|---|---|---|
| 1 | POST | `/chat` | 发起一轮对话(SSE) | `text/event-stream` |
| 2 | POST | `/chat/confirm` | memory 确认挂起恢复(SSE) | `text/event-stream` |
| 3 | POST | `/chat/answer` | ask 问询挂起恢复(SSE) | `text/event-stream` |
| 4 | GET | `/chat/threads` | 会话线程 id 列表 | JSON |
| 5 | GET | `/chat/threads/meta` | 会话元数据列表【待后端落地 B2】 | JSON |
| 6 | GET | `/chat/threads/{thread_id}/messages` | 会话历史消息回填【待后端落地 B1】 | JSON |
| 7 | GET | `/chat/tasks?thread_id=` | 后台任务 peek(非消费,自动汇总轮询用)【2026-09-18 落地】 | JSON |
| 8 | POST | `/chat/summary` | 后台任务全批完成后的自动汇总轮(SSE)【2026-09-18 落地】 | `text/event-stream` |
| 9 | GET | `/models/config` | 模型配置读取(设置页,api_key 掩码回显)【2026-09-18 落地】 | JSON |
| 10 | PUT | `/models/config` | 模型配置保存(缺项不动,重启后端生效)【2026-09-18 落地】 | JSON |
| 11 | GET | `/health` | 存活 + DB + 沙箱自检 | JSON |
| 12 | GET | `/knowledge` | 文档列表 | JSON |
| 13 | POST | `/knowledge/upload` | 上传文档 | JSON |
| 14 | DELETE | `/knowledge/{doc_id}` | 删除文档 | JSON |
| 15 | GET | `/memory` | 长期记忆列表 | JSON |
| 16 | DELETE | `/memory/{key}` | 删除单条记忆 | JSON |
| 17 | GET | `/skills` | 技能元数据列表 | JSON |
| 18 | GET | `/mcp/servers` | MCP 服务器配置列表 | JSON |
| 19 | POST | `/mcp/servers` | 新增/覆盖服务器(B6 落地后 name 进 body) | JSON |
| 20 | DELETE | `/mcp/servers/{name}` | 删除服务器 | JSON |
| 21 | POST | `/mcp/servers/{name}/test` | 单服务器连通性探测 | JSON |

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

### 2.2 Health 资源

#### `GET /health`

正常:`{ "status": "ok", "db": "ok", "sandbox": "ok" }`

DB 异常(注意 `db` 内嵌了完整异常文本):`{ "status": "degraded", "db": "error: 连接串拒绝连接", "sandbox": "ok" }`

沙箱不可达:`{ "status": "ok", "db": "ok", "sandbox": "unreachable" }`

| 字段 | 可能值 |
|---|---|
| `status` | `"ok"` \| `"degraded"` |
| `db` | `"ok"` \| `"error: {异常信息}"` |
| `sandbox` | `"unknown"` \| `"ok"` \| `sandbox_health()` 的 error 文本 \| `"unreachable"` |

**前端注意**:`sandbox` 值域不封闭,应当"非 `ok` 即视为异常",不要精确匹配其他值。此端点从不抛 500。

### 2.3 Knowledge 资源

#### `GET /knowledge` — 文档列表(按 `created_at` 升序)

```json
{
  "docs": [
    { "doc_id": "3f2a9c1b8e4d4f6a9b0c1d2e3f4a5b6c", "filename": "LangGraph 官方指南.pdf", "created_at": "2026-09-16T08:31:22.145+00:00", "chunks": 42 }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `doc_id` | `string` | 32 位 hex(`uuid4().hex`) |
| `filename` | `string` | 上传时的原始文件名 |
| `created_at` | `string` | ISO 8601,带时区偏移 |
| `chunks` | `number` | 该文档切块数 |

#### `POST /knowledge/upload` — 上传文档

请求:`multipart/form-data`,字段名必须是 `file`(**单文件**;多选由前端拆成串行 N 个请求)。**不要手动设 Content-Type**,让浏览器带 boundary。

```js
const fd = new FormData()
fd.append('file', file)
await fetch(`${BASE}/knowledge/upload`, { method: 'POST', body: fd })
```

成功响应(`doc_id` 在**重复内容上传时复用已有 id**):

```json
{ "doc_id": "3f2a9c1b…", "created": true, "name": "LangGraph 官方指南.pdf" }
```

**前端必须处理 `created: false`**:不是错误,是内容判重命中(解析后文本 SHA-256 相同),UI 提示"该文档已存在,已复用"。

错误码:

| 码 | 条件 | detail 原文 |
|---|---|---|
| 400 | `len(content) > 20MB` | `文件超过 20MB 上限` |
| 400 | 解析失败/切块后无内容(B7 落地后;落地前为 500) | 异常原文 |
| 500 | 同上(B7 落地前) | — |

前端应在发起请求前用 `file.size > 20 * 1024 * 1024` 本地拦截。

#### `DELETE /knowledge/{doc_id}` — 删除文档

成功:`{ "ok": true, "doc_id": "3f2a9c1b…" }`

错误码:B7 落地后不存在返 404(`文档不存在:{doc_id}`);落地前为 500,前端按 §1.3 过渡处理。

### 2.4 Memory 资源

#### `GET /memory` — 长期记忆列表(按 `created_at` 降序,固定 limit=100)

```json
{
  "items": [
    { "key": "mem-7c1f2a3b", "content": "用户偏好中文回复", "source": "confirmed", "created_at": "2026-09-16T09:02:11.884+00:00" },
    { "key": "mem-1a2b3c4d", "content": "用户在做 LangGraph 练手项目 TaskForce", "source": "explicit", "created_at": "2026-09-16T08:55:03.201+00:00" }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `key` | `string` | Store 主键 |
| `content` | `string` | 一句话原子事实,缺失时为 `""` |
| `source` | `string` | `"explicit"` \| `"confirmed"`;缺失时为 `""` |
| `created_at` | `string` | ISO 8601;缺失时为 `""` |

#### `DELETE /memory/{key}` — 删除单条记忆

成功:`{ "ok": true, "key": "mem-7c1f2a3b" }`

**注意**:`store.delete()` 对不存在的 key 幂等,删不存在的 key 也返回 200。key 可能含中文/斜杠,必须 `encodeURIComponent`。

### 2.5 Skills 资源

#### `GET /skills` — 技能元数据列表

```json
{
  "skills": [
    { "name": "pdf-extract", "description": "从 PDF 中提取结构化文本与表格", "dir": "F:\\project\\my_pro_3\\skills\\pdf-extract" }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | `string` | 已通过 `^[a-z0-9-]+$` 校验,可安全用作 key |
| `description` | `string` | frontmatter 的 description,可能为 `""` |
| `dir` | `string` | **服务端本地绝对路径**;仅调试展示,不做正式 UI 元素 |

**前端注意**:本接口每次现扫目录,但智能体侧 `_skills_meta()` 是 `lru_cache(maxsize=1)`——新增技能目录后**本接口立刻可见,但智能体路由仍用旧缓存**,需重启后端。技能页加一行提示:"技能变更需重启后端生效"。

### 2.6 MCP 资源

#### `GET /mcp/servers` — 服务器列表(name → config 字典)

```json
{
  "servers": {
    "context7": { "transport": "stdio", "command": "npx", "args": ["-y", "@upstash/context7-mcp"], "env": {} },
    "docs-langchain": { "transport": "http", "url": "https://docs.langchain.com/mcp", "headers": {} }
  }
}
```

后端 `model_dump(exclude_none=True)`,**未设置的字段不会出现**(`args`/`env`/`headers` 可能整个缺失),渲染时全部按可选处理。

| transport | 字段 |
|---|---|
| `"stdio"` | `command: string`(必填)、`args: string[]`、`env: Record<string,string>` |
| `"http"` | `url: string`(必填)、`headers: Record<string,string>` |

错误码:配置文件 JSON 损坏时 `MCPConfigError` 未捕获 → 500。

#### `POST /mcp/servers` — 新增/覆盖服务器

**B6 落地前(现状,前端必须按此实现)**:参数在 **query string** 里,body 直接是 config 对象(FastAPI 对"标量参数 + 单一 dict 体"的默认行为):

```http
POST /mcp/servers?name=github-mcp
Content-Type: application/json

{ "transport": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": { "GITHUB_TOKEN": "ghp_xxx" } }
```

```js
await fetch(`${BASE}/mcp/servers?name=${encodeURIComponent(name)}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(config),
})
```

成功:`{ "ok": true, "name": "github-mcp" }`。**同名会静默覆盖**,前端应做二次确认。

错误码:

| 码 | 条件 | detail |
|---|---|---|
| 422 | `TypeAdapter(MCPServerConfig)` 解析失败(如 `transport` 缺失/非法) | `配置无效:{原始 pydantic 异常}` |
| 500 | `name` 不匹配 `^[a-z0-9_-]+$`(B8 落地前 `_check_name` 未捕获) | — |

前端做名称/格式校验比依赖后端更稳。

#### `DELETE /mcp/servers/{name}` — 删除服务器

成功:`{ "ok": true, "name": "github-mcp" }`。不存在返 404(`服务器 {name} 不存在`)。

#### `POST /mcp/servers/{name}/test` — 连通性探测

请求体:无。后端最长阻塞约 10 秒,前端必须单独给超时/loading 态。

探测到工具:

```json
{ "ok": true, "name": "context7", "tools": ["resolve-library-id", "get-library-docs"] }
```

探测失败(降级,不抛):`{ "ok": false, "name": "context7", "tools": [] }`。**`ok:false` 是正常业务返回,不是异常,UI 显示"未连通"而非红色报错。**

`tools` 形状 B8 落地前未确定(可能是对象数组),前端防御式渲染:

```js
const label = typeof t === 'string' ? t : (t?.name ?? JSON.stringify(t))
```

错误码:404(服务器不存在)。

---

### 2.7 Models 资源(设置页"模型"节)【2026-09-18 落地】

六项可配:主模型与 Embedding 的 `base_url` / `api_key` / 模型名,均走 **OpenAI 兼容协议**(对话 `/chat/completions`、向量 `/embeddings`)。
覆盖表落盘 `.taskforce/model_config.json`(gitignore 已含),**`.env` 是默认值来源,覆盖表只记改动项**;保存后**重启后端生效**(进程启动时读一次)。

#### 2.7.1 `GET /models/config` — 读取模型配置

```json
{
  "config": {
    "llm_base_url": "https://api.deepseek.com",
    "llm_api_key": "sk-c****1c1a",
    "llm_model": "deepseek-flash",
    "embedding_base_url": "https://open.bigmodel.cn/api/paas/v4",
    "embedding_api_key": "ab72****Z8yf",
    "embedding_model": "embedding-3"
  },
  "overridden": ["llm_model"],
  "restart_required": true
}
```

- `config` 是 **`.env` + 覆盖表**(= **重启后**的生效值),不是进程里正在跑的那份——表单编辑的应是"已保存的配置",给运行中旧值会把刚填的内容盖回输入框;两者是否一致由 `restart_required` 单独提示。
- **`api_key` 只回掩码**(前后各 4 位,短值全掩),原文不出网关。
- `overridden`:当前由覆盖表接管的字段(界面打"已覆盖"标)。

#### 2.7.2 `PUT /models/config` — 保存模型配置

请求体**六项全可选,缺项 = 不动**(只发改动项):

```json
{ "llm_model": "doubao-seed-1-6" }
```

| 提交内容 | 语义 |
|---|---|
| 字段缺失 / `null` | **不动**(保留原覆盖;未覆盖的继续走 `.env`) |
| `""` | 清除该项覆盖,回落 `.env` |
| 非空值 | 写入覆盖(去首尾空白) |
| `api_key` 传回掩码 | 保持不动(前端拿不到原文,原样回传不该冲掉真 key) |

- `base_url` 非空时必须 `http(s)://` 开头,否则 **400**(不落盘);空对象提交 = 200 且无改动。
- 响应体与 §2.7.1 相同(保存后的快照)。
- 前端"恢复 .env 默认" = 清空该组三项后提交(即发三个空串),只影响该组。

## 三、SSE 事件帧协议

### 3.1 端点范围

三个端点共用同一套协议,由 `chat.py` 的 `_sse_run()` 统一产出:

- `POST /chat`(text 驱动)
- `POST /chat/confirm`(resume=bool 驱动)
- `POST /chat/answer`(resume=str 驱动)

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
| `next` | `"answer"` \| `"ask"` | `"memory"` \| `"dispatch"` | 下一跳决策 |
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

| 字段 | 说明 |
|---|---|
| `kind` | `"ask"`(ask 节点问询,恢复走 `POST /chat/answer`)\| `"memory"`(memory 写入提案,恢复走 `POST /chat/confirm`)\| `"unknown"`(兜底,禁用输入) |
| `text` | 问题文本 / 提案原文 |

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

---

## 四、后端改造清单(定稿)

> 与全量设计 README 的三批次对应;此处保留详细方案。所有建议**不违反全同步红线**,**不改 `agent/contracts/`**。

### B1【高】历史消息回填端点

见 §2.1.6 契约。实现追加在 `api/routers/chat.py`:

```python
@router.get("/threads/{thread_id}/messages")
def thread_messages(thread_id: str):
    graph, _cp, _usage = _get_app()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    msgs = (state.values or {}).get("messages") or []
    out = []
    for m in msgs:
        if isinstance(m, HumanMessage):
            c = m.content or ""
            if c.startswith("[用户回答]:") or c.startswith("子智能体结果已回收"):
                continue          # 过滤 ask 合成回复与 fan-in 合成消息(与 memory 节点 _last_user_text 同规则)
            out.append({"role": "user", "content": c})
        elif isinstance(m, AIMessage):
            if m.content:
                out.append({"role": "assistant", "content": m.content})
    ints = getattr(state, "interrupts", None) or []
    v = ints[0].value if ints else {}
    pending = None
    if v:
        pending = ({"kind": "memory", "text": v["proposal"]} if "proposal" in v
                   else {"kind": "ask", "text": v["question"]} if "question" in v
                   else {"kind": "unknown", "text": str(v)})
    return {"thread_id": thread_id, "messages": out, "pending_interrupt": pending}
```

影响面:新增只读端点,零改动现有路径;`graph.get_state` 在 confirm/answer 已有先例。**ROADMAP §7 需登记此端点。**

### B2【高】会话元数据端点

见 §2.1.5。**不改 `list_session_ids()`**(REPL 依赖其行为,且它刻意避免反序列化 checkpoint)。若需真实时间戳,可测 `checkpoints` 表的 JSONB `(checkpoint::json->>'ts')::timestamptz` 后再定;`max(checkpoint_id)` 排序已可用且零反序列化。

### B3【高,最高优先级】interrupt 信封 + 类型校验

现状两类挂起产生**不同 key** 的载荷(ask → `{"question":...}`,memory → `{"proposal":...}`),前端只能靠 key 存在性猜类型,而恢复端点不校验类型——**猜错会静默污染数据**(`[用户回答]:True` 写进对话,无一行错误日志)。

方案:§3.3 的 `_interrupt_envelope` + `_require_interrupt` 两段代码,均改动局限 `chat.py`。CLI REPL 不经过 `_sse_run`,零影响。**ROADMAP §7 登记(API 层帧形状变更:数组 → 对象信封)。**

### B4【中】SSE 真流式 + error 帧

当前 `gen()` 攒完再吐:首字节延迟 = 整轮耗时、打字机是快放录像、异常无信号、超时易误杀。方案:`queue.Queue` + worker 线程(**不引入 async**,`graph.stream` 仍同步,gen 仍是同步 generator,FastAPI 端点仍 `def`):

```python
import queue, threading

def gen():
    q: queue.Queue = queue.Queue()
    _DONE = object()

    def emit(etype, data):
        q.put(f"data: {json.dumps({etype: data}, ensure_ascii=False)}\n\n")

    def worker():
        try:
            final = run_turn(graph, config, text=text, resume=resume,
                             on_token=lambda t: emit("token", t),
                             on_route=lambda r: emit("route", r),
                             on_interrupt=lambda u: emit("interrupt", _interrupt_envelope(u)))
            if err标记 := (final is not None and isinstance(final, AIMessage)
                           and final.additional_kwargs.get("taskforce_error")):
                emit("error", {"message": final.content, "code": err标记})
            elif final is not None and isinstance(final, AIMessage):
                usage.record(final)
                emit("usage", {...})
        except Exception as e:
            emit("error", {"message": f"{type(e).__name__}: {e}"})
        finally:
            q.put(_DONE)

    threading.Thread(target=worker, daemon=True).start()
    while (item := q.get()) is not _DONE:
        yield item
```

配套:`agent/service.py` 的 `GraphRecursionError` 分支给返回的 AIMessage 加 `additional_kwargs={"taskforce_error": "recursion_limit"}`(`additional_kwargs` 是 LangChain 标准字段,不算改共享契约,但 `run_turn` 返回值语义有扩展,在 01 模块文档记一笔);`usage.record()` 加 `err is None` 条件;`_get_app()` 加 `threading.Lock`。

风险点:① 客户端 abort 后 worker 仍跑完(daemon 线程,单用户场景可接受,docstring 写明);② checkpointer 是 ConnectionPool(线程安全),图内 Send 各自取连接的纪律不变,但需实测;③ `UsageTracker` 加 `threading.Lock`(两行)。

### B5【中】锁与竞态收尾

`_get_app()` 惰性单例 `if _app is None` 非原子,用户快速连点理论上 build 两次图 → 加 `threading.Lock`(两行);`UsageTracker.record()` 加锁。随 B4 一起做。

### B6~B8【低】小修

- **B6**:`POST /mcp/servers` 改显式 Pydantic 模型(name 进 body)。破坏性变更但前端未开工,现在成本为零。影响面仅 `mcp.py`。
- **B7**:`knowledge.py` 删除不存在 → 404(`except ValueError as e: raise HTTPException(404, str(e))`);upload 解析失败/切块为空 → 400。
- **B8**:`mcp.py` 的 `_check_name` 抛错转 422;`test` 端点 tools 归一化 `tools = [t if isinstance(t, str) else getattr(t, "name", str(t)) for t in found]`。

### 不改(前端兜底)

`/health` sandbox 值域(非 ok 即异常);`/memory` 100 条上限(UI 不承诺"全部");usage 进程累计(前端差分)。

---

## 五、前端落地建议

### 5.1 文件组织

```
dev/front/src/
├── api/
│   ├── http.ts          # fetch 封装 + BASE 拼接 + errText 错误归一化 + ApiError
│   ├── sse.ts           # sseFetch 统一帧解析(纯函数,可单测)
│   └── resources/       # chat.ts / knowledge.ts / memory.ts / skills.ts / mcp.ts / health.ts
├── stores/              # Pinia:仅 chat(会话+消息+挂起)与 ui(toast);管理页局部状态
├── composables/         # useChatStream(唯一调 sseFetch 处)/ useAsync / useLocalStore / useClipboard
├── types/               # 后端契约手工镜像(以本文档为准)
├── views/               # ChatView / KnowledgeView / MemoryView / SettingsView
└── components/
    ├── chat/            # MessageList / RouteTrail / SubagentBatchCard / InterruptCard(Ask/Memory)/ Composer / UsageBadge
    ├── common/          # AppButton / AppInput / EmptyState / Spinner / StatusDot
    └── layout/          # NavRail / ContextPanel / ToastHost
```

### 5.2 会话状态须持久化(localStorage)

1. `threadId → { title(首条输入前 20 字), createdAt, lastActiveAt }`——标题本地生成,换浏览器会丢,可接受;
2. `currentThreadId`;
3. 挂起态**不依赖** localStorage:B1 落地后由 `pending_interrupt` 字段在刷新/切换时恢复;落地前挂起态刷新即丢(知晓即可)。

### 5.3 挂起交互的 UI 映射

| `interrupt.kind` | UI 形态 | 恢复调用 |
|---|---|---|
| `ask` | 展示问题文本 + 内联输入框 | `POST /chat/answer { thread_id, text }` |
| `memory` | "是否记住:XXX"提案预览 + 确认/忽略按钮(默认焦点在忽略) | `POST /chat/confirm { thread_id, approved }` |
| `unknown` | **不要猜**。禁用输入,提示"检测到未知类型的挂起",给"新开会话"出口 | 不调用 |

B3 落地前的过渡判别(前端可先实现,B3 后删):数组首元素 `'proposal' in p[0]` → memory、`'question' in p[0]` → ask。
