# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 回复约定
回复简洁，只回复本次要写的代码，和要进行的测试，多余内容不回复

## 项目概况

**TaskForce**:基于 LangGraph 的单用户本地 Agent 工作台(知识库问答 + 联网调研 + 沙箱代码执行,CLI 与 FastAPI 双入口),面向实习求职的项目经历。Windows 开发机,uv 管理,Python 3.12。

**当前状态:设计与开发文档已完成、项目骨架已初始化,业务代码自模块 01 起逐模块落地。** 一切以 `docs/dev/` 的开发文档为准。

## 代码布局(src 布局,六个平级包,依赖单向无环)

```
src/
├── agent/      # Agent 主体:主图(supervisor/answer/ask/memory)+ subagents/(三个子图)+ contracts/(共享契约)
├── tools/      # 工具与能力:tool/(内置:read_file/write_file/list_files)、skills/、mcp/、sandbox/、websearch/、rag/
├── prompts/    # 全部提示词(md 数据包,零代码,占位符用 $name 形式)
├── settings/   # 基础设施:config、loader(load_prompt 读 md)、usage、session、db/(base/checkpointer/store)
├── api/        # HTTP 入口:main.py + routers/(六个 router)
└── cli/        # 终端入口:repl.py
```

依赖方向:`cli/api -> agent -> {settings, tools}`;`tools -> settings`;`prompts` 纯数据零依赖。仓库根的 `skills/`、`agents.md`、`mcp_config.json`、`.env` 是运行时数据,不进 src。

## 文档体系(动手前必读)

| 文档 | 作用 |
|---|---|
| `docs/dev/TODO.md` | **每次开发前必读**:任务清单与当前进度,完成一项勾一项;从第一个未勾选项继续 |
| `docs/dev/ROADMAP.md` | 开发进度唯一事实源:模块总表、依赖图、契约归属表、契约变更登记 |
| `docs/dev/NN-xxx/DEV.md` | 12 个模块的开发文档,按编号 00->11 严格顺序执行 |
| `docs/DESIGN.md` | 架构方案定稿(what/why) |
| `docs/PROMPT-DESIGN.md` | 主/子智能体的上下文与提示词设计 |
| `docs/adr/0001-0009` | 架构决策记录(含被否决项,勿"修复"有意为之的设计) |
| `docs/troubleshooting/` | **开发问题与解决记录**:实际踩坑沉淀(现象/根因/解决),按模块组织,解决后及时登记,防重复踩坑 |
| `CONTEXT.md` | 术语表;代码命名与沟通必须用其术语(如"任务契约"而非"prompt","会话线程"而非"会话") |

## 开发工作流(硬性纪律)

1. **教学模式(最高优先级)**:本项目是用户的**练手项目**,目的是学习 LangGraph。**用户未明确要求时,禁止代写业务代码**--应当讲解实现思路、给出代码骨架/示例与关键 API、指出坑位,由用户亲自编写;用户写完后可请求 review 与答疑。文档、脚手架配置(pyproject / docker-compose / .env.example 等)不是学习重点,可正常代写。**测试/业务分工(硬性)**:`tests/` 下的测试代码一律由 Claude 负责编写与维护(含随模块落地的单测);业务代码由 Claude 给出**完整代码 + 改动点清单**,用户亲手誊写,Claude 不落盘写业务代码。
2. **严格按模块编号推进**,依赖未完成的模块不开工;开工前先读对应 `DEV.md`,按其分步任务清单执行,每步跑通验收命令才勾选。
3. **TODO.md 进度纪律**:每次开发前先读 `docs/dev/TODO.md` 确认进度;任务通过验收后在该文件打勾,模块完成时同步更新 ROADMAP 总表。
4. **契约唯一出处**:共享 schema(`Route`/`TaskContract`/`ResultSummary`/`AgentState` 等)只在归属模块定义(见 ROADMAP §6 契约归属表,契约代码在 `agent/contracts/`),其他包一律 import;改契约必须先在 ROADMAP §7 登记。
5. **全同步**:禁止引入 async/await。FastAPI 端点一律 `def`(自动走线程池);SSE 用同步 generator + `StreamingResponse`;LangGraph 用 `graph.stream` 同步 API。
6. **双入口共用业务层**:CLI REPL 与 FastAPI 只调同一套 `build_graph()` / `run_turn()`(均在 `agent/` 包),不允许出现第二套实现。
7. **提示词一律放 `prompts/` 下的 md 文件**,经 `settings/loader.py` 的 `load_prompt(name, **slots)` 加载渲染;禁止把提示词字符串内联在节点代码里。占位符用 `$name` 形式(`string.Template`),避免与 JSON 花括号冲突。
8. **并行纪律**:Send fan-out 的并行分支各自独立取 psycopg 连接(连接非线程安全);子智能体绝不直接 `interrupt()`,缺信息时在结果摘要的 `needs_clarification` 标注。
9. 沟通与文档一律使用中文。
10. **问题沉淀**:开发中遇到 bug/坑位并解决验证后,先向用户询问是否值得沉淀,经确认再记录到 `docs/troubleshooting/<模块>.md`(格式见该目录 README:现象/根因/解决/关联);具普遍性的坑回填对应 DEV.md 坑表;不擅自记录。

## 常用命令

```bash
uv sync                        # 安装依赖(hatchling 打包 src 六包,aliyun 镜像已配)
docker compose up -d           # 起本地 PostgreSQL + pgvector(主机端口 5433)
uv run pytest -q               # 全量测试
uv run pytest tests/test_graph.py -q                    # 单个文件
uv run pytest tests/test_graph.py -k test_dispatch -q   # 单个测试
uv run ruff check .            # lint
uv run python -m cli.repl      # CLI REPL 入口
uv run uvicorn api.main:app --port 8010 --reload    # FastAPI 入口(端口固定 8010,勿改;8000 是沙箱隧道)
```

各命令按对应模块 DEV.md 的验收标准为准;外部依赖(远程沙箱、MCP)未配置时相关测试自动 skip,不得让主线阻塞在外部依赖上。import 一律 `from agent.xxx import ...`、`from tools.xxx import ...`、`from settings.xxx import ...`。

## 架构 big picture(读多份文档才能拼出的全貌)

- **Supervisor 拓扑**:主图六节点(`supervisor` 结构化路由 -> `answer`/`ask`/`memory` 或 Send 派发到 `retriever`/`research`/`executor` 三个子图包装节点);dispatch 经 `Send(node, contract)` 动态 fan-out(线程池并行、同节点可多实例),fan-in 全部完成后回 supervisor;`subagent_results` 用 `operator.add` reducer 合并,answer 后消费即清。
- **子智能体独立上下文**:子图只收到任务契约四件套(task/user_utterance/input_data/output_schema),不读主图 messages、不知彼此存在;只回传结构化结果摘要;supervisor 是唯一叙事者。
- **执行智能体的工具三层来源**:`tools/tool/`(内置,如文件读写,操作目标为沙箱工作区)+ `tools/skills/`(用户扩展)+ `tools/mcp/`(外部协议),装配在 executor 子图。
- **记忆双层**:短期 = checkpointer(按 thread_id,PostgresSaver `from_conn_string` 连接池);长期 = Store + pgvector(仅用户事实与偏好,每消息向量检索 top-5 只注入主智能体)。
- **HITL 单一挂起点**:`interrupt()` 只发生在主图 ask 节点(自由文本即回答)与 memory 节点(`/confirm yes|no`),任意时刻至多一个挂起。
- **控制面在本地、执行面在远程**:执行沙箱是用户自建的远程 Docker 服务,本仓库只做 `execute_python` 工具接入(SANDBOX_URL/API_KEY)。
- 模型:火山方舟豆包(LLM)+ 智谱(embedding),均 OpenAI 兼容,`.env` 两套独立配置。
