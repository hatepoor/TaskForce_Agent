# TaskForce 前端架构设计

**版本**:v1.1 · 2026-09-16 · 目标工程 `dev/front/`
> v1.1 修订:① 视图统一命名 SettingsView;② 设计 token 以 UI-DESIGN.md §5.3 为准(深色默认);③ interrupt 载荷按 API-CONTRACT v1.1 对象信封(`{kind, text}`)调整类型与解析;④ 契约速查表移除,以 API-CONTRACT.md 为唯一契约事实源。
> 后端六 router 已就绪(全同步),本文档为设计定稿 + 开发顺序说明;代码骨架供用户誊写。

---

## 0. 决策速览

| 议题 | 结论 | 一句话理由 |
|---|---|---|
| 构建 | Vite 7 + Vue 3.5 + TypeScript(严格模式) | 用户指定;Vite 冷启动快,单页工作台无需 SSR |
| 路由 | vue-router 4,**hash 模式**,仅 4 条顶层路由 | 懒加载压首屏体积;hash 避免前端路径与后端 `/memory` 等真实端点撞车(history 模式下 catch-all 会语义冲突) |
| 状态 | Pinia(仅 chat + ui 两个 store) | 消息流需跨页存活、跨组件读写;管理页数据是页面局部状态,不进 store |
| CSS | 原生 CSS 变量 + `<style scoped>`,零 UI 库;token 用 UI-DESIGN §5.3 | 本地单用户工具、组件量 < 20,引组件库收益不抵主题覆盖与体积成本 |
| Markdown | `marked` + `dompurify` | 助手回答是 Markdown,~30KB 可接受;XSS 防护必须 |
| 测试 | Vitest,只测纯函数(帧解析) | `splitFrames`/`parseFrame` 是唯一值得单测的部分 |
| 部署 | 生产构建产物由 FastAPI StaticFiles 挂载(形态 B) | 单用户本地工具,一条 `uvicorn` 起全栈最省事;hash 路由使 `html=True` 足够 |

**前置结论**:后端无 `/api` 前缀。开发期 `VITE_API_BASE=/api`(proxy rewrite 剥掉),生产期 `VITE_API_BASE=`(同源直连)。全项目只在 `http.ts` 一处拼 base。

---

## 1. 工程总览

### 1.1 技术栈选型表

| 层 | 选型 | 版本基线 | 说明 |
|---|---|---|---|
| 运行时 | Node.js | ≥ 20.19(Vite 7 要求) | 仅构建期,不进运行时链路 |
| 框架 | Vue | ^3.5 | `<script setup>` + Composition API 全量 |
| 语言 | TypeScript | ~5.7 | `strict` 全开,见 §1.4 |
| 构建 | Vite | ^7 | dev server + proxy + 生产构建 |
| 路由 | vue-router | ^4.5 | hash 模式,懒加载 |
| 状态 | Pinia | ^3 | 仅 chat / ui 两个 store |
| Markdown | marked + dompurify | 最新 | XSS 防护必须:助手输出可能含 HTML |
| 测试 | Vitest | ^3 | 与 Vite 同源配置 |
| 包管理 | npm | 随 Node | 不引入 pnpm,减少工具面 |
| UI 库 | 无 | — | 见 §1.3 |

### 1.2 为什么需要 vue-router(而不是单页 Tab 切换)

工作台有 4 个信息密度完全不同的区域(对话 / 知识库 / 记忆 / 设置),差异不只是"显示哪块":

1. **首屏体积**:知识库、记忆、MCP 面板 `() => import(...)` 懒加载后,对话页首包小一半以上;
2. **可回退性**:前进/后退可用,刷新能回到原页面;
3. **URL 即状态**:本地调试时可直接把 `#/memory` 发给未来的自己。

代价约 10KB gzip,值得。**但必须 hash 模式**(`createWebHashHistory`):生产形态是 FastAPI 同源挂载 SPA,history 模式下刷新 `/knowledge` 会被后端 404,修它要加 catch-all,而 catch-all 会与 `/chat`、`/memory` 等**同名真实后端路径撞车**。hash 下前端路径形如 `/#/memory`,服务端永远只看到 `/`。

### 1.3 为什么不用 UI 组件库 / Tailwind

- **Element Plus / Naive UI**:体积 300KB+,而本项目只需按钮/输入框/列表/卡片/徽标几类原语;组件库的视觉语言会主导产品,后期改造成本高。
- **Tailwind**:解决"多人协作样式一致性",单人练手项目收益为负。
- **采用方案**:一份 `src/assets/tokens.css` 定义设计令牌(**内容以 UI-DESIGN.md §5.3 的完整变量表为准**:深色默认 `--bg-base: #101114` 系、单一强调色 `#5b9dff`、三个子智能体身份色、浅色 `prefers-color-scheme` 备选),组件内 `<style scoped>` 写局部样式,全局只保留极简 reset 与滚动条样式。

### 1.4 TypeScript 配置基线

```jsonc
// tsconfig.app.json 关键项
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "paths": { "@/*": ["./src/*"] },
    "types": ["vite/client"]
  }
}
```

`exactOptionalPropertyTypes` 暂不开启:与 Vue 的 `withDefaults`/props 透传摩擦大,收益不抵噪音。`@/*` 别名需在 `vite.config.ts` 的 `resolve.alias` 同步一份,否则运行时解析失败。

### 1.5 开发期 vite proxy

```ts
// dev/front/vite.config.ts
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // 后端路由无 /api 前缀,proxy 只负责剥掉它
        rewrite: (p) => p.replace(/^\/api/, ''),
        // SSE 必须关闭代理层聚合缓冲,否则事件会被攒住一次性下发
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache, no-transform'
          })
        },
      },
    },
  },
  build: { outDir: 'dist', sourcemap: true, target: 'es2022' },
})
```

配合:

```bash
# dev/front/.env.development
VITE_API_BASE=/api
# dev/front/.env.production
VITE_API_BASE=
```

> **不要**用 `VITE_API_BASE=/api` 跑生产:后端没有 `/api` 前缀,全线 404。这是部署期最易踩的坑(详见 §7 坑 11)。

---

## 2. 目录结构

```
dev/front/                      前端工程根(独立于 Python src 六包,不进 uv 依赖、不进 hatchling 打包)
├── index.html                  唯一 HTML 入口
├── package.json                前端依赖与脚本;与 pyproject.toml 无任何交集
├── vite.config.ts              别名 / proxy / 构建输出
├── tsconfig.json               TS 项目引用入口
├── .env.development            VITE_API_BASE=/api
├── .env.production             VITE_API_BASE=(空)
├── .gitignore                  node_modules / dist / *.local / .vite
├── public/                     静态资源,原样拷贝进 dist
├── docs/                       本设计文档(API-CONTRACT / ARCHITECTURE / UI-DESIGN / README)
└── src/
    ├── main.ts                 createApp + Pinia + Router + 全局样式,唯一挂载点
    ├── App.vue                 根组件:四段式外壳(NavRail + ContextPanel + router-view),不含业务逻辑
    ├── api/                    后端契约的唯一调用层,组件/store 不直接写 fetch
    │   ├── http.ts             BASE 拼接、超时、ApiError 归一化、JSON 解析
    │   ├── sse.ts              SSE 传输层:fetch + ReadableStream 分帧解析,纯函数,可单测
    │   ├── chat.ts             /chat 三端点 + threads + threads/meta + threads/{id}/messages
    │   ├── knowledge.ts        /knowledge 列表 / 上传 / 删除
    │   ├── memory.ts           /memory 列表 / 删除
    │   ├── skills.ts           /skills 列表
    │   ├── mcp.ts              /mcp/servers CRUD + 连通性测试
    │   └── health.ts           /health 自检
    ├── stores/
    │   ├── chat.ts             会话线程、消息数组、流式轮次、挂起态(核心 store)
    │   └── ui.ts               全局 toast、错误提示队列
    ├── composables/
    │   ├── useChatStream.ts    把 sse.ts 的传输事件绑定到 chat store 的领域动作(唯一调 sseFetch 处)
    │   ├── useAsync.ts         管理页通用:loading / error / run 三件套
    │   ├── useLocalStore.ts    localStorage 封装(JSON + 版本号 + 容错)
    │   └── useClipboard.ts     复制 thread_id / doc_id / 记忆内容
    ├── views/
    │   ├── ChatView.vue        对话页(M3 载体)
    │   ├── KnowledgeView.vue   知识库页
    │   ├── MemoryView.vue      长期记忆页
    │   └── SettingsView.vue    设置页:health / MCP 服务器 / skills 三节
    ├── components/
    │   ├── chat/               对话域组件(见下表)
    │   ├── common/             AppButton / AppInput / EmptyState / Spinner / StatusDot
    │   └── layout/             NavRail / ContextPanel / PageHeader / ToastHost
    ├── types/                  后端契约手工镜像(唯一契约事实源 = API-CONTRACT.md)
    │   ├── chat.ts             ChatItem 联合类型、SSE 事件载荷、RoutePayload
    │   ├── knowledge.ts        KDoc / KUploadResult
    │   ├── memory.ts           MemoryItem
    │   ├── skills.ts           SkillMeta
    │   ├── mcp.ts              MCPServerConfig 判别联合(stdio | http)
    │   └── api.ts              ApiError、Result<T> 等通用包装
    ├── utils/
    │   ├── id.ts               newThreadId():sess- 前缀 + UUID(见 §7 坑 3)
    │   ├── time.ts             相对时间格式化
    │   └── markdown.ts         marked + dompurify 封装,带 LRU 缓存
    └── assets/
        ├── tokens.css          设计令牌(UI-DESIGN §5.3)
        └── base.css            reset + 全局排版
```

**与仓库的关系**:`dev/front/` 完全独立,有自己的 `package.json` 与 `node_modules`,**不参与** `uv sync`、hatchling 打包、pytest;前后端只有 HTTP 契约,前端改动永远不会破坏 `uv run pytest`。目录名与 `docs/dev/` 同层级语义——都是开发期产物。生产构建输出 `dev/front/dist/` 由后端挂载(§6.2)。

**`components/chat/` 关键组件:**

| 组件 | 职责 |
|---|---|
| `MessageList.vue` | 滚动容器,渲染 `ChatItem[]`,贴底自动滚动策略(UI-DESIGN §6.2) |
| `UserBubble.vue` | 用户消息气泡 |
| `AssistantBubble.vue` | 助手消息:流式期纯文本 pre-wrap,结束后 Markdown 渲染、光标态、usage 角标、兜底文案 |
| `RouteTrail.vue` | 路由轨迹条:聚合本轮全部 route 事件,默认折叠一行,展开看 tasks |
| `SubagentBatchCard.vue` | 子任务批次卡:派发清单 + 回收状态(异步派发下"已回收"在下一轮可见,见 API-CONTRACT §三 route 注) |
| `InterruptCard.vue` | 挂起卡容器,按 `kind` 分派到下面两个 |
| `AskCard.vue` | ask 问询:问题文本 + 多行输入 + 提交(空输入禁止) |
| `ConfirmCard.vue` | memory 提案:预览 + 「记入记忆」/「忽略」(默认焦点在忽略) |
| `Composer.vue` | 底部输入区:Enter 发送 / Shift+Enter 换行 / 流中禁用 / 停止接收按钮 / 中文输入法组合态 |
| `UsageBadge.vue` | 本轮增量 token 一行小字(差分计算) |
| `ThreadList.vue` | 侧边会话列表:切换 / 新建 / 本地标题 |

---

## 3. 分模块开发计划(M0 ~ M6)

每个模块是可独立验收的纵切,顺序不可打乱。每完成一个模块跑 `npm run build` 与 `npx vue-tsc --noEmit`。

### M0 — 脚手架与 proxy 打通

**目标**:空壳工程跑起来,证明"前端 → vite proxy → FastAPI"链路通。

**涉及**:`dev/front/` 根配置、`src/main.ts`、`src/App.vue`、`src/api/http.ts` + `health.ts`、`src/assets/`。

**步骤**:`npm create vite@latest` 生成后清理示例 → 写入 `vite.config.ts`(§1.5)、两份 `.env.*`、`.gitignore` → `http.ts` + `health.ts`,App.vue 临时调 `GET /health` 打到页面 → `tokens.css`(抄 UI-DESIGN §5.3)/`base.css` 接入 main.ts。

**验收**:前后端同时在跑,`http://localhost:5173` 显示 `{status,db,sandbox}` JSON;停后端刷新显示可读错误;`npm run build` 产出 dist;`vue-tsc --noEmit` 零错误。

**依赖**:无。**前置:第一批后端改造(B1~B3)建议在此之前完成。**

### M1 — API 层与类型镜像

**目标**:六个后端 router 全部有类型化封装,`types/` 成为前端唯一契约镜像。

**要点**:
- `http.ts` 提供 `request<T>(path, init)`:`AbortSignal.timeout` 默认 15s,SSE 单列不走此超时(用静默看门狗,§4.4);非 2xx 抛 `ApiError(status, detail)`。
- 类型全部**手工镜像**,不引 `openapi-typescript`(规模小,手写过程暴露契约理解偏差)。与 API-CONTRACT.md 冲突时以契约为准。
- `mcp.ts` 用判别联合还原后端 discriminator;**`POST /mcp/servers` 的 name 在 query、body 直接是 config 对象**(B6 落地前),在 `api/mcp.ts` 消化掉,不让组件感知,并写文件头注释防后人"顺手改掉"。

**验收**:临时 `ApiProbeView.vue` 依次调 GET /chat/threads、/knowledge、/memory、/skills、/mcp/servers、/health 展示原始 JSON 与耗时;DELETE 与 MCP test 各手动点一次确认正反路径(含 404/400 detail 展示)。

**依赖**:M0。

### M2 — 会话管理(依赖后端 B1/B2)

**目标**:新建会话、列表切换、刷新后身份与历史保留。

**要点**:
- `newThreadId()` 必须是 **`sess-` + UUID**(后端过滤 `LIKE 'sess-%'`,裸 UUID 永远不进列表;`crypto.randomUUID` 仅安全上下文可用,localhost 算,局域网 IP 不算,保留降级分支):

```ts
// src/utils/id.ts
export function newThreadId(): string {
  const uuid = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`
  return `sess-${uuid}`
}
```

- 会话列表优先用 `GET /chat/threads/meta`(B2),标题取首条用户输入前 20 字存 localStorage(`tf.threads`);未命中 meta 的裸 id 直接展示。
- **历史回填**:`GET /chat/threads/{id}/messages`(B1)拉取消息渲染;`pending_interrupt` 非空时恢复挂起卡。
- 新建会话不立即请求后端(后端首次 `/chat` 才惰性建 checkpoint),只在前端生成 id 置为当前。

**验收**:新建三个会话,刷新后当前会话、列表、历史消息、挂起态都在;会话间消息不串台。

**依赖**:M1;**后端 B1/B2 已落地**。

### M3 — SSE 对话流(核心,依赖 B3,建议同批做 B4/B5)

**目标**:完整对话闭环——发消息、流式文本、路由轨迹、挂起卡、恢复继续。

**要点**:
- 三入口共用同一条 SSE 解析管线:`POST /chat`(提问)、`POST /chat/answer`(ask 恢复)、`POST /chat/confirm`(memory 恢复)。**不能用 `/chat` 做恢复**——text 走 messages 分支而非 `Command(resume=...)`,混用静默错误。
- 挂起双语义按 `interrupt.kind` 判别(B3 信封);B3 落地前用 key 存在性过渡(见 API-CONTRACT §5.3)。
- 流式期间 Composer 禁用发送、显示「停止接收」;store 层 `turn.status === 'streaming'` 兜底单飞。
- 一轮结束 token 为空时补兜底文案(§7 坑 6)。

**验收**:
1. 普通提问:用户气泡 → 路由轨迹 → 流式文本 → usage 角标(本轮增量);
2. ask 挂起:问询卡出现 → 提交后流继续 → 卡片折叠为已答态;
3. 「记住我喜欢用 uv」:提案卡 → 记入后记忆页可见;忽略则不出现;
4. kill 后端再发送:错误可读,已收文本不丢,输入框内容保留;
5. 流中「停止接收」:立即停渲染,轮次标 aborted,可继续发下一条(留灰色提示"服务端可能仍完成了部分动作");
6. 无挂起时手工调 confirm:400 detail 展示,挂起卡清除。

**依赖**:M1、M2。

### M4 — 知识库页(依赖 B7)

**要点**:
- 上传 FormData 不手动设 Content-Type;前端先做 20MB 预检,后端 detail 展示兜底;**多选拆成串行 N 个请求**(上传是同步阻塞的,embedding 逐块算,并发只会让进度互相打架),进度用 `XMLHttpRequest.upload.onprogress`(fetch 拿不到上传进度)。
- `created: false` 提示"该文档已存在,已复用"而非"上传成功"。
- 删除二次确认(显示 filename);失败刷新列表。

**验收**:上传 `.md` 后列表出现且 chunks > 0;超 20MB 前端拦下;删除后列表一致。

**依赖**:M1(可与 M3 并行);B7。

### M5 — 记忆页

**要点**:`source` 徽标区分 `explicit`(用户明示)/`confirmed`(自动确认);`DELETE /memory/{key}` 的 key 必须 `encodeURIComponent`;空态区分"还没有记忆" vs "检索失败"。

**验收**:M3 确认写入的记忆出现在列表且 source 为 confirmed;删除后刷新仍不存在。

**依赖**:M1。

### M6 — SettingsView 与收尾

**要点**:
- **Health**:`status/db/sandbox` 三状态灯;`sandbox` 非 ok 即异常(UI-DESIGN §4.4);30s 轮询,`document.visibilityState` 不可见时暂停。
- **MCP**:列表(stdio/http 徽标)、新增表单(transport 切换联动字段,**切换不丢草稿**,提交只带当前类型字段)、测试(`ok:false` 显示"未连通"而非红色报错)、删除确认。
- **Skills**:只读,加"技能变更需重启后端生效"提示。
- 收尾:统一 ToastHost、`data-testid` 命名、EmptyState/Spinner 全站统一;**形态 B 下完整跑一遍对话验收**(§6.2)。

**验收**:sandbox 未配置、MCP 为空时各面板优雅降级不报错;控制台零 Vue 警告。

**依赖**:M1~M5。

### 模块依赖图

```
后端 B1/B2/B3 ──► M0 ──► M1 ──┬──► M2 ──► M3(建议 B4/B5 同批)──┐
                              ├──► M4(B7)──────────────────────┼──► M6
                              └──► M5 ──────────────────────────┘
```

---

## 4. SSE 客户端设计

### 4.1 约束

1. **POST 不能用 `EventSource`**(只支持 GET、不能带 body,且自动重连对本项目有害——会重复触发一轮对话)。必须 `fetch` + `response.body.getReader()`。
2. 帧格式 `data: {json}\n\n`,JSON 单键对象,键名即事件类型;前端不需解析 `event:` 字段,但解析器按 SSE 规范兼容多行 `data:` 与注释行,防未来加心跳。
3. 事件五种(信封后):`token`(string)/ `route`(RoutePayload)/ `interrupt`(`{kind, text}` 对象,B3)/ `usage`(UsageEvent)/ `error`(B4,`{message, code?}`)。
4. 当前后端攒完再吐(B4 前),渲染层按"可能一次性到达一大批帧"设计(rAF 合并,§7 坑 5);解析器本就逐帧消费,B4 落地后零改动。

### 4.2 传输层:`src/api/sse.ts`

```ts
// 纯传输层,不含业务语义,便于单测
import type { RoutePayload, InterruptEnvelope, UsageEvent, ErrorEvent } from '@/types/chat'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

export type SseEvent =
  | { type: 'token'; data: string }
  | { type: 'route'; data: RoutePayload }
  | { type: 'interrupt'; data: InterruptEnvelope }
  | { type: 'usage'; data: UsageEvent }
  | { type: 'error'; data: ErrorEvent }
  | { type: 'unknown'; data: unknown }   // 未知键:记录并忽略,不中断流

/** 把累计缓冲切成完整帧;返回剩余的不完整尾巴。 */
export function splitFrames(buf: string): { frames: string[]; rest: string } {
  // 关键:先归一化 CRLF。某些代理会把 \n\n 变成 \r\n\r\n,
  // 只按 '\n\n' 切会永远切不开,表现为"流不结束、界面无输出"。
  const normalized = buf.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const rest = parts.pop() ?? ''
  return { frames: parts, rest }
}

/** 解析单个 SSE 帧;注释帧/心跳/坏 JSON 返回 null,由调用方计数。 */
export function parseFrame(raw: string): SseEvent | null {
  const dataLines = raw
    .split('\n')
    .filter((l) => l.startsWith('data:'))
    .map((l) => l.slice(5).replace(/^ /, ''))
  if (dataLines.length === 0) return null
  let obj: Record<string, unknown>
  try {
    obj = JSON.parse(dataLines.join('\n'))
  } catch {
    return null                                  // 半帧/损坏帧:丢弃,不断流
  }
  const key = Object.keys(obj)[0]
  if (!key) return null
  const data = obj[key]
  switch (key) {
    case 'token':     return { type: 'token', data: String(data) }
    case 'route':     return { type: 'route', data: data as RoutePayload }
    case 'interrupt': return { type: 'interrupt', data: data as InterruptEnvelope }   // B3 信封:{kind, text}
    case 'usage':     return { type: 'usage', data: data as UsageEvent }
    case 'error':     return { type: 'error', data: data as ErrorEvent }
    default:          return { type: 'unknown', data }
  }
}

export interface SseHandlers {
  onToken?: (t: string) => void
  onRoute?: (r: RoutePayload) => void
  onInterrupt?: (i: InterruptEnvelope) => void
  onUsage?: (u: UsageEvent) => void
  onErrorEvent?: (e: ErrorEvent) => void        // 流内 error 帧(B4)
  onError?: (e: SseError) => void               // 传输层错误:非 2xx / 无 body / 网络中断
  onDone?: () => void                           // 流正常结束(挂起也算:服务端本轮流就此打住)
}

export class SseError extends Error {
  constructor(
    public kind: 'http' | 'network' | 'nobody' | 'parse',
    public status: number,
    message: string,
  ) { super(message) }
}

export async function sseFetch(
  path: string, body: unknown, handlers: SseHandlers, signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    handlers.onError?.(new SseError('network', 0, '无法连接后端,请确认 uvicorn 已启动'))
    return
  }

  if (!res.ok) {
    // 非 2xx:后端在 StreamingResponse 之前抛了 HTTPException,body 是 JSON
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (typeof data?.detail === 'string') detail = data.detail
      else if (data?.detail) detail = JSON.stringify(data.detail)
    } catch { /* 非 JSON 错误体:保留状态码文案 */ }
    handlers.onError?.(new SseError('http', res.status, detail))
    return
  }
  if (!res.body) {
    handlers.onError?.(new SseError('nobody', res.status, '响应没有可读流'))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  let badFrames = 0

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      // 必须 { stream: true }:中文 3 字节,网络分片劈开多字节字符会出乱码
      buf += decoder.decode(value, { stream: true })

      const { frames, rest } = splitFrames(buf)
      buf = rest
      for (const raw of frames) {
        const ev = parseFrame(raw)
        if (!ev) { badFrames += 1; continue }
        switch (ev.type) {
          case 'token':     handlers.onToken?.(ev.data); break
          case 'route':     handlers.onRoute?.(ev.data); break
          case 'interrupt': handlers.onInterrupt?.(ev.data); break
          case 'usage':     handlers.onUsage?.(ev.data); break
          case 'error':     handlers.onErrorEvent?.(ev.data); break
          case 'unknown':   console.warn('[sse] 未知事件类型', ev.data); break
        }
      }
    }
    buf += decoder.decode()                     // 冲掉解码器内部残留
    if (buf.trim()) {
      const ev = parseFrame(buf)
      if (ev?.type === 'token') handlers.onToken?.(ev.data)
    }
    if (badFrames > 0) console.warn(`[sse] 丢弃了 ${badFrames} 个无法解析的帧`)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    handlers.onError?.(new SseError('network', 0, '流读取中断'))
    return
  } finally {
    reader.releaseLock()
  }
  handlers.onDone?.()
}
```

### 4.3 领域层:`src/composables/useChatStream.ts`

把传输事件翻译成 store 动作,管理"当前轮次"生命周期。**唯一允许调用 `sseFetch` 的地方。**

```ts
import { ref } from 'vue'
import { sseFetch, type SseHandlers } from '@/api/sse'
import { useChatStore } from '@/stores/chat'

export function useChatStream() {
  const chat = useChatStore()
  const controller = ref<AbortController | null>(null)

  async function run(path: string, body: unknown) {
    if (chat.isStreaming) return                  // 单轮互斥,store 层兜底
    const ac = new AbortController()
    controller.value = ac
    chat.beginTurn()

    const handlers: SseHandlers = {
      onToken: (t) => chat.appendToken(t),
      onRoute: (r) => chat.pushRoute(r),
      onInterrupt: (i) => chat.setPending(i),     // B3 信封:{kind, text}
      onUsage: (u) => chat.attachUsage(u),
      onErrorEvent: (e) => chat.failTurn(e.message),   // 流内 error 帧(B4)
      onError: (e) => chat.failTurn(e.message, e.kind === 'http' ? e.status : undefined),
      onDone: () => chat.endTurn(),               // 挂起也走这里:轮次结束,pending 非空
    }
    await sseFetch(path, body, handlers, ac.signal)
    chat.flushTokens()
    controller.value = null
  }

  return {
    send: (text: string) => run('/chat', { thread_id: chat.currentThreadId, text }),
    submitAnswer: (text: string) => run('/chat/answer', { thread_id: chat.currentThreadId, text }),
    submitConfirm: (approved: boolean) => run('/chat/confirm', { thread_id: chat.currentThreadId, approved }),
    /** 仅停前端消费;服务端那轮仍会跑完(§7 坑 7),文案用「停止接收」 */
    abort: () => controller.value?.abort(),
  }
}
```

**调用侧示例(`AskCard.vue`):**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useChatStream } from '@/composables/useChatStream'

const chat = useChatStore()
const { submitAnswer } = useChatStream()
const draft = ref('')

async function submit() {
  const text = draft.value.trim()
  if (!text || chat.isStreaming) return
  chat.resolvePending({ answer: text })   // 先落本地状态,卡片立刻变"已提交"
  draft.value = ''
  await submitAnswer(text)                // 后端 400(挂起已失效)时 failTurn 提示
}
</script>
```

### 4.4 错误处理约定

| 场景 | 判定 | 前端行为 |
|---|---|---|
| 后端未启动 / 连接被拒 | fetch 抛非 AbortError | 助手气泡转错误态「无法连接后端,请确认 uvicorn 已启动」,**保留输入框内容** |
| 非 2xx | `res.ok === false` | 400 → 业务提示(detail 原文,可能"挂起已在别处恢复")并清挂起卡;404 → 刷新对应列表;422 → 校验详情;其他 → detail 原文 |
| 响应无 body | `res.body == null` | 「响应没有可读流」,通常是代理层把流吃了 |
| 流中途断开 | `reader.read()` 抛错 | 本轮标 error,已渲染文本保留 + 「(连接中断,输出可能不完整)」 |
| 单帧解析失败 | `parseFrame` 返回 null | 丢弃计数,**绝不因一帧坏掉中断整条流** |
| 用户主动中止 | AbortError | 不算错误:标 `aborted`,留"服务端可能仍完成了部分动作"提示 |
| 流结束无任何 token | `onDone` 时 token 为空 | 补兜底文案(§7 坑 6) |

**超时策略**:SSE 不设总超时。改用**静默看门狗**:每收到任意帧重置计时器,连续 120s 无帧才判卡死。首轮惰性装配图 + MCP 可能几十秒,UI 必须在 1s 内给出"正在初始化智能体…"反馈。

---

## 5. 状态管理设计

### 5.1 store 划分

| store | 是否创建 | 内容 | 理由 |
|---|---|---|---|
| `useChatStore` | **是** | 会话列表、当前 thread_id、各会话消息数组、轮次状态、挂起态 | 消息流跨页面存活,ThreadList/MessageList/Composer/InterruptCard 四组件读写 |
| `useUiStore` | **是** | toast 队列、全局 loading | 跨页横切关注点 |
| 管理页(knowledge/memory/settings) | **否** | — | 数据只被单页消费,进页拉、离页弃;`useAsync` + `ref` 局部状态 |

判断准则:**只有"跨路由存活"或"被三个以上无共同祖先的组件消费"才进 store**。

### 5.2 `chat.ts` 结构

```ts
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { ChatItem, InterruptEnvelope, RoutePayload, UsageEvent } from '@/types/chat'
import { newThreadId } from '@/utils/id'

export const useChatStore = defineStore('chat', () => {
  // ---- 会话身份 ----
  const threads = ref<ThreadMetaRow[]>([])               // /chat/threads/meta 镜像(B2)
  const currentThreadId = ref<string>(newThreadId())
  const threadMeta = ref<Record<string, ThreadMeta>>({}) // 本地标题/时间(localStorage 同步)

  // ---- 消息与轮次(按会话分组,切会话不丢) ----
  const itemsByThread = ref<Record<string, ChatItem[]>>({})
  const turnByThread = ref<Record<string, TurnState | null>>({})
  const pendingByThread = ref<Record<string, PendingInterrupt | null>>({})

  const items = computed<ChatItem[]>(() => itemsByThread.value[currentThreadId.value] ?? [])
  const turn = computed(() => turnByThread.value[currentThreadId.value] ?? null)
  const pending = computed(() => pendingByThread.value[currentThreadId.value] ?? null)
  const isStreaming = computed(() => turn.value?.status === 'streaming')

  // token 的 rAF 缓冲(§7 坑 5):故意放在响应式系统之外
  let tokenBuf = ''
  let rafId: number | null = null

  function beginTurn() { /* 关闭上一轮、写新 TurnState、记录 usageBefore 快照 */ }
  function appendToken(t: string) { /* tokenBuf += t;rafId 空则 requestAnimationFrame(flush) */ }
  function flushTokens() { /* tokenBuf 一次性并入末尾 assistant item,清空 */ }
  function pushRoute(r: RoutePayload) { /* flushTokens(); 关当前 assistant 流;push RouteItem */ }
  function setPending(i: InterruptEnvelope) { /* kind → PendingInterrupt;push InterruptItem */ }
  function attachUsage(u: UsageEvent) { /* usageAfter;本轮增量 = after - before */ }
  function endTurn() { /* flushTokens();streaming=false;token 为空补 note */ }
  function failTurn(msg: string, status?: number) { /* 标 error */ }
  function resolvePending(patch: Partial<PendingInterrupt>) { /* 卡片切 submitting/resolved */ }

  return {
    threads, currentThreadId, threadMeta, items, turn, pending, isStreaming,
    beginTurn, appendToken, flushTokens, pushRoute, setPending,
    attachUsage, endTurn, failTurn, resolvePending,
  }
})
```

### 5.3 消息类型建模(`src/types/chat.ts`)

消息数组是**时间序的平铺联合数组**,不是"用户/助手"两个平行数组——路由轨迹与 token 交错发生,平铺数组天然保序。

```ts
/** ---------- 后端契约镜像(唯一事实源:API-CONTRACT.md) ---------- */

export type RouteNext = 'answer' | 'ask' | 'memory' | 'dispatch'

export interface TaskPayload {
  agent: 'retriever' | 'research' | 'executor'
  task: string
  reason: string
}
export interface RoutePayload {
  next: RouteNext
  question: string | null
  tasks: TaskPayload[] | null
}

/** interrupt 信封(B3 后):kind 自描述,恢复端点按 kind 选,不靠猜 */
export interface InterruptEnvelope {
  kind: 'ask' | 'memory' | 'unknown'
  text: string
}

export interface UsageEvent {
  thread_id: string          // 全流中唯一携带 thread_id 的事件
  calls: number              // 进程级累计,不是本轮
  input_tokens: number
  output_tokens: number
}

export interface ErrorEvent {  // B4 流内 error 帧
  message: string
  code?: string                // 'recursion_limit' 等
}

/** ---------- UI 侧模型 ---------- */

export interface BaseItem { id: string; seq: number; at: number }

export interface UserItem extends BaseItem { kind: 'user'; text: string }

export interface AssistantItem extends BaseItem {
  kind: 'assistant'
  text: string
  streaming: boolean           // true:纯文本 pre-wrap + 光标;false:Markdown 渲染
  usage?: TurnUsage
  note?: string                // 兜底:递归过深 / 无输出 / 流中断
  error?: { message: string; status?: number }
}

export interface RouteItem extends BaseItem { kind: 'route'; route: RoutePayload }

export interface InterruptItem extends BaseItem {
  kind: 'interrupt'
  sub: 'ask' | 'memory' | 'unknown'
  text: string
  status: 'waiting' | 'submitting' | 'resolved' | 'failed'
  answer?: string              // ask 已答
  approved?: boolean           // memory 已决
  error?: string
}

export type ChatItem = UserItem | AssistantItem | RouteItem | InterruptItem

export interface TurnUsage { calls: number; inputTokens: number; outputTokens: number }

export interface TurnState {
  turnId: string
  status: 'streaming' | 'done' | 'aborted' | 'error'
  startedAt: number
  finishedAt?: number
  usageBefore?: { calls: number; input_tokens: number; output_tokens: number }
  usageAfter?: UsageEvent
  error?: { message: string; status?: number }
}

export interface PendingInterrupt {
  sub: 'ask' | 'memory' | 'unknown'
  text: string
  status: InterruptItem['status']
  itemId: string               // 关联消息数组里的 InterruptItem
}

export interface ThreadMeta { title: string; createdAt: number; lastActiveAt: number; awaitingTasks?: boolean }
export interface ThreadMetaRow { thread_id: string; last_checkpoint: string; checkpoints: number }
```

B3 落地前的过渡判别(落地后删除):

```ts
export function classifyInterruptLegacy(p: unknown): InterruptEnvelope {
  const first = Array.isArray(p) ? p[0] : p
  if (first && 'proposal' in first) return { kind: 'memory', text: first.proposal }
  if (first && 'question' in first) return { kind: 'ask', text: first.question }
  return { kind: 'unknown', text: JSON.stringify(first) }
}
```

`interrupt` 数组理论上可多元素(后端 `[u.value for u in updates]`),当前图结构恒为一元素;UI 约定只渲染第一个为交互卡,其余只读附列。

### 5.4 usage 角标为什么显示"增量"

`UsageTracker` 是进程级单例,`usage` 事件是自 uvicorn 启动以来的累计值,且跨会话共享。直接显示会得到"第一次 100,第二次 350"的困惑数字。因此:`beginTurn()` 记 `usageBefore` 快照(上一轮的 `usageAfter`,首轮为 0);`attachUsage(u)` 后本轮增量 = `u - usageBefore`;角标显示「本轮 ↑123 / ↓456 tok · 累计 N 次调用」,累计值放 tooltip。注意刷新页面后首轮快照丢失,差值偏大,可接受(副作用已在 API-CONTRACT 登记)。

---

## 6. 构建与集成

### 6.1 脚本

```jsonc
// dev/front/package.json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview --port 4173",
    "typecheck": "vue-tsc --noEmit",
    "test": "vitest run",
    "lint": "eslint . --ext .ts,.vue"
  }
}
```

`build` 前置 `vue-tsc --noEmit`:类型错误阻断构建,是小型前端最划算的质量闸门。

### 6.2 两种部署形态与推荐

**形态 A — 双进程(开发期)**:`uv run uvicorn api.main:app --reload` + `npm run dev`,前端 5173,proxy 转发。

**形态 B — 单进程(推荐日常与演示)**:

```bash
cd dev/front && npm run build
uv run uvicorn api.main:app        # 打开 http://127.0.0.1:8000
```

后端挂载(`src/api/main.py`,所有 `include_router` **之后**追加;文档类改动可代写):

```python
# 仅当构建产物存在时挂载,保证没跑过 npm build 的环境(CI/pytest)照常启动。
# 必须放在 include_router 之后:FastAPI 按注册顺序匹配,精确路由优先。
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_DIST = Path(__file__).resolve().parents[2] / "dev" / "front" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="front")
```

**推荐形态 B**:单用户本地工具的心智负担应停留在"起一个服务";无 CORS、无端口漂移、无"忘起前端"。hash 路由保证 `html=True` 足够(所有前端路径服务端部分都是 `/`)。

**注意**:`StaticFiles` 挂 `/` 后,拼错的后端路径返回 404 HTML 而非 JSON——调试期看到 HTML 响应体就是"路径写错了"的信号。

### 6.3 仓库卫生

`dev/front/.gitignore` 必含 `node_modules/`、`dist/`、`*.local`、`.vite/`。`dist/` 不入库(构建产物入库会让"代码改了产物没更"成隐性 bug 源);clone 后需自行 `npm run build`,本地工具可接受。

---

## 7. 风险与坑位清单

按"踩中概率 × 排查难度"排序,前四条必踩。

### 坑 1 — SSE 半帧与 UTF-8 字符跨片(必踩)

**现象**:乱码、最后几个字丢失、整条流卡住。
**根因**:(a) TCP 分片与 `\n\n` 边界无关,一次 `read()` 可能拿半个 JSON;(b) 中文 UTF-8 3 字节,`decode(value)` 不带 `{stream: true}` 会把跨片字符解成 `U+FFFD`(本项目输出全中文,必踩)。
**对策**:见 `splitFrames`/`sseFetch` 实现;CRLF 归一化防代理变形;流结束 `decoder.decode()` 冲残留。

### 坑 2 — interrupt 双语义恢复端点不可混用(必踩)

**现象**:B3 落地前,类型判错不报错——`approved=true` 被当答案写进对话,或字符串 "yes" 被 memory 节点当真值,**静默写入未确认的记忆**。
**对策**:B3 信封 + `_require_interrupt` 后端兜底;前端按 `kind` 选端点;`ConfirmCard` 只发 true/false,不提供"自由文本确认"入口。**B3 落地前必须用 legacy 判别函数过渡,不能裸猜。**

### 坑 3 — thread_id 必须前端生成且带 `sess-` 前缀(必踩)

**现象**:新会话永远不进列表;或刷新后上下文找不回。
**根因**:`usage` 事件是全流唯一带 thread_id 的帧,在轮次末尾才发,不能等它确认身份;`list_session_ids()` 过滤 `LIKE 'sess-%'`。
**对策**:§M2 的 `newThreadId()`;对 `/chat/threads` 返回的 id 做前缀断言,契约漂移在开发期暴露。

### 坑 4 — 全同步后端 + 长回答占用线程池(必踩)

**现象**:等长回答时点知识库页整界面转圈;多个 SSE 并发后所有请求变慢。
**根因**:端点全 `def` 走线程池(默认约 40 线程),一个 SSE 连接在整轮期间占线程,内部还串行调 LLM、并行分支各取 psycopg 连接。
**对策**:**单飞轮次**(UI 禁用 + store 早退);**不自动重试**(自动重试会重复触发整轮任务,可能重复写记忆、重复执行沙箱代码);管理页 loading 局部化;首轮冷启动 1s 内给"正在初始化智能体…"反馈。

### 坑 5 — token 流渲染性能(必踩)

**现象**:回答变长界面卡顿、输入框打不出字、CPU 飙高。
**根因**:每 token 一次响应式写 + Markdown 重解析 + DOMPurify 清洗,O(长度²);后端攒完再吐(B4 前)导致一帧内数百 token。
**对策**:token 累加进**非响应式** `tokenBuf`,`requestAnimationFrame` 每帧最多刷一次;**流式期间不解析 Markdown**(`streaming` 时 pre-wrap 纯文本,结束才 `marked`;半截 Markdown 本来也渲染不对);`markdown.ts` LRU 缓存;`:key` 用创建时生成的 id 而非数组下标;历史 RouteItem > 50 条折叠为单行(本地工具不引虚拟列表)。

### 坑 6 — 某些路径不产生任何 token(易踩)

**现象**:发问后出现空气泡,轮次结束。
**根因**:`run_turn` 有两条返回 AIMessage 但不走流式 token 的路径——`GraphRecursionError` 兜底与无 checkpointer 桩;memory 确认写入路径也只整段回复不走流式。
**对策**:`endTurn()` 检查 token 为空时写 `note`:「本轮循环过深已中止,请把需求拆小一些」或「本轮没有产生文本输出(可能已直接执行动作,如写入记忆)」。B4 落地后由 error 帧覆盖前者。

### 坑 7 — 中止不等于取消服务端任务(易踩)

**现象**:点了「停止接收」,过一会儿记忆里多了一条、沙箱执行完了。
**根因**:`abort()` 只断浏览器侧读取;后端同步 generator 继续跑完(B4 前,"下次 yield 检测断开"的窗口都不存在)。
**对策**:文案「停止接收」非「取消任务」;中止后重拉 `/memory` 与会话列表(切页 onMounted 拉取天然满足);留灰色提示"上一轮已停止接收,服务端可能仍完成了部分动作"。

### 坑 8 — usage 是进程级累计值(易踩)

见 §5.4。对策:相邻快照差分;文案避免"本会话用量"措辞。

### 坑 9 — 历史消息回放(结构性缺口,B1 解决)

B1 落地前切换旧会话聊天区空白。前端曾考虑 localStorage 缓存方案,定稿为**等 B1 端点**,`itemsByThread` 每会话独立数组的设计使数据来源可无缝切换。M2 依赖 B1,不安排降级路径。

### 坑 10 — 恢复端点的 400 是正常业务路径(易踩)

**现象**:网络面板红色 400,前端弹未捕获异常。
**根因**:双击按钮/双标签页同时恢复必触发 400「该会话没有待处理的挂起」。
**对策**:400 映射为业务提示(toast detail 原文),挂起卡标 `failed`;提交瞬间即 `disabled` 堵重复点击。

### 坑 11 — 生产环境 `VITE_API_BASE`(部署必踩)

**现象**:`npm run build` 后所有请求 404。
**根因**:构建误用 development 模式或 `.env.production` 漏配,请求打到 `/api/chat` → 后端无此前缀。
**对策**:两份 `.env` 都入库(不含密钥);base 只在 `http.ts` 一处读;M6 验收**必须**在形态 B 下完整跑一遍,不能只 `vite preview`。

### 坑 12 — `POST /mcp/servers` 参数位置反直觉(易踩)

**现象**:新增 MCP 永远 422 报缺 name。
**根因**:`create_server(name: str, config: dict)`——name 是 query 参数,body 直接是 config 对象。
**对策**:`api/mcp.ts` 消化(代码见 §M1),文件头注释防后人"顺手改掉";B6 落地后此坑消失,但前端代码无需改(封装层切换)。

---

## 附录:开发顺序总览

1. 用户确认全量方案(README.md 决策表)→ 登记 TODO/ROADMAP;
2. **后端第一批 B1~B3**(业务代码用户誊写,Claude 写 `tests/test_api_history.py` 等配套测试);
3. M0 脚手架(配置类可代写)→ M1 → 依模块计划推进;
4. M3 开工前完成 B4/B5(真流式 + error 帧);
5. M6 收尾时做形态 B 验收 + README 增补前端起步段。
