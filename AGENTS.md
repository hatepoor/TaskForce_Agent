# AGENTS.md -- 编码智能体工作区指令(TaskForce 开发侧)

> 面向编码智能体(ZCode、Claude Code 等)的开发者指令,每次会话自动加载。**本文件是指令的单一事实源**(CLAUDE.md 为其指针,勿双边编辑)。
> **TaskForce 产品内智能体的运行时背景在 [BACKEND.md](BACKEND.md)**——经
> `agent/memory_ctx.py` 的 `load_agents_md()` 注入产品 system,与本文件无关:
> 改这里的开发纪律不会影响产品人设,反之亦然。

## 一、项目概况

**TaskForce**:企业级投资调研助手——基于 LangGraph 的单用户本地 Agent 工作台,面向投资调研场景(知识库问答 + 联网调研 + 沙箱代码执行;复杂调研问题先拆解为计划、经用户确认后多智能体接力执行),CLI REPL / FastAPI / Web 工作台三入口,另有 LangGraph Studio 调试点。练手目的是学习 LangGraph,同时是面向实习求职的项目经历。Windows 开发机,uv 管理,Python 3.12。

**当前状态**:后端模块 R + 00~11、前端 12 个模块、plan_0.1(Plan-and-Execute,ADR-0012)全部完成。知识库内核为 `src/rag_v01/`(docling 解析 + 父子分块 + Milvus 内置 BM25 + 向量双路 RRF 融合,方案见 `docs/20-决策与方案/modules/rag_0.1/`);旧 `tools/rag/` 的解析/切分/BM25/pgvector 存储已于 2026-09-22 下线,只留 `embed.py`(长期记忆在用)。基线:后端全量 505 tests 绿,前端 vitest 190 tests 绿。进度以 `docs/30-开发过程/TODO.md` 与各 `docs/20-决策与方案/modules/*/TODO.md` 为口径,架构决策以 `docs/20-决策与方案/adr/` 为准,文档导航以 `docs/index.md` 为准。

## 二、代码布局(src 七包,平级,依赖单向无环)

```
src/
├── agent/      # 主图(supervisor/answer/ask/memory/planner)+ tasks.py(TaskManager)+ subagents/(三子图 + 共享 ReAct 骨架)+ contracts/(Route/TaskContract/ResultSummary/Plan 系)
├── rag_v01/    # 知识库 RAG 内核(独立可搬):docling 解析、父子分块、Milvus 混合检索、ragas 评估(带独立 CLI)
├── tools/      # tool/(内置:文件读写、clock、webfetch)、skills/、mcp/、sandbox/、websearch/、rag/(kb_search 工具封装 + embed)
├── prompts/    # 全部提示词(md 数据包,零代码,占位符 $name 形式)
├── settings/   # 基础设施:config、loader(load_prompt 读 md)、usage、session、model_overrides(设置页覆盖表)、db/(base/checkpointer/store)
├── api/        # HTTP 入口:main.py + routers/(七 router:chat/knowledge/memory/skills/mcp/model_settings/health)
└── cli/        # 终端入口:repl.py + context/streaming/commands/(斜杠命令按域一文件)
dev/front/      # Web 工作台(Vue 3 + Vite 独立工程:不进 uv / hatchling / pytest;生产构建产物由 FastAPI 同源托管)
langgraph.json  # `langgraph dev` 入口,指向 agent/studio.py 的 make_studio_graph
```

依赖方向:`cli/api -> agent -> {settings, tools, rag_v01}`;`tools -> settings`;`prompts` 纯数据零依赖。仓库根的 `skills/`、`agents.md`(运行时数据,gitignore)、`mcp_config.json`、`.env` 不进 src。import 一律 `from agent.xxx import ...`、`from tools.xxx import ...`、`from settings.xxx import ...`、`from rag_v01.xxx import ...`。

## 三、文档体系(动手前必读;完整导航见 `docs/index.md`)

> 组织方式:**按用途 + 生命周期**分层(目录带中文数字前缀)。三态图例:🟢 现行(唯一口径) / 🔵 参考(定稿/讲解) / ⚪ 历史(仅存档) —— 逐目录状态见 index.md。
> **原子化规范**:单文件 **≤200 行**(超限即拆,分片保留原编号前缀、同构命名);每篇头部带**定位块**(一句话 + 所属体系 + 上下游各 1 条);**自包含**(不写"如前述/见上文",跨文档只留"细节见 X");每目录一个 `README.md` 作原子索引;跨模块引用优先指向对方 README(稳定锚点)。

| 文档 | 作用 |
|---|---|
| `docs/index.md` | **文档总索引**:按任务找文档 + 生命周期图例 + 原子化规范;新目录/新文档先入索引再建文件 |
| `docs/10-项目概览/` | 导览 + 现有架构总览(ARCHITECTURE.md:包结构、主/子图拓扑、契约与依赖) |
| `docs/20-决策与方案/adr/` | 架构决策记录 0001~0012(0012 = Plan-and-Execute;含被否决项,**勿"修复"有意为之的设计**;编号被 src 代码注释引用,文件勿改名) |
| `docs/20-决策与方案/design/` | 方案定稿:DESIGN-1/DESIGN-2(定位与能力)、PROMPT-DESIGN(上下文与提示词,§编号被 src 注释引用) |
| `docs/20-决策与方案/modules/` | 现行模块方案树(**唯一口径**,如 rag_0.1、plan_0.1,各含 README + TODO.md);新方案文档一律建在此处,按 rag_0.1 先例拆文档树 |
| `docs/30-开发过程/TODO.md` | **每次开发前必读**:任务清单与当前进度,完成一项勾一项;从第一个未勾选项继续 |
| `docs/30-开发过程/ROADMAP.md` | 开发进度唯一事实源:模块总表、依赖图、契约归属表、契约变更登记 |
| `docs/30-开发过程/`(模块目录与专项计划) | 00-bootstrap~11-api-finalize 共 12 个模块目录(各含 DEV.md)与专项计划(react-refactor-plan.md),按编号顺序执行 |
| `docs/40-排障记录/` | **开发问题与解决记录**:实际踩坑沉淀(现象/根因/解决),按模块组织;解决新坑先问用户是否沉淀再登记 |
| `docs/50-讲解与面试/` | 面向人的讲解与面试材料(非工程约束文档);rag/ 下两级索引 |
| `docs/60-前端文档/` | 前端开发文档(API-CONTRACT 为前端契约唯一事实源;后端契约变更须同步其 types/api/文档三处);三份大手册(契约/架构/UI)已拆为目录树,各带 README 索引 |
| `docs/70-个人素材/` | 简历、演示剧本(demo-scripts.md,README 配套)等个人素材(非工程文档) |
| `docs/99-历史存档/` | 历史方案与废弃材料(rag_improve_v1、ARCH-REVIEW、agents.example.md;**已下线**,头部带失效横幅;仅存档,勿按其实施) |
| `CONTEXT.md` | 术语表;代码命名与沟通必须用其术语(如"任务契约"而非"prompt","会话线程"而非"会话") |

> **索引纪律**:新目录/新文档**先入 `docs/index.md` 再建文件**;旧方案被取代时在头部就地加『状态+日期+继任链接』横幅,不删除历史文档。

## 四、开发工作流(硬性纪律)

1. **教学模式(最高优先级)**:本项目是用户的**练手项目**,目的是学习 LangGraph。**用户未明确要求时,禁止代写业务代码**——讲解实现思路、给出代码骨架/示例与关键 API、指出坑位,由用户亲自编写;用户写完后可请求 review 与答疑。文档、脚手架配置(pyproject / docker-compose / .env.example 等)不是学习重点,可正常代写。**测试/业务分工(硬性)**:`tests/` 下的测试代码一律由智能体负责编写与维护(含随模块落地的单测,fake model/monkeypatch 模式,不依赖真实 LLM/DB);业务代码给出**完整代码 + 改动点清单**,用户亲手誊写。
2. **严格按模块编号推进**,依赖未完成的模块不开工;开工前先读对应 DEV.md,按其分步任务清单执行,每步跑通验收命令才勾选。
3. **TODO.md 进度纪律**:每次开发前先读 `docs/30-开发过程/TODO.md` 确认进度;任务通过验收后在该文件打勾,模块完成时同步更新 ROADMAP 总表;`docs/20-决策与方案/modules/*/TODO.md` 内的里程碑同理。
4. **契约唯一出处**:共享 schema(`Route`/`TaskContract`/`ResultSummary`/`AgentState`/Plan 系等)只在归属模块定义(见 ROADMAP §6 契约归属表,契约代码在 `agent/contracts/`),其他包一律 import;改契约必须先在 ROADMAP §7 登记。
5. **全同步**:禁止引入 async/await。FastAPI 端点一律 `def`(自动走线程池);SSE 用同步 generator + `StreamingResponse`;LangGraph 用 `graph.stream` 同步 API。子图后台并行靠 `TaskManager` 的 `ThreadPoolExecutor`(方案 A,ADR-0009),不靠 asyncio。
6. **双入口共用业务层**:CLI REPL 与 FastAPI 只调同一套 `build_graph()` / `run_turn()`(均在 `agent/` 包),Studio 装配点同样只调 `build_graph()`;不允许出现第二套实现。
7. **提示词一律放 `prompts/` 下的 md 文件**,经 `settings/loader.py` 的 `load_prompt(name, **slots)` 加载渲染;禁止内联在节点代码。占位符 `$name` 形式(`string.Template`),避免与 JSON 花括号冲突。固定 system 只放静态内容(保前缀缓存),动态内容走消息流(ADR-0011)。
8. **HITL 纪律**:所有 `interrupt()` 只发生在主图 ask/memory/plan_confirm 节点(ADR-0008 单一挂起点,0012 扩展);子智能体绝不 interrupt,缺信息在结果摘要标注,由 supervisor 决定是否问询。
9. **并行纪律**:psycopg 连接非线程安全,并行分支各自取连接;`TaskManager` 一把 `threading.Lock` 护账本(结果与计数同步、drain 消费即清、全批完成才回调)。
10. 沟通与文档一律使用中文;回复简洁,只说本次要写的代码与要进行的测试。
11. **问题沉淀**:坑位解决验证后先问用户是否值得沉淀,确认后记 `docs/40-排障记录/<模块>.md`(格式见该目录 README);具普遍性的坑回填对应 DEV.md 坑表,不擅自记录。
12. **Python 风格**:遵循 `python-camel-style` skill(悬挂缩进 8 格、尾逗号、一行一参数、避免正则、100 字符边界,与 PEP 8 有意不同);存量代码渐进——新写与被改到的代码必须合规,谁改到谁顺手改,不做一次性整库重排;格式违规底单见 `docs/30-开发过程/style-violations-20260925.md`。

## 五、常用命令

```bash
uv sync                        # 安装依赖(hatchling 打包 src 七包,aliyun 镜像已配)
docker compose up -d           # 起本地 PostgreSQL + pgvector(主机端口 5433;知识库 Milvus 跑在 WSL,不在此 compose 内)
uv run pytest -q               # 全量测试
uv run pytest tests/test_graph.py -q                    # 单个文件
uv run pytest tests/test_graph.py -k test_dispatch -q   # 单个测试
uv run ruff check .            # lint(line-length 100,规则 E/F/I/W/UP/B)
uv run python -m cli.repl      # CLI REPL 入口
uv run uvicorn api.main:app --port 8010 --reload    # FastAPI 入口(端口固定 8010,勿改;8000 是沙箱隧道)
uv run langgraph dev --no-browser   # LangGraph Studio 调试入口(langgraph.json -> src/agent/studio.py:make_studio_graph;端口 2024,平台托管持久化,不挂本地 checkpointer)
cd dev/front && npm run dev    # 前端开发双进程(5173,/api 由 vite proxy 转发到 8010)
cd dev/front && npm run build  # 前端生产构建(dist/,FastAPI 同源托管)
cd dev/front && npm run test && npx vue-tsc --noEmit   # 前端测试与类型检查
```

各命令按对应模块 DEV.md 的验收标准为准;外部依赖(远程沙箱、MCP、Milvus)未配置时相关测试自动 skip,主线不阻塞在外部依赖上。Windows 坑:CLI/API 入口需先 reconfigure stdout 为 UTF-8(GBK 坑,ruff 对应 per-file-ignore 已配)。

## 六、架构 big picture(读多份文档才能拼出的全貌)

- **Plan-and-Execute(ADR-0012,plan_0.1)**:复杂调研先计划后执行。planner 仅在生成计划时调一次 LLM(`with_structured_output(PlanDraft)`);`plan_draft`(调 LLM)与 `plan_confirm`(纯确定性、interrupt 挂起点)必须双节点拆分——resume 后整节点重跑,重跑的是零副作用的 plan_confirm,计划不漂移。用户批准后按批派发,每批完成由 supervisor 内 `_advance_plan` 纯 Python 短路推进(以 task_id 对账 ResultSummary、解锁后续步骤、分批、收口),**计划推进绝不走路由 LLM,LLM 不得擅自改计划**;plan 以 dict 存 `AgentState.plan`(无 reducer、整体覆盖、仅 plan_draft/plan_confirm/supervisor 单点写,子图不碰);step 对账靠 PlanStep.task_id 复用 `ResultSummary.task_id`(零契约变更)。同步 Send 备胎通道不支持 plan(tasks=None 时 plan_confirm 直接 goto answer 附说明)。
- **Supervisor 拓扑与异步派发**:主图九节点 = `supervisor` 结构化路由 + `answer`/`ask`/`memory` + `plan_draft`/`plan_confirm` + 三个子图包装节点(retriever/research/executor);派发主通路是 `agent/tasks.py` 的 TaskManager(线程池 MAX_WORKERS=3 后台执行子图,submit 即返回可继续交互),同步 Send fan-out 仅作 tasks=None(测试/无管理器)时的备胎;结果由 supervisor 每轮 `drain_done()` 原子回收注入,answer 消费即清;`AUTO_NOTICE` 自动唤醒汇总(REPL watcher 线程 / Web 前端轮询 `GET /chat/tasks` + `POST /chat/summary`),plan 推进复用同一唤醒通路,唤醒轮以 PREFIX_SYSTEM_NOTICE 识别并短路跳过路由 LLM。
- **HITL 三挂起点**:ask(问询)、memory(`/confirm yes|no`)、plan_confirm(计划批准),全部在主图,任意时刻至多一个挂起;子图绝不 `interrupt()`(ADR-0008,挂起点清单由 ADR-0012 修订)。
- **子智能体独立上下文**(ADR-0009/0010):三子图共用 `subagents/react.py` 手写 ReAct 骨架(agent→tools 循环,自数轮数 + 16k 字符预算闸门);只收任务契约四件套,不读主图 messages、不知彼此存在;私有消息键 `react_msgs`(禁命名 messages,直挂同键会并进主图历史);只经 `subagent_results` 回传结构化摘要;supervisor 是唯一叙事者。
- **执行智能体的工具三层来源**:`tools/tool/`(内置,如文件读写、clock、webfetch,操作目标为沙箱工作区)+ `tools/skills/`(用户扩展)+ `tools/mcp/`(外部协议),装配在 executor 子图;知识库检索经 `tools/rag/kb_search.py` 封装暴露给 retriever(工具名与 JSON 契约自 2026-09-22 起未变)。
- **记忆双层**:短期 = PostgresSaver checkpointer(ConnectionPool 连接池,按 thread_id,断线重启续聊、挂起态可恢复);长期 = PostgresStore + pgvector,**memory-as-tool**(ADR-0011):`memory_search`/`store_memory` 两工具由主智能体按需调用,废除旧的"每轮 top-5 注入 system"。写入双分支:显式"记住X"直写(source=explicit),模型自主提案经 interrupt 用户确认才写(source=confirmed)。
- **知识库检索**:内核 `src/rag_v01/`(docling 解析 + 父子分块 + BM25(jieba 分词)+ 向量双路 RRF 融合召回),agent 侧只有 `tools/rag/kb_search.py` 适配层,方案见 `docs/20-决策与方案/modules/rag_0.1/`。
- **存储分工**:PostgreSQL + pgvector 只管会话 checkpoint 与长期记忆 Store;知识库的向量与 BM25 在 **Milvus**(HNSW + 内置 BM25,跑在 WSL,不在 docker compose 内)。
- **控制面本地、执行面远程**:沙箱是自建远程 Docker 服务,本仓库只做 `execute_python` 工具接入(SANDBOX_URL/API_KEY)。
- **第三装配点 LangGraph Studio**:`uv run langgraph dev` 经 langgraph.json 挂 `agent/studio.py` 的 `make_studio_graph()`;与 cli/api 的差别仅为调试便利(不挂本地 checkpointer——平台托管持久化;不接 watcher 自动唤醒——plan 靠交互轮推进),图结构与业务层完全共用 `build_graph()`。
- **模型分层**:火山方舟豆包 / DeepSeek(LLM)+ 智谱(embedding),均 OpenAI 兼容协议。**思考模式分层**:路由 LLM 固定 thinking=disabled 独立实例(DeepSeek 思考模式与结构化输出的强制 tool_choice 不兼容),生成侧(answer/子图)跟 `.env` 的 `LLM_THINKING`(adaptive/enabled/disabled);`.env` 是默认值,设置页「模型」节可覆盖 base_url/api_key/模型名(落 `.taskforce/model_config.json`,保存后重启生效)。
