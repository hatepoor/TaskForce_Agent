# TaskForce 前端全量设计方案(总览)

> 2026-09-16 · 由 API 契约 / 前端架构 / UI 交互三个设计角色并行产出,主会话交叉校对后定稿。
> 目标工程:`dev/front/`(仓库根新目录,Vue 3 + Vite + TypeScript,独立于 Python src 六包)。
> 文档均为设计定稿,可代写;前端业务代码按教学模式由用户誊写。

## 文档地图

| 文档 | 内容 | 读者开工前必读章节 |
|---|---|---|
| [API-CONTRACT.md](API-CONTRACT.md) | 15 个端点的请求/响应全表、SSE 帧协议与边界情况、后端改造清单详细方案 | 全文 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 技术栈、目录结构、M0~M6 模块计划、SSE 客户端与 Pinia 状态设计、12 条坑位清单 | 全文 |
| [UI-DESIGN.md](UI-DESIGN.md) | 布局、组件树、对话流/挂起卡/管理页交互细节、设计 token | §1 §3 §5 |

## 关键决策(交叉校对裁决)

三位设计师各自独立设计,以下分歧点已统一裁决:

| 议题 | 裁决 | 理由 |
|---|---|---|
| 开发期代理 | Vite proxy 用 `/api` 前缀 + `rewrite` 剥掉,`VITE_API_BASE` 按环境切换(开发 `/api`,生产空) | 六个前缀逐一透传要写六条配置且遗漏即 404;单前缀 + rewrite 一处收口。生产同源直连后端,无 CORS 问题 |
| interrupt 帧形状 | **采用后端对象信封改造**:`{"interrupt": {"kind": "ask"\|"memory", "text": "..."}}`;前端判 `kind` 而非猜 key | 前端未开工,无兼容包袱;协议自描述,消灭"把 `true` 当答案写进对话"的静默污染路径。后端同步加 `_require_interrupt` 类型校验兜底 |
| 路由 | vue-router 4 **hash 模式** | 生产形态是 FastAPI 同源挂载 SPA,history 模式的前端路径会与后端 `/memory` 等真实端点撞车,hash 彻底规避 |
| UI 库 / CSS | 无 UI 库,原生 CSS 变量 token + scoped 样式;token 采用 UI-DESIGN §5.3(深色默认 + 浅色跟随系统) | 组件量 < 20,组件库收益不抵体积与视觉主导成本;两份 token 草案以 UI 设计稿为准 |
| 视图命名 | ChatView / KnowledgeView / MemoryView / **SettingsView**(MCP+Skills+Health 三节) | UI 稿命名,ARCHITECTURE 中 SystemView 统一改称 SettingsView |
| 管理页状态 | 不进 Pinia,页面局部 `ref` + `useAsync` | 只有 chat 满足"跨路由存活 + 多组件消费"两条准入 |
| 重新生成按钮 | **不做** | 后端无"回退 checkpoint 重跑"能力,重发同文本会污染上下文;只提供"重试"(仅限请求失败/零输出情形) |
| 会话标题 | 前端本地生成(首条用户输入截 20 字,存 localStorage) | 后端列表接口保持轻量不反序列化;单用户工具够用 |
| usage 展示 | 前端相邻快照差分显示"本轮增量",累计值放次要位置 | 后端 UsageTracker 是进程级累计,直接显示会误导 |

## 后端改造清单(合并定稿,按批次)

后端红线不变:全同步、禁 async、不动 `agent/contracts/` 共享契约。所有方案细节见 API-CONTRACT.md §四。

### 第一批(阻塞前端核心功能,随 M2/M3 前完成)

| # | 项目 | 改动位置 | 改动量 |
|---|---|---|---|
| B1 | 历史消息回填端点 `GET /chat/threads/{thread_id}/messages`(含内部消息过滤 + `pending_interrupt` 挂起态回填,信封形状同 SSE) | `api/routers/chat.py` 新增只读端点 | ~30 行 |
| B2 | 会话元数据 `list_session_meta()`(纯 SQL,max(checkpoint_id) 排序,不反序列化 checkpoint)+ 端点 `GET /chat/threads/meta`;**不改** `list_session_ids()`(REPL 依赖) | `settings/db/checkpointer.py` + `chat.py` | ~25 行 |
| B3 | interrupt 对象信封 `{kind, text}` + `/chat/confirm`、`/chat/answer` 加 `_require_interrupt` 类型校验(不符返 400) | `api/routers/chat.py` | ~25 行 |

### 第二批(体验改造,建议随 M3 一起做)

| # | 项目 | 改动位置 | 改动量 |
|---|---|---|---|
| B4 | SSE 真流式(`queue.Queue` + worker 线程,**不违反全同步红线**)+ `error` 事件帧 + `GraphRecursionError` 打 `taskforce_error` 标记。当前实现是攒完全部帧再一次性 yield,打字机效果是假的、异常无任何信号 | 重写 `_sse_run` + `agent/service.py` 一处 return | ~45 行 |
| B5 | `usage.record()` 调用加 `err is None` 条件;`_get_app()` 加 `threading.Lock`(防快速连点竞态);顺手给 `UsageTracker` 加锁 | `chat.py` / `settings/usage.py` | ~10 行 |

### 第三批(小修,随对应管理页模块做)

| # | 项目 | 改动位置 |
|---|---|---|
| B6 | `POST /mcp/servers` 改 Pydantic 模型,name 进 body(现在是 query,反直觉;前端未开工现在改成本为零) | `api/routers/mcp.py` |
| B7 | `DELETE /knowledge/{doc_id}` 不存在时 500 → 404;`upload` 解析失败 500 → 400 | `api/routers/knowledge.py` |
| B8 | MCP name 非法 `_check_name` 抛错 500 → 422;`test` 端点 tools 返回值归一化为字符串数组 | `api/routers/mcp.py` |

### 开放项(暂不做,登记备案)

- ~~**子任务结果(ResultSummary)的前端可见性**~~ → **2026-09-18 已落地**:按当初登记的方向实现——后端补非消费 peek 端点 `GET /chat/tasks?thread_id=`(结果留给汇总轮 drain)+ 自动汇总端点 `POST /chat/summary`(以 `AUTO_NOTICE` 跑一轮,与 REPL watcher 同语义);前端 `useTaskWatch` 3s 轮询,全批完成即自动出汇总,**用户无需再问一句**。批次卡(SubagentBatchCard)随之不再需要。
- `/memory` 100 条上限、`/health` sandbox 值域不封闭:前端兜底,后端不动。

## 前端模块计划(M0~M6 摘要,详见 ARCHITECTURE.md §3)

```
M0 脚手架+proxy 打通 health ──► M1 API 层+类型镜像 ──┬──► M2 会话管理(依赖 B2)──► M3 SSE 对话流(依赖 B1/B3,建议同批做 B4/B5)──┐
                                                    ├──► M4 知识库页(依赖 B7)──────────────────────────────────────────┼──► M6 SettingsView+收尾
                                                    └──► M5 记忆页 ────────────────────────────────────────────────────┘
```

后端改造批次与前端模块的对位关系:B1/B2/B3 阻塞 M2/M3,B4/B5 决定 M3 的加载/错误 UX,B7 对应 M4。**建议节奏:先做第一批后端改造(业务代码用户誊写,Claude 写配套测试),再开 M0。**

## 下一步

1. 用户确认本方案(尤其上面"关键决策"表与改造三批次)。
2. 登记 `docs/dev/TODO.md`(模块 12 前端工作台 + 后端改造子项)与 `ROADMAP.md` §7(B3 信封属 API 层帧形状变更,需登记)。
3. 从第一批后端改造(B1~B3)开工:Claude 给完整代码+改动点清单,用户誊写;测试由 Claude 写。
4. 然后 M0 脚手架(配置类,可代写)。
