# DESIGN-1-定位与多智能体

> 一句话: 项目定位与形态、多智能体架构(Supervisor 拓扑 / 路由与并行派发 / 统一 HITL)
> 体系: design · 项目方案 v2(精简版·面向实习求职) · 节选一
> 上游: 无(本篇是方案起点)
> 下游: [DESIGN-2-能力与工程规范](./DESIGN-2-能力与工程规范.md)
> 细节见: [PROMPT-DESIGN(上下文与提示词设计)](./PROMPT-DESIGN.md)、根目录 `CONTEXT.md`(术语)

> v2 于 2026-08-28 定稿:项目定位从"深入学习 LangGraph 的完整系统"调整为"面向实习求职的项目经历",多用户与部分 LangGraph 进阶特性移入 backlog(见 ADR-0005,其取代 ADR-0003 的多用户决策;Send 并行后经 ADR-0006 回归 v1)。术语定义见根目录 `CONTEXT.md`,上下文与提示词设计见 `docs/20-决策与方案/design/PROMPT-DESIGN.md`。核心思想:**砍掉一切伪必需品,把工时花在五个核心能力上,留足时间做演示与文档。**

**项目名:TaskForce**。架构隐喻:主智能体是指挥官(Supervisor),三个子智能体是特遣队员,任务可并行派发。README 定位句:**"TaskForce -- 基于 LangGraph 的个人 Agent 工作台:知识库问答、联网调研、沙箱代码执行,CLI 与 API 双入口。"**

## 1. 定位与形态

- 个人 Agent 工作台:知识库问答 + 联网调研 + 轻量任务执行,一条指令统一调度。
- **单用户、无鉴权**:数据表保留 `user_id` 列(默认 `'local'`)作为未来补多用户的扩展点,但 v1 不做注册/登录。
- **无前端**。终端 REPL + 斜杠命令为第一入口;FastAPI 提供最小 HTTP API 作为第二入口,CLI 与 API **共用同一套业务层**,不允许两套实现。
- **控制面在本地、执行面在远程**:Agent 主体(主图、PG、FastAPI、CLI)在本地运行;执行沙箱为用户自建的远程 Docker 沙箱服务,直接接入(ADR-0007)。
- 本地主体**全同步**(不用 async):FastAPI 端点用 `def` + 同步 generator 喂 `StreamingResponse` 实现 SSE;LangGraph 用 `graph.stream` 同步 API。同步形态最好调试,且规避了"SSE 流式 + interrupt"的异步绞杀坑。
- **Send 并行不受全同步影响**:LangGraph 同步运行时对同一超步的多个分支用**线程池**并行执行;子智能体均为 IO-bound(LLM/Web 搜索/沙箱 HTTP 调用),等待时释放 GIL,墙钟时间 ≈ 最慢分支。并发与异步是正交概念,asyncio 的收益要到成百上千路并发时才体现,本场景并发量是个位数。工程约束:并行节点不得共享单个 psycopg 连接(每路径独立取连接)。

## 2. 多智能体

- Supervisor 拓扑:主智能体 + 3 个子智能体,子智能体互不直连,协作经主智能体路由。**主智能体支持并行派发**(ADR-0006):一次决策可同时派多个子任务,经 `Send(node, state)` 动态 fan-out,全部完成后 fan-in 回 supervisor 汇总。
- **主智能体**:任务拆解与编排、亲自求解复杂任务、长期记忆唯一写入者。路由用 Pydantic 结构化输出,解析失败落入默认回退节点;防路由死循环用 LangGraph 原生 `recursion_limit`(config 顶层项)+ 捕获 `GraphRecursionError` 兜底(ADR-0009)。
- **主/子智能体的上下文构成、系统提示词结构、消息策略与 token 治理**:详见 `docs/20-决策与方案/design/PROMPT-DESIGN.md`(要点:子智能体只收到自包含的任务契约、独立上下文执行、只回传结构化结果摘要;主层消息全量保留〔滑窗已废除,ADR-0009 R1,压缩功能为 backlog〕 + 子结果消费即清;提示词以 md 文件存放于 `prompts/` 包,经 `settings/loader.py` 的 `load_prompt()` 加载)。

### 路由与并行派发设计

```python
class Task(BaseModel):
    agent: Literal["retriever", "research", "executor"]
    task: str        # 派发的子任务(重构后的子问题,非用户原话)
    reason: str      # 一句话理由,进日志/演示,路由可解释

class Route(BaseModel):
    next: Literal["answer", "memory", "dispatch", "ask"]
    question: str | None       # ask 时必填:要问用户的问题
    tasks: list[Task] | None    # dispatch 时必填,可含多个不同子智能体的任务
```

主图状态与流转:

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]                  # 主层对话历史
    subagent_results: Annotated[list, operator.add]          # 并行结果摘要累积(reducer,answer 后消费即清)
```

```
用户消息
   │
   ▼
supervisor ──结构化路由──┬──► answer:主智能体亲自作答 ────────────────► END
   ▲                    ├──► memory 节点:显式直写 / interrupt 确认 ──┐
   │                    ├──► ask 节点:interrupt 问询用户 ────────────┤
   │                    └──► dispatch:Send fan-out ──┬─ retriever 子图 ─┤
   │                                                  ├─ research 子图 ──┤ 结果摘要
   │                                                  └─ executor 子图 ──┘ 回 supervisor
   └───── recursion_limit 兜底:GraphRecursionError → 诚实中止消息(ADR-0009)┘
```

- **fan-in 语义**:LangGraph 保证同一轮派发的所有 Send 执行完毕后才回到 supervisor,由它判断结果是否足够(继续派发 / 总结回答)。
- **结果回传用摘要**:子智能体在独立上下文窗口执行,只把结构化结果摘要一条写回 `subagent_results`,主层上下文不膨胀。这是"多 agent 的 token 成本怎么控"的标准答案。信息不足时子智能体在摘要的 `needs_clarification` 字段标注,由 supervisor 决定是否发起问询。
- **子智能体执行模式(ADR-0010)**:三个子智能体统一为 **ReAct 工具循环**——模型节点 `bind_tools` 各自工具集 -> 有工具调用则执行并回填 ToolMessage -> 无则收尾写结果摘要;差异仅在工具集、循环上限(检索 5 / 调研 8 / 执行 12 轮)与收尾逻辑;循环骨架共用 `agent/subagents/react.py`,且必须留在编译子图内部(防流式泄漏)。supervisor 不走 ReAct:结构化路由即官方 router 模式(ADR-0010 R2)。
  1. **知识库检索智能体**:持 `kb_search` 工具的 Agentic RAG——LLM 自主改写查询、多轮检索(去重+截断内聚在工具内)、只基于命中作答;命中为空标 needs_clarification;
  2. **调研智能体**:持 `web_search` 工具(起步用 `ddgs`,免费免 key,预留替换)的搜-评-再搜 ReAct 循环;
  3. **执行智能体**:持内置文件工具 / Skill / MCP 工具 / `execute_python` 的 ReAct 执行循环。
- 面试必答题(写进 README 设计决策):
  - **为什么用子智能体子图而不是普通工具**--多步循环、独立上下文、可独立演进;
  - **为什么需要多智能体与并行**--任务可分解、子任务无依赖时应并行,Supervisor 的价值正在于此;
  - **没有 async 怎么并行**--并发与异步是正交概念:LangGraph 同步运行时用线程池并行执行同一超步的多个 Send 分支;子智能体全部是 IO-bound(LLM/Web/沙箱调用),等待时释放 GIL,线程并行有效,墙钟时间 ≈ 最慢分支;asyncio 的收益要到成百上千路并发才体现,本场景是个位数并发,全同步换取可调试性;
  - **沙箱为什么独立在远程 Docker**--容器级隔离、执行面与控制面分离;
  - **Supervisor 与 fan-out/fan-in 的关系**--并行派发不改变 Supervisor 属性,两者是正交维度:Supervisor 描述控制关系(决策集中、子智能体互不直连、结果回环再决策、派发由 LLM 动态决定),fan-out/fan-in 描述执行并发形态(Send 分发、reducer 汇聚)。纯 fan-out/map-reduce 管线没有中央决策者与决策回环,分派由数据静态决定;本系统属于"Supervisor 编排 + fan-out 执行"的组合,即 Anthropic 所称的 orchestrator-workers;
  - **为什么 HITL 只发生在主图层**--见"统一 HITL 机制"。

### 统一 HITL 机制(ADR-0008)

所有 interrupt 只发生在主图节点,**单一挂起点原则**:任意时刻最多一个 pending interrupt,恢复逻辑完全确定。两类挂起:

- **问询(question)**:supervisor 遇到不确定情况或需要用户输入(任务澄清、缺失参数、凭据等)时路由到 ask 节点,`interrupt()` 携带问题挂起,CLI 打印问题;**用户的自由文本输入即回答**,作为 user message 进入主图消息,回到 supervisor 继续决策。
- **确认(confirm)**:memory 节点的确认写入,`interrupt()` 携带记忆提案,`/confirm yes|no` 触发 `Command(resume=...)`;显式写入("记住 X")不挂起直接写。

子智能体**不直接 interrupt**:发现信息不足时在结果摘要的 `needs_clarification` 标注,由 supervisor 决定是否发起问询。理由:并行 fan-out 下多个子分支同时 interrupt 会产生多个 pending interrupts(resume 语义复杂、是 LangGraph 出了名的坑);且与"子智能体互不直连"的拓扑一致。

已知妥协:ask 的回答(含密码等敏感信息)明文进入对话历史与 checkpointer;单用户本地部署接受此边界,README 注明,打码存储在 backlog。
