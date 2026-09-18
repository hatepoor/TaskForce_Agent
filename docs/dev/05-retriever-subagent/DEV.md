# 05-Retriever-Subagent 模块开发文档:检索子智能体

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`agent/subagents/retriever.py`
> ⚠️ **2026-09-04 修订(ADR-0010)**:三子智能体统一 ReAct 模式。本模块原"查询改写→检索→组织答案"三节点管线设计**作废**,已实现代码由模块 R 重写;现行为准的设计见 [react-refactor-plan.md](../react-refactor-plan.md):ReAct 循环(agent→tools→finalize)+ `kb_search` 工具,查询改写由 LLM 多轮调工具涌现。
> 一句话:把 03 的检索桩换成真子图--持 `kb_search` 工具的 ReAct 检索智能体(Agentic RAG),第一个真实子智能体上线。

## 1. 目标与范围

- **做什么(按 ReAct 重写,由模块 R 执行)**:retriever 子图(共享键 contract/subagent_results + 私有键 messages/hits/iteration);agent 节点 bind `kb_search` 工具(RAGStore.search 封装,去重+截断内聚在工具内,查询改写由 LLM 多轮调工具涌现);finalize 节点(无命中 need_clarification 不调 LLM;正常经 AnswerOut 产出 ResultSummary,data 含 doc_id/filename/seq/content/score);循环上限 5 轮;主图挂载(替换桩)。
- **范围外**:不注入 agents.md(裁决:检索智能体不注入);不注入长期记忆;不 interrupt(缺数据走 needs_clarification)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [03-graph-skeleton](../03-graph-skeleton/DEV.md) | `TaskContract`/`ResultSummary`/Send 挂载机制/主图节点名 |
| [04-rag](../04-rag/DEV.md) | `RAGStore.search` |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `agent/subagents/retriever.py` | ReAct 编译子图(复用 R 的 build_react_subgraph 骨架;共享键直挂,ADR-0009 方案 A) |
| `tools/rag/kb_search.py` | [R] kb_search 工具:RAGStore.search 封装,(doc_id,seq) 去重 + content 截断内聚 |
| `agent/build.py`(微调) | retriever 节点直挂编译子图(方案 A 实验失败则 wrapper,见 03-DEV T4) |
| `prompts/base.md` | [05] 子智能体共享底座(已按 ReAct 语义重写) |
| `prompts/subagents/retriever.md` | [05] ReAct 角色块(kb_search 工具说明 + 检索纪律,已重写) |
| `tests/test_retriever.py` | fake model(脚本化 tool_calls)+ 假 RAGStore 的循环单测(R-T3 重写) |
| `cli/repl.py`(改) | 注册 /kb 上传、列表、删除命令(调 RAGStore)✅ 已完成 |

## 4. 分步任务清单

> 原 T1-T4(三节点管线)已作废,由 [react-refactor-plan.md](../react-refactor-plan.md) 的 R-T1..R-T8 承接(kb_search 工具 → 共享骨架 → retriever 重写 → 全图接线 → 循环上限 → 无命中语义 → 流式过滤 → 真模型验收)。

### T5:REPL /kb 命令
- [ ] 在 02 的命令注册表注册 `/kb upload <file>`、`/kb list`、`/kb delete <doc_id>`(调 RAGStore;04 只提供 `python -m tools.rag.cli` 独立入口)。代码已就绪,验收并入 R-T8。
- 验收:REPL 内上传 fixture 文档 -> `/kb list` 可见 -> 提问命中 -> 删除后不再命中。
## 5. 验收标准(整模块)

- [ ] REPL 演示:上传 PDF -> 提问 -> 路由轨迹可见 -> 答案引用文档内容而非臆造;
- [ ] 无命中场景 needs_clarification 正确置位;
- [ ] `uv run pytest -q` 全绿(test_graph 回归基线不破)。

## 6. 核心概念速查

- **子图作为节点(ADR-0009)**:首选共享键直挂——`RetrieverState` 声明与主图共享的 `contract`/`subagent_results` 键,编译图直接 `add_node`;`Send` payload `{"contract": ...}` 经子图 schema 校验进入。仅当 03 的直挂实验失败才用 wrapper(invoke 编译图 + 转换进出 + 异常兜底,登记三项代价)。
- **独立 state**:子图 schema 无 `messages` 键,主图消息不投影进来,这正是"独立上下文"的实现。
- 提示词模板见 `docs/PROMPT-DESIGN.md` §2.1-2.3。

## 7. 常见坑与规避

| 坑 | 规避 |
|---|---|
| 子图内误用主图 state 字段 | 子图只用 RetrieverState;缺信息是 build_contract 的锅,回 03 改契约(走登记) |
| 检索结果全量塞进组织答案节点 | snippet 截断;每查询 top-5 已是上限 |
| 答案夹带模型知识 | 组织答案提示词明确"只基于检索内容";演示时用知识库外问题验证诚实性 |

## 8. 契约接口

**本模块定义**:无新共享契约(retriever 子图为内部实现)。

**本模块消费**:`TaskContract`/`ResultSummary`(03)、`kb_search`(R,`tools/rag/kb_search.py`)、`build_react_subgraph`(R,`agent/subagents/react.py`)。
