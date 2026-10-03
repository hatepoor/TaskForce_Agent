# TaskForce 开发路线图(ROADMAP)

> 本文档是**开发进度的唯一事实源**。设计意图见 `docs/design/DESIGN.md`,上下文与提示词设计见 `docs/design/PROMPT-DESIGN.md`,架构决策见 `docs/adr/`,术语见根目录 `CONTEXT.md`。
> 状态图例:🔲 未开始 | 🔨 进行中 | ✅ 完成 | ⏸ 阻塞(注明原因) | ♻️ 返工

## 1. 模块总表

| 编号 | 模块 | 文档 | 依赖 | 状态 | 工时 | 备注 |
|---|---|---|---|---|---|---|
| 00 | 脚手架与基础设施 | [DEV.md](00-bootstrap/DEV.md) | - | ✅ | 2h | config/db/联调全部验收通过 |
| 01 | 最小对话闭环(**最小 demo**) | [DEV.md](01-minimal-agent/DEV.md) | 00 | ✅ | 3h | 单节点图 + REPL 流式 + usage;get_state 无 checkpointer 崩溃已修(chunk 攒整兜底) |
| 02 | 会话持久化 + CLI 骨架 | [DEV.md](02-persistence-cli/DEV.md) | 01 | ✅ | 3h | checkpointer / thread_id / /new /resume /stats;3.x 需自建 ConnectionPool(autocommit);2026-09-04 决议:启动改开新会话(旧会话 /resume)+ /list_session |
| 03 | 多智能体骨架(**契约冻结**) | [DEV.md](03-graph-skeleton/DEV.md) | 02 | ✅ | 3h | 七节点图 + Send 并行 + 消费即清 + recursion_limit 兜底;实测修正:Send 须包 Command(goto=[])、主图移除 contract 共享键(并行冲突)、supervisor 注入桩结果防乒乓(见 troubleshooting/03) |
| 04 | RAG 内核 + 知识库管理 | [DEV.md](04-rag/DEV.md) | 00 | ✅ | 4h | parse/split/embed/RAGStore/pgvector;维度断言实测生效;psycopg3 executemany 须在 cursor 上 |
| R | **ReAct 架构改造(插队,最高优先级)** | [react-refactor-plan.md](react-refactor-plan.md) | 03, 04 | ✅ | 8h | T1-T9 全部完成:kb_search/react.py/retriever 重写/service 白名单;实测修正:直挂同键名即共享,子图消息键改 react_msgs(ADR-0010 红线 2);T8 真模型黄金剧本验收通过(隔离库 hits=11);51 tests 全绿 |
| 05 | 检索子智能体 | [DEV.md](05-retriever-subagent/DEV.md) | 03, 04 | ✅ | 3h | 第一个真实子图(ReAct 循环 + kb_search),按模块 R ReAct 模式完成(原三节点管线作废重写) |
| 06 | 长期记忆 + 统一 HITL | [DEV.md](06-memory-hitl/DEV.md) | 02 | ✅ | 7h | ADR-0011 重构后落地:固定 system + 记忆工具化(memory_search/store_memory);ask/memory 双 interrupt 全链路 + /confirm 重启可恢复;5 条实踩坑位沉淀(流式 JSON 泄漏等) |
| 07 | Skills 渐进式加载 | [DEV.md](07-skills/DEV.md) | 01, 03 | ✅ | 2h | SkillRegistry(frontmatter 解析/重名报错/失败跳过)+ $skills_meta 注入 supervisor 与 answer 两侧 + /skills 命令;附带 REPL 原子化拆分(context/streaming/commands) |
| 08 | MCP 接入 | [DEV.md](08-mcp/DEV.md) | 01 | ✅ | 3h | 两层描述 + 单服务器失败降级;范围扩展:union 模型支持 stdio + streamable-http 双协议(远程 MCP 提前落地);REPL 冒烟全流程通过 |
| 09 | 执行智能体 + 沙箱接入 | [DEV.md](09-executor-sandbox/DEV.md) | 03, 07, 08 | ✅ | 5h | 沙箱工具组(协议实测对齐,无 session_id)+ executor ReAct 子图(三层工具装配 + warnings 执行效应)+ mcp_meta 注入 answer;真模型 CSV 统计=166 全链路验收通过 |
| 10 | 调研智能体 + 并行派发 | [DEV.md](10-research-parallel/DEV.md) | 03 | ✅ | 7h | web_search 直连 AnySearch API(替代 ddgs,snippet 截断内聚工具内);research ReAct 子图(搜-评-再搜,8 轮上限 + 16k 字符上下文闸门进共享骨架);Send 多任务 fan-out(MAX_PARALLEL_SUBAGENTS=3 提示词+代码双约束,recursion_limit 25→40);真模型黄金剧本验收;2026-09-11 异步派发(方案 A):dispatch 改 TaskManager 后台线程,主图不再阻塞 |
| 11 | FastAPI 6-router + 收尾 | [DEV.md](11-api-finalize/DEV.md) | 02, 05-10 | ✅ | 5h | 六 router(chat SSE / knowledge / memory / skills / mcp / health);HITL 恢复端点;159 测试 + ruff 全绿;README(架构图/起步/刻意不做/五道设计决策)+ .env.example + 5 条演示剧本 |

合计约 **47h**(不含演示打磨)。**按编号 00->11 顺序执行即天然满足全部依赖**;04 / 07 / 08 是可插空支线。

## 2. 模块依赖图

```mermaid
flowchart TD
    M00[00 脚手架] --> M01[01 最小对话闭环 demo]
    M01 --> M02[02 会话持久化+CLI]
    M02 --> M03[03 多智能体骨架 契约冻结]
    M00 -.支线.-> M04[04 RAG 内核]
    M03 --> M05[05 检索子智能体]
    M04 --> M05
    M02 --> M06[06 长期记忆+HITL]
    M01 -.支线.-> M07[07 Skills]
    M03 -.提示词接入.-> M07
    M01 -.支线.-> M08[08 MCP]
    M03 --> M09[09 执行智能体+沙箱]
    M07 --> M09
    M08 --> M09
    M03 --> M10[10 调研智能体+并行派发]
    M02 --> M11[11 FastAPI+收尾]
    M05 --> M11
    M06 --> M11
    M09 --> M11
    M10 --> M11
```

主线(严格串行):`00 -> 01 -> 02 -> 03 -> 05 -> 06 -> 09 -> 10 -> 11`;支线 04/07/08 挂在主链早期节点上,任意穿插。

## 3. 最小 demo 路径(用户硬要求)

**定义**:依赖装好、LLM 连上,在 REPL 输入一条消息并收到流式回复,usage 有打点。无子图、无记忆、无 RAG、无 API。

**最快路径**:`git clone -> uv sync -> 填 .env(LLM 三件套)-> 模块 00(2h)-> 模块 01(3h)-> REPL 第一条消息`。约 **5 小时**;环境顺利(LLM key 就绪、跳过 DB 部分,PG 留到 02)可压到 **3.5 小时**。后续模块只在此之上叠加,不重构这条链。

## 4. 并行/串行调度

- **绝对串行**:`00 -> 01 -> 02 -> 03`(约 11h)。这是全部后续工作的地基与契约冻结点。
- **契约冻结(03)之后**:05/06/09/10 可按任意顺序推进(编号序即推荐序)。
- **可插空支线**:04(仅依赖 00)、07(核心依赖 01,提示词接入需 03)/08(仅依赖 01)、09 的 sandbox 客户端、10 的 research 循环核心。遇到外部阻塞(等 API key、等沙箱部署、MCP 联调)时优先推支线,**主线永远不阻塞在外部依赖上**。

## 5. 与原四阶段里程碑的映射

| 原阶段 | 模块 | 工时 |
|---|---|---|
| 阶段 1 地基+单智能体 | 00 + 01 + 02 | 8h |
| 阶段 2 RAG+检索子智能体 | 03 + 04 + 05 | 10h |
| 阶段 3 记忆+HITL+Skills+MCP+沙箱 | 06 + 07 + 08 + 09 | 17h |
| 阶段 4 调研+并行+收尾 | 10 + 11 | 12h |

## 6. 契约归属表(一契约一定义处,其余一律 import)

| 契约 | 定义模块 | 定义位置 | 消费模块 |
|---|---|---|---|
| `Settings` / `get_settings()`(LLM/Embedding/DB/沙箱配置 + 启动断言) | 00 | `settings/config.py` | 全部 |
| psycopg 连接辅助(幂等建扩展) | 00 | `settings/db/base.py` | 04, 06 |
| `build_graph(llm, checkpointer)` / `make_llm()`(图的唯一构建入口) | 01 | `agent/build.py` | 01-10、11 |
| `run_turn()`(单轮业务层,CLI 与 API 共用) | 01 | `agent/service.py` | 02+、11(SSE 包装) |
| `UsageTracker`(usage 打点与 /stats) | 01 | `settings/usage.py` | 02+、11 |
| checkpointer 工厂(连接池 + setup 幂等) | 02 | `settings/db/checkpointer.py` | 03+、11 |
| `SessionStore`(thread_id 本地持久化) | 02 | `settings/session.py` | 02、11 |
| `AgentState`(messages + subagent_results reducer) | 03 | `agent/state.py` | 03, 05, 09, 10, 11 |
| `Route` / `Task`(结构化路由 schema) | 03 | `agent/contracts/route.py` | 03 |
| `TaskContract`(任务契约四件套类型) | 03 | `agent/contracts/task_contract.py` | 03(构造)、05/09/10(消费) |
| `ResultSummary`(结果摘要 schema) | 03 | `agent/contracts/summary.py` | 03(answer 读/清)、05/09/10(写) |
| interrupt 载荷与合成消息前缀(`ask_payload`/`classify_interrupt`/`PREFIX_*`) | 03→contracts | `agent/contracts/interrupt_payload.py`(2026-09-23 c5 新增,见 §7) | 06(ask/memory 节点)、11(/chat)、cli/repl、service.AUTO_NOTICE |
| `build_contract()`(会话 -> 契约的纯函数) | 03 | `agent/supervisor.py` | 03 内部(dispatch) |
| `load_prompt(name, **slots)`(md 提示词加载与渲染) | 03 | `settings/loader.py` | 03+、05、06、09、10 |
| RAG 内核接口(检索 `ingest/search` + 管理 `list_docs/upload/delete_doc`,全走 facade) | 04→**rag_v01** | `src/rag_v01/__init__.py`(管理面 2026-09-23 收编,见 §7)/ `src/rag_v01/store.py` | 05(retriever 子图)、11(/knowledge)、cli `/kb`(2026-09-22 换内核, 见 §7) |
| `kb_search(query, top_k=5)` 检索工具(去重+截断内聚;工厂 `make_kb_search` 注入 seam,2026-09-23 c6) | R | `tools/rag/kb_search.py`(适配 `rag_v01`) | 05(retriever) |
| `build_react_subgraph(...)`(ReAct 循环共享骨架) | R | `agent/subagents/react.py` | 05, 09, 10 |
| 子图装配注册表(`get_subgraph(llm, agent)` / `BUILDERS`) | 03/10→subagents | `agent/subagents/registry.py`(2026-09-23 c7 新增,见 §7) | build.py(直挂)、tasks.py(后台 invoke) |
| 长期记忆 Store 工厂(PG + pgvector) | 06 | `settings/db/store.py` | 06、11 |
| 长期记忆管理查询(`list_memories`/`delete_memory` + `MEMORY_NS` 单一出处) | 06→memory_ctx | `agent/memory_ctx.py`(2026-09-23 c4 收编,见 §7) | 11(/memory)、cli `/memory` |
| `SkillRegistry`(Skill 注册/渐进加载) | 07 | `tools/skills/loader.py` | 03(元数据注入)、09(executor) |
| MCP 工具提供器(索引常驻 + 按需详情 + 降级) | 08 | `tools/mcp/client.py` | 09(executor) |
| 沙箱工具组(`execute_python(code, timeout)` / `write_file` / `read_file` / `list_files`) | 09 | `tools/sandbox/client.py` | 09(executor)、`tools/tool/files.py` |
| 内置文件工具(`read_file`/`write_file`/`list_files`,操作沙箱工作区) | 09 | `tools/tool/files.py` | 09(executor) |
| `PlanDraft`/`PlanStepDraft`/`Plan`/`PlanStep`(计划契约,plan_0.1) | plan_0.1 | `agent/contracts/plan.py` | 03(planner 节点/推进块)、06(HITL 模式参照) |

## 7. 契约变更登记

> 任何模块要改动他人契约(签名/字段/接口)前,先在此登记,评审后再改代码。

| 日期 | 契约 | 变更内容 | 影响模块 | 状态 |
|---|---|---|---|---|
| 2026-08-31 | 全部契约路径 | 项目结构改为 src 六包布局(agent/tools/prompts/settings/api/cli),提示词改为 md 文件经 `settings/loader.py` 加载 | 全部 | ✅ 已同步文档 |
| 2026-09-01 | 主图提示词结构 | `$subagent_results` 从 supervisor 系统提示词挪到 answer 调用的消息流(前缀缓存友好);supervisor.md 仅剩 `$skills_meta`/`$memory` 两个插槽;PROMPT-DESIGN §1.1 第 6 段语义同步此登记 | 03/05/09/10 | ✅ supervisor.md 已改 |
| 2026-09-02 | 主图上下文策略 | **滑动窗口作废**(ADR-0009 R1):路由/汇总均全量保留 messages,删 SLIDE_WINDOW/sliding_messages;"压缩上下文"排入 backlog(优先级提升);过渡期 service.py 加超阈值日志告警 | 03/11 | ✅ PROMPT-DESIGN §1.2/§4.2 已标作废 |
| 2026-09-02 | 防死循环机制 | 自数步数(MAX_STEPS/route_marker/哨兵消息)作废,改用 LangGraph 原生 `recursion_limit`(config 顶层键,初值 25)+ `run_turn` 捕获 `GraphRecursionError` 返回诚实兜底消息(ADR-0009 §2 争议 B) | 03/11 | ✅ 已同步 03-DEV |
| 2026-09-02 | 子图接入方式 | 桩子图从"单函数假桩/wrapper 写死"改为**真实编译 StateGraph**;首选**共享键直挂**(`contract`/`subagent_results` 共享键 + `add_node(编译图)` + `Send(子图名, {"contract": ...})`,03 第 0 步最小实验验证);失败降级 wrapper 并登记三项代价(checkpoint 不共享/流式不保证/异常不传播);新增 `SubgraphContract` 契约与 `max_parallel_subagents`(初值 3)(ADR-0009) | 03/05/09/10 | ✅ 已同步 03/05/09/10-DEV |
| 2026-09-02 | AgentState.contract 键 | 主图**移除** `contract` 键:共享键直挂仅需 `subagent_results`;`contract` 由 Send payload 直达子图,主图不声明(实测:并行多子图写回 contract 触发 InvalidUpdateError,ADR-0009 第 0 步实验延伸发现) | 03 | ✅ 已同步 state.py |
| 2026-09-02 | ResultSummary.agent 命名 | **"retrieval" 统一为 "retriever"**(与 Route.Task.agent / 子图节点名 / supervisor.md 能力清单一致,消除同名智能体两套命名的矛盾;DEV.md/design/PROMPT-DESIGN.md 同步修正) | 03/05/10 | ✅ 已同步 summary.py / stub.py / build.py / tests / 文档 |
| 2026-09-02 | ResultSummary.task 上限 | 删除 `max_length=100`:task 是 supervisor 自由生成文本的回显,长度不可控,加会上限会在子图边界抛 ValidationError 崩掉整轮(已实测复现);`conclusion` 的 100 上限保留(决策字段) | 03/05/09/10 | ✅ 已同步 summary.py + 回归测试 |
| 2026-09-04 | 子智能体执行模式 | **三子智能体统一 ReAct 工具循环**(ADR-0010):手写循环共享骨架 `agent/subagents/react.py`(05/09/10 复用);retriever 检索能力封装为 `kb_search` 工具(去重+截断内聚),查询改写由 LLM 多轮调工具涌现;RetrieverState 增私有键 messages(add_messages)/hits/iteration;05 已实现三节点管线作废重写;supervisor 保持结构化路由不变;契约 schema 冻结不变(data={"hits":...} 行为形状保持);防失控改双层(子图自数 max_iterations + 主图 recursion_limit 兜底,ADR-0009 §2B v3 补注) | 05/09/10 | ✅ 已完成(模块 R 全量验收通过) |
| 2026-09-10 | 沙箱工具契约 | `execute_python(code, session_id)` → `execute_python(code, timeout)`:实测用户沙箱(09-DEV §1 前提"协议以实际为准")为**无状态**执行(每次新建容器),无 session_id 概念;且出参无 files 字段,文件走独立端点 `/files/write`、`/files/read`(无列目录端点,list_files 用 execute_python 跑 os.listdir 实现,实测工作区挂载进容器可见);工具组统一"不抛异常,结构化 {ok, error}"返回 | 09/11 | ✅ 已同步 ROADMAP §6 |
| 2026-09-04 | RAGStore.upload 返回值 | `str` → `tuple[str, bool]`(doc_id, created):新增内容级防重——documents 加 content_hash(解析后文本统一换行+strip 的 SHA-256)+ (user_id, content_hash) 唯一索引,重复上传复用已有文档且不再切块/向量化;存量旧数据不回填(用户决议,content_hash 为 NULL 不参与判重);消费方 rag/cli 与 REPL /kb 已同步 | 04/05/11 | ✅ 已同步 store/cli/repl/tests |
| 2026-09-04 | 主智能体上下文结构 | **固定 system + 动态 messages**(ADR-0011):① agents.md 全文/记忆 top-5/子结果从 system 移出——agents.md 只在 answer/ask 侧、构建期装配一次,记忆改 `memory_search`/`store_memory` 工具(按需调用,ToolMessage 进消息流),子结果改结构化资源消息(不再占 HumanMessage 角色);② 路由(supervisor)prompt 精简为轻量 router,不再注入 agents.md/记忆正文;③ prompt caching 从"明确不做"改"静态前缀工程化"(P0);④ store 改 `graph.compile(store=...)` 注入,user_id 入 settings | 03/06/11 + 文档 | ✅ 已同步 design/PROMPT-DESIGN §1.1/§4.2、design/DESIGN §3、ADR-0011、design/ARCH-REVIEW.md;核心已落地(固定 system + 记忆工具化 + cache 观测 + 超阈值告警,74 tests 绿,真模型端到端验证 memory_search 命中);store 注入方式与 user_id 入 settings 排 backlog |
| 2026-09-14 | RAGStore.search score 语义 | **score 从"余弦距离,越小越近"翻转为"RRF 融合分,越大越相关"**:纯 pgvector → BM25+向量双路召回 + RRF 融合(方案 A,任务见 docs/improved/rag_improve_v1/)。新增 `tools/rag/bm25.py`(tokenize 双端共用 / Bm25Index 内存索引懒加载+脏标记+双检锁 / rrf_fuse 排名并集融合);`store.search` 拆 `_search_vector`(向量路,SQL 补 `c.id AS chunk_id`)与关键词路,`rrf_fuse` 取 top_k,关键词路独占命中 `_fetch_chunks` 回填;upload/delete 后置脏(懒重建,存量零迁移)。返回 dict **新增 `chunk_id` 键**(只增不改)。消费方:kb_search 仅透传 score 零改动;cli.py 输出数字透传零改动;测试断言按新语义 | 04/05/11 + 测试 | ✅ 已同步 store.py/bm25.py/tests(29 passed)+ 本登记 |
| 2026-09-16 | chat 路由只读增量(前端支持 B1/B2) | 新增两个只读端点,不改既有契约:① `GET /chat/threads/{thread_id}/messages` 历史消息回填(graph.get_state 读 messages,过滤 `[用户回答]:`/`子智能体结果已回收` 内部合成消息,附 `pending_interrupt` 挂起信封);② `GET /chat/threads/meta` 会话元数据(settings/db/checkpointer.py 新增 `list_session_meta` 纯 SQL 聚合,max(checkpoint_id) 降序,不反序列化 checkpoint;`list_session_ids` 不动,REPL 零影响) | 11/前端12 | ✅ 已落地(tests/test_api_history.py) |
| 2026-09-16 | chat SSE interrupt 帧形状(B3,前端支持) | **数组 → 对象信封**(API 层帧变更,非 agent 契约):`{"interrupt": [{question\|proposal}]}` → `{"interrupt": {kind: "ask"\|"memory"\|"unknown", text}}`(`_interrupt_envelope`);配套 `/chat/confirm`、`/chat/answer` 加 `_require_interrupt` 挂起类型校验(不符 400——原先只查非空不查类型,判错会把 approved=True 当答案静默写进对话)。前端(dev/front)按 kind 选恢复端点;REPL 不经 `_sse_run` 零影响 | 11/前端12 | ✅ 已落地(test_api_history.py 14 用例 + test_api.py 同步修正假图挂起类型语义) |
| 2026-09-16 | chat SSE error 帧与真流式(B4/B5,前端支持) | ① SSE 事件流**新增 `error` 帧**:worker 异常时发 `{"error": {message, code?}}` 后正常关流;② `run_turn` 兜底消息语义扩展——recursion_limit 场景 `additional_kwargs={"taskforce_error": "recursion_limit"}` → error 帧带 `code`;③ 流式从"攒帧一次性 yield"改 worker 线程 + `queue.Queue` 边跑边推(全同步红线内);④ usage 帧仅正常轮发送(err is None);⑤ `_get_app` 双检锁 + `UsageTracker` 加锁。前端(05/07)据此做错误 UX 与加载态 | 11/前端12 | ✅ 已落地(test_api_history.py;curl 实测 token 帧逐条到达) |
| 2026-09-22 | **知识库内核换轨:RAGStore(pgvector) → `rag_v01`(Milvus)** | 里程碑 B 步骤 1~6。① **打包**: 新模块从 `src/new_module/rag_v01/` 挪到 **`src/rag_v01/`**(与其它六包同深度并进 `hatch packages`)—— 混深度的目录进不了 editable 安装的 `.pth`, 挪之前 `import rag_v01` 运行时必失败; ② **工具契约不变**: `kb_search` 的 JSON 契约(`doc_id/filename/seq/content/score`, content 截 500, top_k 钳 1-10)与工具名都不变(`prompts/subagents/retriever.md` 写死了这个名字, 提示词是静态前缀), 适配层从 `kb_search_v2.py` 改名回 `kb_search.py`; 变的是 `content`(父块全文 + 最佳子块, 旧的是 500 字切片)与 `score`(RRF 分, 语义方向不变); ③ **API 契约三处变更**: `doc_id` 改**内容寻址**(文件字节 sha256 前 16 位, 16 hex; 同内容重复上传必然同 id → `created: false` 据此判定)、`created_at` 恒为 `null`(新内核没有文档表, 没有上传时间)、`DELETE /knowledge/{doc_id}` 对不存在的 id 由 500 改 **404**; ④ **下线**: 删 `tools/rag/{parse,split,bm25,store,kb_search,cli}.py` 与旧测试(test_rag/test_bm25/test_rag_hybrid/test_kb_search), `embed.py` **保留**(长期记忆 `settings/db/store.py` 在用, 覆盖搬到 `tests/test_rag_embed.py`); ⑤ 消费方 `agent/subagents/retriever.py`、`api/routers/knowledge.py`、`cli/commands/knowledge.py` 同批切换 | 04/05/11/cli + 前端契约 | ✅ 已落地(主线 400 passed / 2 failed 全是远程沙箱不可达; rag_v01 203 passed; ruff 干净) |

| 2026-09-23 | embedding 客户端归属 + `get_store` 签名(架构整理 c2) | `tools/rag/embed.py` **整体下沉为 `settings/embeddings.py`**:`settings/db/store` 原反向 import `tools.rag.embed`、而后者又依赖 `settings.config`,形成 settings↔tools 包级循环,打穿"tools→settings"单向依赖(2026-09-22 登记中"embed.py 保留"一句由此替代);`get_store(database_url, embed=None)` 新增可选 embed 注入,缺省仍用 settings 版真实客户端,注入时向量维度由该函数实测(测试免真实 key);`tools/rag` 只剩 `kb_search` 适配层 | 06/11 + tests | ✅ 已同步代码 |

| 2026-09-23 | `build_executor_graph` 签名(架构整理 c3) | `build_executor_graph(llm)` → `build_executor_graph(llm, tools=None)`:缺省才调 `_gather_tools()`(原 build 期调用两次 → 一次,MCP 连接发现双倍支付与"meta/bind_tools 两批可能不一致"风险一并消除);`tools` 显式注入时提示词工具索引 meta 与 bind_tools 的工具集与注入列表同源;tests/test_executor 改为注入内置工具/假工具,不再 monkeypatch 私有符号 | 03/09/11 + tests | ✅ 已同步代码 |
| 2026-09-23 | rag_v01 管理面 + memory_ctx 管理查询(架构整理 c4) | ① facade 新增 `list_docs()`(定型条目+文件名排序)、`upload(content, filename)`(收编 20MB 上限/判重快照/带原名临时落盘/created 判定, 返回 `{ok,error,doc_id,created,name}`)、`delete_doc(doc_id)->bool`(不存在返 False, 404 文案留入口)、常量 `MAX_UPLOAD_BYTES`(自 api/routers/knowledge 下沉);② `agent/memory_ctx` 新增 `list_memories()/delete_memory()` 与 `MEMORY_NS/LIST_LIMIT`, namespace 字面量 ("memory","default") 双入口三处重复收编为单一出处;③ api/cli 的 knowledge、memory 四入口退化纯渲染(CLI 上传从此同受 20MB 上限, 消除已现漂移);HTTP 状态码与文案仍归各入口 | 11/cli + tests | ✅ 已同步代码 |

| 2026-09-23 | interrupt 载荷契约 + 合成消息前缀常量(架构整理 c5) | 新增 `agent/contracts/interrupt_payload.py`:`InterruptKind`(ask/memory/unknown)、`InterruptPayload{kind,text}`、构造器 `ask_payload/memory_payload`、识别器 `classify_interrupt`(kind 优先, 兼容旧检查点 question/proposal 键名形状, 未知给 unknown 不静默);前缀常量 `PREFIX_USER_ANSWER`("[用户回答]:")/`PREFIX_SUBAGENT_RESULT`("子智能体结果已回收")/`PREFIX_SYSTEM_NOTICE`("(系统通知)")与 `SYNTHETIC_USER_PREFIXES` 收编单一出处。② ask/memory 节点按契约构造载荷(**载荷加 kind 字段**, 存量检查点经 classify 兼容不迁移);③ api/chat 三处键名探测与 cli/repl 分发改直读 kind(未知挂起不再静默落入问询, 显式告警);④ 前缀字面值不变(提示词引用与存量消息零影响), `service.AUTO_NOTICE` 改由前缀常量拼接 | 03/06/11/cli + tests | ✅ 已同步代码 |

| 2026-09-23 | kb_search 工厂 seam + retriever 注入签名(架构整理 c6) | ① `kb_search` 由模块级单例改为工厂 `make_kb_search(search_backend=None)`(缺省后端 `_default_search` 仍惰性转调 rag_v01.search;**工具名与 ToolMessage JSON 五键契约不变**);② 新增 `hit_key(item)`,`(doc_id, seq)` 去重键定义与 seq 提取同居 `tools/rag/kb_search.py`(`_collect_hits` 改调 hit_key);③ `build_retriever_graph(llm, search_backend=None)` 显式注入后端;tests 改为工厂注入假件, 删除 test_retriever 裸赋值 + autouse 还原 hack(实测假件泄漏事故就此根除) | 05/11 + tests | ✅ 已同步代码 |

| 2026-09-23 | 子图装配唯一出处(架构整理 c7) | 新增 `agent/subagents/registry.py`:`BUILDERS` + `get_subgraph(llm, agent)`(按 llm 强引用缓存、按 agent 惰性编译, 同 llm 同 agent 只编译一次);`build_graph` 直挂与 `TaskManager._subgraph` 后台 invoke 经注册表取**同一批**实例, 消除双份装配与双倍 MCP 发现冷启动;`tasks._BUILDERS` 模块字典并入 registry;Send 备胎通道与 ADR-0009 双通道语义不变;TaskManager 懒构建语义保留(未派发的 agent 仍不编译) | 03/10/11 + tests | ✅ 已同步代码 |
| 2026-09-24 | Plan 系契约 + Route.next 扩展 + AgentState.plan(plan_0.1 Plan-and-Execute) | ① 新增 `agent/contracts/plan.py`:`PlanStepDraft/PlanDraft`(LLM 输出形状,`validate_structure` 四规则——id 格式 `^s\d+$` 且唯一/依赖存在/只向前引用防环/1~5 步)+ `PlanStep/Plan`(运行时形状:status/task_id/result_digest 为代码维护的运行时字段;行为方法 ready_steps/mark_by_task/cascade_skip/snapshot/finished);② `Route.next` Literal 加 `"plan"`(Literal 加值向后兼容,旧 checkpoint 不受影响);③ `AgentState` 新增 `plan: dict \| None`(存 model_dump 同 last_route 先例,plan_draft/plan_confirm/supervisor 推进块单点写,无 reducer);④ **ResultSummary 无变更**(task_id 已有 summary.py:22,对账靠派发时回填 PlanStep.task_id);⑤ interrupt 载荷新增 `plan_payload`(kind="plan",挂起点清单经 ADR-0012 扩为 ask/memory/plan_confirm) | 03(supervisor 推进)/06(HITL 同款)/11(HITL 恢复端点复用) + tests | 🔨 方案定稿(docs/new_module/plan_0.1/),代码按其 TODO.md 誊写 |
| 2026-10-03 | AgentState.contextDigest 键(agent_opt_0.1 P4 上下文分层) | 新增 `contextDigest: dict`(=`{"digest","uptoId"}`,**水位制定稿式压缩**,方案见 docs/new_module/agent_opt_0.1/05-上下文分层.md):存储层 messages 全量 append-only 永不删改;视图层 supervisor/answer 发 LLM 前确定性拼装(固定 system + digest + 水位后消息),**prefix cache 命中率不降为硬约束**;单点写=answer(supervisor 只读),digest 绝不写进 messages channel;子图不声明同名键 | 03(supervisor/answer 拼装)+ tests | ✅ 已落地(2026-10-03,496 passed;缓存命中率冒烟待跑) |
| 2026-10-03 | ResultSummary.report 字段 + conclusion 上限(agent_opt_0.1 P0 成稿回传,M0 登记) | `contracts/summary.py`:ResultSummary 加 `report: str = Field(default="")`(子图收尾 JSON 的完整成稿原样回传,answer 汇总优先消费;空串=旧协议回退 evidence 渲染);`conclusion` max_length 100→200(2026-09-28 用户裁决),契约/代码截断/三子图提示词三处同步;旧 checkpoint 缺字段反序列化得默认值,向后兼容 | 05/09/10(三子图)+ 06(answer)+ tests | ✅ 已落地(2026-10-03,496 passed;URL/KB 效果冒烟待跑) |

## 8. 开发原则(硬性)

1. **循序渐进**:严格按依赖链推进,不跳级;依赖未完成的模块不开工。
2. **每步可运行**:模块文档每个任务都有验收命令,任何中间态系统都能启动/测试。
3. **契约先行**:03 冻结 contracts 之前,05/06/09/10 只做骨架不写业务逻辑;改契约必须走 §7 登记。
4. **全同步**:禁止引入 async/await;SSE 用同步 generator(design/DESIGN.md §1)。
5. **共用业务层**:REPL 与 FastAPI 调同一 `run_turn`/`build_graph`(均在 `agent/` 包),不出现第二套实现。
6. **提示词外置**:提示词一律放 `prompts/` 的 md 文件,经 `load_prompt()` 加载,禁止内联在节点代码。
7. **测试伴随**:每模块产出物含 tests/;验收命令即 `uv run pytest ...`。

## 9. 排序风险与规避(开发顺序层面的坑)

1. **契约未冻结就开子图(最高风险)**:任务契约与结果摘要是子图唯一接口,先变更后开工会全线返工 -> 03 用桩子图验证全链路后再冻结,之后才开真实子图。
2. **dispatch 后期才引入 Send(结构性返工)**:若 03 实现成普通节点调用、10 才改 Send + reducer,状态设计与线程安全都要重写 -> **03 从第一天就用 Send 通道 + `operator.add` reducer,哪怕一次只派一个任务**。
3. **interrupt 恢复路径拖到 API 阶段才验证**:会在 SSE + HTTP resume 复合出难查的 bug -> 06 在 REPL 里把挂起->恢复(自由文本 + /confirm)全部测通,11 只做端点映射。
4. **psycopg 连接跨线程共享**:Send 并行分支共享单连接会崩 -> 02 建连接层即按"每路径独立取连接"设计。
5. **pgvector 维度与 embedding 不一致**:建表即错 -> 00 建表时 `vector(N)` 的 N 由 config 决定,04 落 embedding 时启动断言强制校验。
6. **外部依赖不可控(沙箱/MCP)**:沙箱冒烟未配置自动 skip;MCP 单服务器失败降级告警;联调排成支线,主线不等待。
7. **06 工时虚高**(记忆+HITL 是风险最高的模块):按"显式写入(无 interrupt)-> ask 问询(interrupt)-> 确认写入(interrupt)"三步内部分解,每步可跑可测,不要一口气做完。
