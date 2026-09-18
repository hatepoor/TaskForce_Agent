# TaskForce 开发 TODO List

> **使用规则(硬性)**:
> 1. **每次开发前先通读本文件**,确认当前进度,从第一个未勾选项继续;
> 2. 任务完成**并通过对应 DEV.md 的验收命令后**,将 `[ ]` 改为 `[x]`;
> 3. 模块完成时同步更新 [ROADMAP.md](ROADMAP.md) 总表状态(置 ✅);
> 4. 本文件只做进度追踪,任务细节以各模块 DEV.md 为准。

**当前模块**:全部模块已完成 ✅(R + 00~11);剩余收尾:演示剧本彩排 + GitHub 交付(见模块 11)

> **Web 工作台(dev/front)**:前端 12 个模块(01~12)亦已完成 ✅,进度与验收证据见 [dev/front/docs/todolist.md](../../dev/front/docs/todolist.md)。
> 生产形态:FastAPI 同源托管前端构建产物(`src/api/main.py` 条件挂载,dist 存在才挂),两条命令起步见 README「Web 工作台」。
> 注意:本机 8000 是沙箱通道(`SANDBOX_URL` 指向的 SSH 隧道),起形态 B 请换端口(如 `--port 8010`)。

---

## 模块 R 子智能体 ReAct 化改造 ✅(详见 [react-refactor-plan.md](react-refactor-plan.md))

> 2026-09-04 架构变更(ADR-0010):三子智能体统一 ReAct 工具循环,supervisor 保持结构化路由;05 已实现的管线版 retriever 作废重写;提示词 4 件已重写完成。

- [x] T1 kb_search 工具封装(tools/rag/kb_search.py)+ tests/test_kb_search.py
- [x] T2 共享 ReAct 骨架 agent/subagents/react.py(fake 冒烟,不接主图)
- [x] T3 retriever 重写(循环 + finalize + hits 形状)+ test_retriever.py 重写
- [x] T4 全图接线(build.py 挂真子图 + test_graph 回归)
- [x] T5 循环上限落地(达上限 partial;retriever=5)
- [x] T6 无命中 need_clarification 语义回归(不调收尾 LLM)
- [x] T7 service.py 流式白名单(真模型 bind_tools 探针与 REPL 泄漏实证并入 T8)
- [x] T8 真模型端到端验收(黄金剧本:探针 + 上传→提问→引用 + 库外问题诚实)
- [x] T9 文档同步收尾 + ROADMAP 置 ✅

---

## 模块 00 脚手架与基础设施 ✅(详见 [00-bootstrap/DEV.md](00-bootstrap/DEV.md))

- [x] T1 目录骨架与配置文件(六包 + `__init__.py` + 全部占位文件)
- [x] T2 pyproject 改写 + `uv sync`
- [x] T3 `docker compose up -d` 起 PG + 填写 `.env`
- [x] T4 实现 `settings/config.py`(Settings + get_settings + assert_ready)
- [x] T5 实现 `settings/db/base.py`(get_conn + ensure_vector_ext 幂等)
- [x] T6 ruff 验证(`uv run ruff check .`)
- [x] T7 pytest 骨架验证(tests/test_smoke.py:config 加载 + 缺失报错)
- [x] 整模块验收(config 正常读取 llm_model / 扩展幂等)+ ROADMAP 置 ✅

## 模块 01 最小对话闭环(最小 demo)✅(详见 [01-minimal-agent/DEV.md](01-minimal-agent/DEV.md))

- [x] `agent/build.py`:`make_llm()` + `build_graph()`(单节点 chat 图)
- [x] `agent/service.py`:`run_turn()`(单轮业务层,流式回调)
- [x] `settings/usage.py`:`UsageTracker` usage 打点
- [x] `cli/repl.py`:REPL 流式输出 + 基础斜杠命令
- [x] `tests/test_minimal.py`:fake model 单测(3 passed)
- [x] 整模块验收(REPL 一问一答 + usage 打点 + 记忆断裂实验)+ ROADMAP 置 ✅

## 模块 02 会话持久化 + CLI 骨架 ✅(详见 [02-persistence-cli/DEV.md](02-persistence-cli/DEV.md))

- [x] `settings/db/checkpointer.py`:PostgresSaver 工厂(连接池 + setup 幂等;3.x 需自建 ConnectionPool + autocommit)
- [x] `settings/session.py`:`SessionStore`(thread_id 本地持久化)
- [x] REPL 接入 thread_id + `/new` `/resume` `/stats` `/help` `/quit` 命令注册表
- [x] 重启自动恢复验收(重启进程直接问"我叫什么"答对)
- [x] 整模块验收(会话切换/恢复/重启续聊/usage 出数)+ ROADMAP 置 ✅

## 模块 03 多智能体骨架(契约冻结)✅(详见 [03-graph-skeleton/DEV.md](03-graph-skeleton/DEV.md))

- [x] T1 `settings/loader.py` + `prompts/supervisor.md` + `prompts/answer.md`
- [x] T2 contracts 三契约(Route/Task、TaskContract、ResultSummary)
- [x] T3 AgentState 扩展(contract/subagent_results 共享键 + 哨兵 reducer)+ supervisor 节点(全量 messages + 回退;recursion_limit 兜底,ADR-0009)
- [x] T4 桩子图(真实编译 StateGraph)+ 主图六节点重构(共享键直挂,先跑 ADR-0009 §5 第 0 步实验)
- [x] T5 answer 消费即清(全量 messages + 子结果进消息流)
- [x] T6 fake model 全图接线测试(后续所有模块的回归基线)
- [x] T7 REPL 接入新图 + 路由轨迹打印
- [x] 整模块验收 + ROADMAP 置 ✅

## 模块 04 RAG 内核 + 知识库管理 ✅ 支线(详见 [04-rag/DEV.md](04-rag/DEV.md),仅依赖 00)

- [x] 文档解析(pypdf / python-docx)+ RecursiveCharacterTextSplitter 切块
- [x] `tools/rag/store.py`:RAGStore(建表 / upload / search top-5 / delete / list_docs)
- [x] `tests/test_rag.py`
- [x] 整模块验收 + ROADMAP 置 ✅

## 模块 05 检索子智能体 ✅ 按模块 R ReAct 模式完成(详见 [05-retriever-subagent/DEV.md](05-retriever-subagent/DEV.md),依赖 03+04)

> ⚠️ 2026-09-04 架构变更(ADR-0010):本模块改按 ReAct 模式实施;下列任务由模块 R 对应项承接(T1→R-T1/T3,T2/T3→R-T3,T4→R-T4/T7/T8),整模块验收并入 R-T8。

- [x] retriever 子图(收任务契约 → RAGStore 检索 → 回结果摘要)← 已按三节点管线实现,**作废,由 R-T3 重写**
- [x] `prompts/base.md` + `prompts/subagents/retriever.md` ← 已按 ReAct 语义重写(2026-09-04)
- [x] REPL `/kb upload|delete|list` 命令
- [x] `tests/test_retriever.py` ← 管线版,**作废,由 R-T3 重写**
- [x] 整模块验收 + ROADMAP 置 ✅(并入 R-T8)

## 模块 06 长期记忆 + 统一 HITL ✅(详见 [06-memory-hitl/DEV.md](06-memory-hitl/DEV.md),依赖 02+03,全项目风险最高,严格按 T1→T6 顺序)

- [x] T1 Store 工厂(PostgresStore + pgvector,插查删 roundtrip)
- [x] T2 记忆检索 + agents.md(按 ADR-0011 重构:agents.md 固定 system 缓存;记忆改 memory_search/store_memory 工具,answer 侧按需调用,不再注入 system)
- [x] T3 显式写入(仍无 interrupt)
- [x] T4 ask 问询(第一个 interrupt,REPL 内测通)
- [x] T5 确认写入(第二个 interrupt)
- [x] T6 `/memory` 命令 + 全量回归
- [x] 整模块验收(演示剧本三幕 + 单一挂起点断言)+ ROADMAP 置 ✅

## 模块 07 Skills 渐进式加载 ✅ 支线(详见 [07-skills/DEV.md](07-skills/DEV.md),核心依赖 01,T2 需 03)

- [x] T1 SkillRegistry 扫描与解析
- [x] T2 元数据接入主图提示词 `$skills_meta`(03 未完成则顺延)
- [x] T3 `/skills` 命令 + 示例 Skill
- [x] 整模块验收(token 增量检查:元数据 26 tok vs 全文 134 tok)+ ROADMAP 置 ✅

> 2026-09-09 附带重构:repl.py 原子化拆分为 `cli/context.py`(ReplContext)+ `cli/streaming.py`(StreamRenderer)+ `cli/commands/`(斜杠命令按域一个文件,统一签名 cmd(args, ctx));技能渲染函数 render_skills_meta/_skills_meta 下沉 `tools/skills/loader.py`(避免 agent 内 supervisor<->answer 循环 import)。

## 模块 08 MCP 接入 ✅ 支线(详见 [08-mcp/DEV.md](08-mcp/DEV.md),仅依赖 01)

- [x] `tools/mcp/client.py`:MCP 工具提供器(langchain-mcp-adapters + 失败降级告警;含两层描述 + 索引 token 告警)
- [x] `mcp_config.json` schema 定稿(tools/mcp/config.py:pydantic union 模型,stdio + streamable-http 双协议)
- [x] `tests/test_mcp.py`(本地 echo fixture 冒烟,含 stdio/http 连接、超时降级、一坏一好、两层描述,15 个用例)
- [x] 整模块验收(REPL 冒烟:add/test/list 降级/remove 全流程)+ ROADMAP 置 ✅

> 2026-09-10 范围扩展(用户要求):原 DEV 范围外"远程 MCP 不做"提前落地——MCPServerConfig 改 union 模型(StdioServer/HttpServer),client 的 model_dump 直透 adapters,远程 streamable-http 与本地 stdio 同一条连接路径;测试以本地起 streamable-http echo 服务器真实冒烟。

## 模块 09 执行智能体 + 沙箱接入 ✅(详见 [09-executor-sandbox/DEV.md](09-executor-sandbox/DEV.md),依赖 03+07+08)

- [x] `tools/sandbox/client.py`:沙箱工具组 execute_python/write_file/read_file/list_files(协议实测对齐,session_id 契约变更已登记 ROADMAP §7)
- [x] `tools/tool/files.py`:内置文件工具(read_file/write_file/list_files,包装沙箱 client)
- [x] executor ReAct 子图 + `prompts/subagents/executor.md`(T2/T3:warnings 强制列执行侧效应,从 tool_calls 收集)
- [x] `tests/test_executor.py`(6 用例:成功流 warnings/partial 上限/内置工具装配;真沙箱冒烟在 test_sandbox.py skipif)
- [x] 整模块验收(真模型 REPL:CSV 统计=166 全链路 + MCP 能力对主智能体可见(mcp_meta 注入 answer))+ ROADMAP 置 ✅

> 2026-09-10 设计补强:MCP 工具仅装配进 executor 子图、主智能体不可见(问"mcp 有哪些"答不上)→ mcp_meta()(lru_cache+三态语义)注入 answer 提示词;三态语义坑与 uvx 冷启动超时见 troubleshooting/09。

## 模块 10 调研智能体 + 并行派发 🔲(详见 [10-research-parallel/DEV.md](10-research-parallel/DEV.md),依赖 03)

- [x] research ReAct 子图(web_search 工具搜-评-再搜,复用 R 共享骨架;含 T3 上下文膨胀闸门共享骨架落地;详见 10-DEV)
- [x] Send 多任务 fan-out(supervisor 一次派多个 Task + 线程池并行;MAX_PARALLEL_SUBAGENTS=3 双约束)
- [x] `prompts/subagents/research.md`
- [x] `tests/test_research.py`(并行合并断言 + 闸门用例;test_graph 补多 Send/clamp/三任务 fan-in 断言)
- [x] 整模块验收 + ROADMAP 置 ✅(真模型黄金剧本:dispatch 并行 + answer 汇总;期间修复 .env 键大写规范/Settings 字段补漏/anysearch 网络抖动)

> 2026-09-11 架构变更(异步派发方案 A):dispatch 不再同步 Send 阻塞主图——supervisor 把任务提交 `agent/tasks.py` 的 TaskManager(线程池 + 懒构建子图),立即返回"已派发"确认消息并 END,用户可继续交互;后台完成的 ResultSummary 由 supervisor 每轮 `drain_done()` 原子回收注入,answer 消费即清。同步 Send 通道在 tasks=None 时保留为备胎(build_graph 可注入 fake 供测试)。

## 模块 11 FastAPI 6-router + 收尾 ✅(详见 [11-api-finalize/DEV.md](11-api-finalize/DEV.md),依赖 02+05~10)

- [x] `api/main.py` + 六个 router(chat SSE 流式 / knowledge / memory / skills / mcp / health,list 见 DEV.md)
- [x] interrupt 恢复的 HTTP 端点映射(/chat/confirm + /chat/answer,挂起检查 + resume 透传,与 REPL 同语义)
- [x] 全量回归 + README + 演示剧本(159 passed + ruff 全绿;README 含架构图/起步/刻意不做/五道设计决策;demo-scripts 5 条剧本)
- [x] 整模块验收 + ROADMAP 置 ✅

> 2026-09-11 实施备注:chat SSE 与 REPL 共用 run_turn(_sse_run 事件攒集逐条 yield);TypeAdapter 解析 MCP 配置 union(discriminator);knowledge 局部 import 改顶层(测试可 monkeypatch);B008 入 per-file-ignores(FastAPI 惯用)。

> 2026-09-12 追加(异步主动汇总):TaskManager 加 on_done 回调唤醒 REPL watcher 线程;turn_lock 互斥实现"用户询问优先、答完自动汇总";输出走清行协议(\r\x1b[2K 擦提示行 + 汇总后重印)。期间修复两个实测 bug:节点局部注入未写回主图(troubleshooting/common #3,严重)、sandbox_meta 判断键与 /health 真实形状不符(troubleshooting/09 #3)。

> 2026-09-18 追加(Web 侧主动汇总闭环,用户报"子智能体结果回来后主智能体不主动回答,要再问一次"):REPL 有 watcher,API/前端没有等价机制,结果只能等下一轮用户轮被 `drain_done` 回收。修复——① `agent/tasks.py`:结果带**会话线程归属**(`submit(jobs, thread_id)`、`drain_done/has_done` 可按线程过滤,多线程不串),`on_done` 改**全批完成才触发**(修 REPL 半批先汇总),新增**非消费 peek** `status(thread_id)`;② `agent/supervisor.py`:supervisor 节点接 LangGraph 注入的 `config` 取 `thread_id`,`build.py` 节点 lambda 同步加形参;③ `AUTO_NOTICE` 从 `cli/repl.py` 上移到 `agent/service.py`(双入口同一触发语);④ `api/routers/chat.py`:`GET /chat/tasks`(peek)+ `POST /chat/summary`(以 AUTO_NOTICE 跑一轮,守卫无结果返 400),历史回填过滤 `(系统通知)` 前缀,**零 token 轮(派发确认/记忆确认)整段补发 token 帧**(此前 Web 侧只剩"无文本输出"兜底文案);⑤ 前端 `useTaskWatch` 3s 轮询(可见性/KeepAlive 暂停、15 分钟上限、用户轮优先、切会话不代汇总),全批完成自动开汇总轮(不插用户气泡),`ThreadMeta.awaitingTasks` 随本地元数据持久化(刷新后继续等)。验收:后端 216 passed + ruff 全绿(httpx 探针跑通 派发→peek→汇总→0/0 清位 全链),前端 vitest 167/167 + vue-tsc + build 通过,headless 浏览器探针实测"只输入一次,12s 后汇总自动出现、输入框为空"。契约未动,FE 开放项(dev/front/docs README §开放项 / UI-DESIGN §7.2)标记为已落地。

> 2026-09-18 追加(设置页"模型"节,用户提需求):可在设置里配置主模型与 Embedding 的 base_url / api_key / 模型名,提示走 **OpenAI 兼容协议**。实现——① 新建 `settings/model_overrides.py`:覆盖表落 `.taskforce/model_config.json`(与 `session.py` 同目录,gitignore 已含),`.env` 仍是默认值来源、**不写回 .env**;② `settings/config.py` 在 `get_settings()` 里叠加覆盖(进程启动时读一次 → **保存后重启生效**),新增 `applied_overrides()`(启动快照)与 `effective_config()`(`.env` + 覆盖表 = 重启后口径,表单编辑对象);③ 新建 `api/routers/model_settings.py`:GET/PUT `/models/config`,**api_key 只回掩码**(前后各 4 位,原文不出网关),PUT **只发改动项**(缺项=不动、空串=清除覆盖回落 `.env`、掩码回传=保持不动),`base_url` 非空必须 http(s);④ 前端设置页第 4 节(路由 `…|models`):两张卡 + 协议提示 + "重启后端生效"横幅 + 每卡"恢复 .env 默认"。**验收期发现并修掉两处首版缺陷**:全量提交会把未改动的 `.env` 值复制成覆盖(日后改 `.env` 被静默压住)、GET 返回运行中值导致保存后输入框被旧值盖回。验收:后端 `tests/test_model_settings.py` 12 条、全量 **236 passed** + ruff 全绿;前端 vitest **176/176** + vue-tsc + build;headless 探针实测(掩码/改一项/重启横幅/恢复默认/落盘只含改动项/零未捕获异常),测试期间写入的覆盖表已清空为 `{}`。

---

## 优化 01:RAG 混合检索(BM25 + 向量 · 方案 A)

> 2026-09-14 起。纯 pgvector → 双路召回 + RRF 融合,改造封闭在 RAGStore 内。方案/任务/进度唯一事实源:**[docs/improved/rag_improve_v1/TODO.md](../improved/rag_improve_v1/TODO.md)**(本区仅同步状态)。

- [x] 模块 01 依赖与分词(tokenize,5 passed)
- [x] 模块 02 Bm25Index + rrf_fuse(含 SafeBM25Okapi 负 idf 修复,12 passed)
- [x] 模块 03 store.py 双路融合(29 passed,真实库 roundtrip)
- [x] 模块 04 契约登记与文档同步(本区即登记产物,ROADMAP §7 已登记)
- [x] 模块 05 评测集与全量回归(8 篇文档 9 条查询,hybrid ≥ 纯向量全部成立;全量 191 passed)
