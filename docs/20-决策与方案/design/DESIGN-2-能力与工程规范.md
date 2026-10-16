# DESIGN-2-能力与工程规范

> 一句话: 记忆 / 知识库 / Skills·MCP·沙箱 / 模型接入 / 交互接口 / 技术栈 / 代码布局 / 里程碑 / 测试规范 / Backlog
> 体系: design · 项目方案 v2(精简版·面向实习求职) · 节选二
> 上游: [DESIGN-1-定位与多智能体](./DESIGN-1-定位与多智能体.md)
> 下游: 无(本方案到此结束)
> 细节见: [PROMPT-DESIGN(上下文与提示词设计)](./PROMPT-DESIGN.md)

## 3. 记忆

- **短期记忆**:LangGraph checkpointer(Postgres),按 thread_id 隔离会话线程,跨重启恢复(`/resume`)。
- **长期记忆**:LangGraph Store(PostgresStore + pgvector),仅存用户事实与偏好;写入仅主智能体,分显式写入与确认写入(interrupt + HITL,ADR-0002);支持查看与删除。
  - **条目结构**:一句话原子事实 + 来源标记(`explicit` / `confirmed`)+ 创建时间;写入时由主智能体把要记的内容压缩成单条原子事实,不存成段对话。
  - **检索**:封装为 `memory_search(query, top_k)` 工具,由主智能体判断需要时**按需调用**(ADR-0011,memory-as-tool);结果以 ToolMessage 进消息流,**不注入系统提示词**。
  - **写入**:封装为 `store_memory(content, source)` 工具 + memory 节点(显式写入直写 / 确认写入 interrupt + HITL,ADR-0002),source 标 `explicit` / `confirmed`。
- **agents.md**:本地文件(build_graph 期读入并缓存,路径入 settings,消除 cwd 依赖),固定进 system;按 ADR-0011 只进 **answer/ask 侧**,路由(supervisor)不注入;调研与执行智能体经任务契约收到全文,知识库检索智能体不注入(详见 docs/20-决策与方案/design/PROMPT-DESIGN.md)。

## 4. 知识库与 RAG

- 解析:TXT/Markdown 用内置读取,PDF 用 `pypdf`,Word 用 `python-docx`(**不用 unstructured**,依赖链在 Windows 上极易装崩,ADR-0005)。
- 切块:`RecursiveCharacterTextSplitter`,chunk 500 / overlap 100。
- 向量化:智谱 embedding 入 pgvector;检索向量召回 top-5。
- 管理以文档为最小单元(上传/列表/删除,删除连同向量)。

## 5. Skills、MCP 与执行沙箱

- **Skill**:`skills/` 目录,文件夹 + SKILL.md(遵循 Anthropic Skills 规范);元数据(name + description)常驻提示词,全文用时才读,渐进式加载;主智能体与执行智能体可用;Skill 附带脚本一律经沙箱执行,不直接在本机运行。
- **MCP**:`mcp_config.json` 配置本机 stdio 服务器,`langchain-mcp-adapters` 把工具暴露给智能体;连接带超时,单服务器失败降级为告警并继续,绝不阻塞主流程;工具按"索引常驻 + 按需拉详情"注入(详见 docs/20-决策与方案/design/PROMPT-DESIGN.md)。
- **内置工具**:`tools/tool/` 存放 agent 自带的基础工具(read_file / write_file / list_files),操作目标为**沙箱工作区**而非本机文件系统,底层经沙箱执行封装。

### 执行沙箱(接入用户自建的远程 Docker 服务,ADR-0007)

- 沙箱服务由用户预先自建并部署于其远程服务器(Docker 容器形态),**本仓库不开发沙箱本身,只实现本机侧接入**;具体接口协议与容器策略以沙箱实际实现为准。
- 本机侧:`tools/sandbox/client.py` 把沙箱能力适配封装为 LangChain 工具 `execute_python(code)`;调用携带 `session_id`(= 会话线程 id),若沙箱支持会话级工作区,则同一会话内"先写文件、下一步再读"的跨步任务可用。
- `.env` 配 `SANDBOX_URL` / `SANDBOX_API_KEY`;沙箱端点必须鉴权(它是"任意代码执行"端点,绝不裸奔公网)。
- backlog(面试加分项):把本 Agent 反向封装为 MCP Server 对外提供服务。

## 6. 模型接入

- **LLM**:火山引擎方舟(豆包系列),OpenAI 兼容接口。
- **Embedding**:智谱 embedding 模型,OpenAI 兼容接口。
- 两套独立配置:`.env` 中 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 与 `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL`。
- 启动时断言 embedding 维度与 pgvector 的 `vector(N)` 列一致,不一致直接报错。

## 7. 交互与接口

- **REPL 斜杠命令**:`/kb upload <file>`、`/kb list`、`/memory list`、`/mcp add`、`/new`、`/resume <id>`、`/confirm`(HITL 确认)、`/stats`(当前会话累计 token 与预估费用)等;**问询挂起时自由文本输入即回答,无需命令**。
- **FastAPI router(6 个,约 15 个端点)**:

| Router | 端点 |
|---|---|
| `/chat` | `POST /chat`(SSE 流式)、`GET /chat/threads`、`POST /chat/confirm`(confirm 挂起的批准/拒绝后 resume)、`POST /chat/answer`(question 挂起的回答后 resume) |
| `/knowledge` | `GET`、`POST /upload`(multipart)、`DELETE /{doc_id}` |
| `/memory` | `GET`、`DELETE /{id}` |
| `/skills` | `GET`(扫描目录,只返回元数据) |
| `/mcp` | `GET /servers`、`POST /servers`、`DELETE /servers/{name}`、`POST /servers/{name}/test` |
| `/health` | `GET`(存活 + DB 连通自检;已配置沙箱时加沙箱连通自检) |

## 8. 技术栈与依赖

本地主体:

| 依赖 | 用途 |
|---|---|
| `fastapi` `uvicorn` | HTTP/ASGI,同步端点 |
| `langgraph` | 主图 + 子图、Command(goto)、Send 并行(线程池)、interrupt |
| `langgraph-checkpoint-postgres` | 短期记忆 checkpointer |
| `langchain-core` `langchain-openai` `langchain-text-splitters` | 模型/工具抽象、切块(**不装 langchain 整包**) |
| `langchain-mcp-adapters` + `mcp` | MCP stdio 客户端 |
| `psycopg[binary]` | 裸 SQL 访问 PG(不用 ORM;连接非线程安全,并行路径各取各的连接) |
| `pypdf` `python-docx` | PDF / Word 解析 |
| `python-dotenv`(经 pydantic-settings) | `.env` 读取 |
| `ddgs` | 调研智能体 Web Search(免费免 key) |

沙箱服务:用户自建,不在本仓库;本机侧接入仅需标准 HTTP 客户端,无新增依赖。

开发依赖:`pytest` `httpx` `ruff`。本地基础设施:Docker Compose 起 `pgvector/pgvector:pg16`。

**明确不装**:`unstructured`、`SQLAlchemy`、`langchain` 整包、`langchain-community`、`asyncpg`、`redis`。

## 9. 代码布局(src 布局,六个平级包,依赖单向无环)

```
taskforce/
├── pyproject.toml            # uv 管理;hatchling 打包 src 下六个包;aliyun 镜像
├── docker-compose.yml        # postgres + pgvector(本地,主机端口 5433)
├── .env.example              # 配置模板(.env 本地创建,不入库)
├── agents.md                 # 静态全局背景(手工维护)
├── skills/                   # 本地 Skills 数据(每目录一个 SKILL.md)
├── mcp_config.json           # 本机 MCP 服务器配置
├── CLAUDE.md / CONTEXT.md / docs/
├── tests/
└── src/
    ├── agent/                # ★ Agent 主体(只有编排,无任何能力实现)
    │   ├── contracts/        # 共享契约:route / task_contract / summary(03 冻结)
    │   ├── state.py          # AgentState(messages + subagent_results reducer)
    │   ├── build.py          # build_graph + make_llm(六节点主图组装)
    │   ├── service.py        # run_turn(双入口共用业务层)
    │   ├── supervisor.py     # 结构化路由节点 + build_contract
    │   ├── answer.py         # 汇总作答 + 消费即清
    │   ├── ask.py            # 问询节点(interrupt)
    │   ├── memory.py         # 记忆节点(显式直写 / interrupt 确认)
    │   └── subagents/        # stub / retriever / executor / research 四个子图
    ├── tools/                # ★ 工具与能力服务
    │   ├── tool/             # 内置工具:read_file / write_file / list_files(沙箱工作区)
    │   ├── skills/           # SkillRegistry(渐进式加载)
    │   ├── mcp/              # MCPToolProvider(config + client,索引+按需详情+降级)
    │   ├── sandbox/          # execute_python(接入自建远程沙箱)
    │   ├── websearch/        # web_search(ddgs)
    │   └── rag/              # parse / split / embed / store / cli
    ├── prompts/              # ★ 全部提示词(md 数据包,零代码,占位符 $name)
    │   ├── supervisor.md / answer.md / ask.md / memory.md / base.md
    │   └── subagents/        # retriever / executor / research 角色块
    ├── settings/             # ★ 基础设施
    │   ├── config.py         # Settings + get_settings + 启动断言
    │   ├── loader.py         # load_prompt(name, **slots):读 md + 渲染占位符
    │   ├── usage.py          # UsageTracker(/stats)
    │   ├── session.py        # SessionStore(thread_id 本地持久化)
    │   └── db/               # base(连接+建扩展)/ checkpointer / store
    ├── api/                  # HTTP 入口:main.py + routers/(六个 router)
    └── cli/                  # 终端入口:repl.py
```

依赖方向:`cli/api -> agent -> {settings, tools}`;`tools -> settings`;`prompts` 纯数据零依赖。仓库根的 `skills/`、`agents.md`、`mcp_config.json`、`.env` 为运行时数据,不进 src。

## 10. 开发里程碑(约 47h,按业余每周 8-12h 计 6 周)

| 阶段 | 内容 | 可演示成果 |
|---|---|---|
| 1 地基+单智能体(约 8h) | Docker PG 起库;最小 LangGraph 图直连 LLM;SSE;checkpointer;REPL;usage 打点与 /stats | CLI 聊天 -> 重启服务 -> `/resume` 接着聊;`/stats` 显示 token 与费用 |
| 2 RAG+检索子智能体(约 10h) | 解析/切块/embedding/pgvector;`/knowledge`;检索子图 + 结构化路由;任务契约与结果摘要 schema | 上传 PDF -> 提问 -> 路由日志可见子智能体被调用 |
| 3 记忆+HITL+Skills+MCP+沙箱接入(约 17h,风险最高) | 长期记忆(`memory_search`/`store_memory` 工具 + 显式/确认写入,ADR-0011);**统一 HITL(ask 问询 + confirm 确认,单一挂起点)**;Skills 渐进加载;MCP stdio 接入(工具索引+按需拉取);接入自建远程沙箱(execute_python 封装 + 联调) | "记住我偏好 X" -> 新会话生效;任务缺参数时智能体主动提问并继续;"写脚本统计这份 CSV" -> 沙箱执行返回结果 |
| 4 调研智能体+并行派发+收尾(约 12h) | Web Search 调研 ReAct 子图(ADR-0010);**Send 并行派发**(线程池 fan-out/fan-in,子结果消费即清);README + 3-5 条固定演示剧本;ruff;(可选)录屏 | "对比 LangGraph 与 CrewAI 并结合我知识库笔记" -> 并行派发可见,一次汇总回答 |

前三阶段完成即具备说服力,阶段 4 之后随时可停。沙箱接入是独立小任务,可与阶段 3 其余内容并行。模块级任务拆解见 `docs/30-开发过程/ROADMAP.md` 与 12 份模块 DEV.md。

## 11. 测试与工程规范最小集

- **值得写**:RAG 解析->切块->存->检索 roundtrip(固定小 fixture);用 fake ChatModel 把整图跑一圈的接线测试(零 API 成本、不 flake);API 冒烟(health/knowledge);记忆 store 插查删 roundtrip;interrupt 挂起与 resume 的往返(fake model 驱动);沙箱接入冒烟(未配置 `SANDBOX_URL` 时自动 skip)。
- **不写**:LLM 输出断言、提示词文本单测、深 mock 图测试、沙箱服务内部测试(不属本仓库)。
- ruff 一处配置负责 lint + format;类型注解写满但 v1 不跑 mypy。
- **README 必含**(面试官 30 秒扫描线):一句话定位(见顶部定位句)、架构图(mermaid,含本地主体与远程沙箱的分离)、录屏/GIF + 一行启动命令、五分钟起步、功能勾选清单 + **"刻意不做"清单(附取舍理由)**、设计决策章节、一条命令跑测试。

## 12. Backlog(明确不做,README 中附一句取舍理由)

多用户/JWT(表已预留 user_id)、前端、时间旅行 `/rewind`、Langfuse tracing(要用必须带"定位了什么问题"的故事)、rerank/混合检索、多命名知识库、把 Agent 封装为 MCP Server、重试/降级框架、ask 回答中敏感信息的打码存储、对话摘要压缩、动态工具选择、tiktoken 精确计量、deep agents(已废弃,ADR-0001)。
