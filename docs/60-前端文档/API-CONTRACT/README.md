# TaskForce 前端 API 契约文档

> 一句话: 全站 API 契约入口:基础约定 + 端点总索引
> 体系: 前端文档 · API-CONTRACT
> 分片: 01~08
> 索引: 文末「分片索引」节

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

> **已知缺口(已闭合,2026-09-22)**:`DELETE /knowledge/{doc_id}` 删不存在的文档曾返回 500(旧 `RAGStore.delete()` 抛 `ValueError` 而 router 未捕获)。**换内核(rag_v01)时一并修掉**:改为路由先查存在性,不存在直接 404 —— 前端的过渡处理可撤,按 404 走正式分支。

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
| 22 | POST | `/chat/plan` | plan 计划确认挂起恢复:'y' 执行,其他取消【2026-09-27 落地】 | `text/event-stream` |
| 23 | DELETE | `/chat/threads/{thread_id}` | 删除会话:清 checkpoint 三表 + 任务台账【2026-09-27 落地】 | JSON |
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

### 分片索引

| 分片 | 涵盖章节 | 内容一句话 |
|---|---|---|
| [01-端点-chat.md](./01-端点-chat.md) | §2.1 | Chat 资源:发起对话与三类挂起恢复(`confirm`/`answer`/`plan`)、线程列表/元数据/历史回填、任务 peek 与自动汇总、删除会话 |
| [02-端点-知识库.md](./02-端点-知识库.md) | §2.3 | Knowledge 资源:文档列表、上传(multipart,20 MB 上限)、删除 |
| [03-端点-记忆.md](./03-端点-记忆.md) | §2.4 | Memory 资源:长期记忆列表(硬编码 `limit=100`)与单条删除 |
| [04-端点-技能与MCP.md](./04-端点-技能与MCP.md) | §2.5、§2.6 | Skills 资源:技能元数据列表;MCP 资源:服务器列表、新增/覆盖、删除、连通性测试 |
| [05-端点-设置与健康.md](./05-端点-设置与健康.md) | §2.2、§2.7 | Health 资源:`/health` 存活 + DB + 沙箱自检;Models 资源:设置页模型配置读取与保存(api_key 掩码回显) |
| [06-SSE事件帧协议.md](./06-SSE事件帧协议.md) | §三 | SSE 端点范围、帧格式、五类事件(`token`/`route`/`interrupt`/`usage`/`error`)、解析规则、边界情况、请求超时 |
| [07-后端改造清单.md](./07-后端改造清单.md) | §四 | B1~B8 改造项(历史回填、会话元数据、interrupt 信封、真流式 + error 帧、锁与竞态、小修)与「不改(前端兜底)」 |
| [08-前端落地建议.md](./08-前端落地建议.md) | §五 | 前端文件组织、会话状态须持久化(localStorage)、挂起交互的 UI 映射 |

> 本手册由原 `API-CONTRACT.md` 按节拆分而成,正文除新增分片头部与本索引外未作改动;端点条目见上方 §2.0 总览。
