
---

# TaskForce 多智能体架构修正方案（v2）

> 状态：待评审 → 定稿后执行
> 背景：用户对模块 03 T3 的初版实现提出两点架构性否决（滑窗删除、步数限制写法不正规），并要求按 LangGraph 官方规范重构子智能体封装。本文档为团队讨论结论与修改清单。
> 依据：LangChain 官方文档（2026-09 检索）：
> - [Add a subgraph as a node](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#add-a-subgraph-as-a-node)
> - [Call a subgraph inside a node（不同 state schema）](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#call-a-subgraph-inside-a-node)
> - [Recursion limit](https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit) / [Impose a recursion limit](https://docs.langchain.com/oss/python/langgraph/use-graph-api#impose-a-recursion-limit)
> - [Router: Use Command / Send](https://docs.langchain.com/oss/python/langchain/multi-agent/router#basic-implementation)
>
> **v2 修订说明（2026-09-02）**：
> 1. 争议 A 裁决变更：**共享键直挂 + Send 为首选方案（03 优先验证）**，适配节点 wrapper 降级为 fallback；理由：官方"Add a subgraph as a node"只需父子**共享键**，不要求 schema 相同——"子图不认识 messages"不构成直挂障碍；
> 2. 登记 wrapper 模式三项代价（checkpoint 不共享 / 流式不保证 / 异常不传播），v1 中"流式可见其内部节点"备注作废；
> 3. 补充 recursion_limit 步数预算公式（父+子图总和）；
> 4. 补充 subagent_results 消费链路（answer 节点读取 + RESET）；
> 5. 补充 Send 并发上限与 R1 全量保留期的运营保险。

---

## 1. 用户决议（硬性，不讨论）

| # | 决议 | 影响 |
|---|---|---|
| R1 | **删除滑动窗口**。上下文全量保留，不做任何截断；后续以"压缩上下文"功能替代（新增 backlog） | supervisor 路由、answer 汇总均使用完整 `state["messages"]`；删 `SLIDE_WINDOW`、`sliding_messages()`；PROMPT-DESIGN §1.2 作废并登记 |
| R2 | **步数限制改用官方机制**：递归上限用 LangGraph 原生 `recursion_limit`（invoke/stream 的 config 顶层项，默认 25），捕获 `GraphRecursionError` 兜底；不自己数消息 | 删 supervisor.py 的 `_steps()`、`route_marker()`、`MAX_STEPS` 哨兵消息方案 |
| R3 | **子智能体 = 编译后的子图，直接 `add_node` 进父图**（官方"Add a subgraph as a node"模式）；Send 扇出并发，同一子图可多实例 | `agent/subagents/` 下每个子智能体一个 `build_xxx_graph()` 返回编译图；主图 `add_node("retriever", retriever_graph)` |

> R3 补充执行口径（v2）：直挂的前提是父子图**共享键**，详见 §2 争议 A 首选方案。如最小实验失败，允许降级为官方"Call a subgraph inside a node"模式，但必须登记 §2 争议 A 的三项代价。

---

## 2. 团队讨论：两个争议点的裁决

### 争议 A：Send 的输入与"子图作为节点"如何兼容？

**问题**：官方两种子图接入方式——
- **共享 state keys**：编译子图直接 `add_node`，父子图经同名通道自动读写；
- **不同 state schema**：节点函数包裹 `subgraph.invoke(转换后的输入)`，手动转换进出。

我们的子图 schema 与主图 AgentState 不同（子图不认识 `messages`）。v1 据此判定"直接 Send 给子图不可行"，采用 wrapper 模式。**v2 修订：该结论不成立**——官方直挂模式**只要求共享键**，不要求 schema 相同；`messages` 不投影进子图即可，`contract` / `subagent_results` 两个共享键足以支撑直挂。

**裁决（v2，方案 A 优先）**：

**方案 A（首选，03 优先验证）：共享键直挂 + Send**

- 主图 `AgentState` 与子图 `SubgraphState` **都声明** `contract`、`subagent_results` 两个共享键（父子各自可有私有键）；
- `add_node("retriever", retriever_graph)` 直挂编译子图；`Send("retriever", {"contract": ...})` 直接发往子图节点（payload 经子图 schema 校验）；
- **收益**：完全符合 R3 决议；子图共享父图 checkpointer（独立命名空间，无冲突）；`stream(subgraphs=True)` 可见子图内部节点；无 wrapper 代码。
- **风险**：Send payload 到子图节点的校验行为需**最小实验实测确认**（见 §5 执行顺序第 0 步）。

**方案 B（fallback，仅当方案 A 实验失败）：适配节点 wrapper**（官方"Call a subgraph inside a node"模式）

- 每个子智能体模块提供 `build_xxx_graph() -> CompiledGraph`（纯子图，自己的 SubgraphState）；
- 主图侧提供适配节点：`Send` 目标为适配节点，节点内 `contract = SubgraphContract(**payload)` 校验 → `subgraph.invoke({"contract": contract})` → 返回 `{"subagent_results": [summary]}` 给主图 reducer；
- **必须登记的三项代价**：
  1. **checkpoint 不共享**：wrapper 内 invoke 的子图"runs in its own world"，**默认不共享父图 checkpointer**（除非手动传入）→ 子图无法持久化/中断恢复，与 06 HITL 目标冲突；因此子图 compile **不传 checkpointer（stateless）**，依赖主图持久化；
  2. **流式不保证**：`stream(subgraphs=True)` 的命名空间展开是直挂模式的承诺，wrapper 内 invoke 不在其列 → v1 备注"流式可见其内部节点"**作废，待实测**；
  3. **异常不传播**：子图异常默认**静默失败**并返回部分 state → wrapper 内必须**显式 try/except + 输出键校验**（缺失键即抛错），并补记日志。
- **附加约束**：官方明确"同一节点内不能调用多个子图"→ 每个适配节点只 invoke **一个**子图（本项目一图一适配节点，满足）；异步场景用 `ainvoke` 而非 `invoke`（避免阻塞事件循环）。

**演进验收标准**：方案 A 实测通过后，wrapper 全部退役（ROADMAP §7 登记为"已按共享键直挂重构"）。

### 争议 B：recursion_limit 的粒度与兜底行为

**问题**：官方默认 25 super-steps，超限抛 `GraphRecursionError`。需防"路由乒乓死循环"（supervisor 反复 dispatch 不收敛）。

**裁决（v2 修订，补充预算公式）**：

1. **预算公式**：`recursion_limit` 是整个 run（**父图 + 所有子图**）的 super-step 总和，估算：`supervisor(1) + max(子图内部节点数) × 路由轮数`。若 retriever 子图内部 3 节点，一轮 dispatch ≈ 4 步 → 25 对应约 5 轮路由循环，乒乓必触发；**如方案 A 直挂 + 多子图并行，步数按最坏子图节点数计**；

   > **v3 补注（2026-09-04，ADR-0010）**：子智能体统一 ReAct 后，子图步数动态化（每轮工具调用 ≈ 2 super-steps），上述"固定节点数 × 轮数"公式失效。修订为**双层防失控**：子图自数 `max_iterations`，超限经条件边优雅收尾（partial + warnings，保住 need_clarification 语义），主图 `recursion_limit` 仅作全局兜底；§6"必要时上调 40"继续有效。
2. 主图编译不变，运行时 config 显式传 `recursion_limit=25`（**config 顶层键，不进 `configurable`**）；
3. 兜底位置在 `run_turn`（service.py）：捕获 `GraphRecursionError` → 返回诚实 AIMessage（"本轮任务循环过深，已中止，请简化需求"）。图本身不捕（让引擎正常落 checkpointer 状态，不掩盖错误）；
4. 06 模块 HITL 挂起与 recursion_limit 无冲突：挂起时流正常返回，不消耗步数；resume 后重新计数。

---

## 3. 多智能体架构设计（修正后定稿）

### 3.1 总拓扑（方案 A：共享键直挂）

```mermaid
flowchart TD
    U["用户输入 run_turn()"] --> SUP["supervisor 节点<br/>llm.with_structured_output(Route)<br/>失败/超限→Command(answer)"]
    SUP -->|Command goto| ANS["answer 节点<br/>读 subagent_results 汇总作答 + RESET 清空"]
    SUP -->|Command goto| ASK["ask 节点(03 桩→06 interrupt)"]
    SUP -->|Command goto| MEM["memory 节点(03 桩→06 实装)"]
    SUP -->|Send(共享键直挂)| R1["retriever 子图<br/>(add_node 直挂,独立上下文)"]
    SUP -->|Send| R2["research 子图"]
    SUP -->|Send| R3["executor 子图"]
    R1 -->|subagent_results reducer| SUP
    R2 -->|subagent_results reducer| SUP
    R3 -->|subagent_results reducer| SUP
    ANS --> END(["END"])
    ASK --> SUP
    MEM --> SUP
```

- 同一轮可 Send 多个任务（**上限见 §3.4**），同类型子图可多实例并行；全部完成后 fan-in 回 supervisor；
- `subagent_results: Annotated[list, _add_or_reset]` 并行合并；answer 消费后哨兵清空；
- 子图不可见 messages、不感知彼此（HITL 单一挂起点原则，ADR-0008）；
- 方案 B（wrapper）拓扑：`SUP → Send → 适配节点 → invoke 子图`，节点层多一层适配节点，其余相同。

### 3.2 子智能体封装规范（方案 A 为主，方案 B 为 fallback）

**方案 A：共享键直挂**

```python
# agent/subagents/retriever.py
class SubgraphState(TypedDict):
    # 与主图 AgentState 共享的键（共享通道）
    contract: SubgraphContract
    # 子图私有键（可选）
    retrieved: list

def build_retriever_graph(llm) -> CompiledGraph:
    g = StateGraph(SubgraphState)
    g.add_node("retrieve", retrieve_node)
    g.add_edge(START, "retrieve")
    return g.compile()          # 不传 checkpointer → stateless，随父图持久化

# 主图侧：直挂
builder.add_node("retriever", retriever_graph)   # 与 Send("retriever", {"contract": ...}) 配合
```

**方案 B（fallback）：适配节点 wrapper**

```
agent/subagents/retriever.py   # fallback 形态
├── SubgraphState(TypedDict)   # 子图私有 schema：contract + subagent_results
├── build_retriever_graph(llm) -> CompiledGraph
│     └── StateGraph(SubgraphState)：START → 检索节点(们) → END，compile()（不传 checkpointer）
└── 主图侧适配节点 make_node(graph)  # Send 目标；invoke 编译子图 + 转换进出 + try/except + 键校验
```

数据流（方案 B）：`Send("retriever", 契约dict)` → 适配节点校验为 `SubgraphContract` → `retriever_graph.invoke({"contract": ...})` → 子图内部自由多节点 → 末节点返回 `{"subagent_results": [ResultSummary]}` → reducer 合并回主图。

### 3.3 与官方规范的对应关系

| 官方模式 | 本项目采用（v2） |
|---|---|
| Router：`Command(goto=单目标)` | answer / ask / memory 三条静态路由 |
| Router：`[Send(agent, input)]` fan-out | dispatch → 子图节点（共享键直挂，首选） |
| subgraph as node（共享 schema） | **03 首选方案**（`contract`/`subagent_results` 共享键） |
| subgraph inside node（不同 schema） | **fallback**（wrapper，仅方案 A 实验失败时启用，登记三项代价） |
| recursion_limit + GraphRecursionError | run_turn 兜底；REPL config 显式 25；预算公式见 §2 争议 B |

### 3.4 新增：subagent_results 消费链路与并发控制

1. **消费链路**：fan-in 回 supervisor 后，supervisor **只做路由不吞结果**；路由到 answer 节点 → answer 读取 `state["subagent_results"]` + 用户原问题生成最终答案 → 消费后 `RESET` 清空；
2. **并发上限**：Send 扇出受配置 `max_parallel_subagents`（初值 3）约束，防并行 LLM 调用的成本与限流失控；同类型子图多实例并行时，步数计入 §2 争议 B 的预算公式。

---

## 4. 修改清单（按文件，v2 修订）

| 文件 | 动作 | 内容 |
|---|---|---|
| `src/agent/state.py` | **改** | 新增共享键：`contract: SubgraphContract`、`subagent_results: Annotated[list[ResultSummary], _add_or_reset]`；保留 `RESET` 哨兵 reducer |
| `src/agent/supervisor.py` | **重写** | 删 `SLIDE_WINDOW/sliding_messages/_steps/route_marker/MAX_STEPS`；`route_node` 全量 messages + 失败返回 None；`build_contract` 不变；`dispatch_sends` 生成 `Send("子图节点名", {"contract": ...})` |
| `src/agent/subagents/stub.py` | **重写** | 真实子图：`SubgraphState`（含共享键）+ `build_stub_graph()` 编译图（内部 1 个节点回 ResultSummary） |
| `src/agent/build.py` | **重写** | supervisor 节点 Command 路由不变；子图**直挂 `add_node`**（方案 A）；若实验失败 → 适配节点 wrapper（方案 B）；删步数相关 |
| `src/agent/service.py` | 改 | `run_turn` 捕获 `GraphRecursionError` → 诚实 AIMessage 兜底；get_state 双路径保留 |
| `src/cli/repl.py` | 改 | config 增加 `"recursion_limit": 25`（顶层键，不进 configurable） |
| `src/prompts/supervisor.md` | 不动 | 与滑窗无关 |
| `tests/test_graph.py` | **新建（T6）** | fake model 轨迹/累积/清空/回退/超限五类断言；超限用 `recursion_limit=3` 触发；**新增"路由乒乓"用例（fake model 持续 dispatch）与"共享键直挂 vs wrapper"对照冒烟** |
| `docs/PROMPT-DESIGN.md` | 改 | §1.2 滑窗段落标记"已作废（2026-09-01 决议）：全量保留，压缩功能排入 backlog" |
| `docs/dev/ROADMAP.md` | 登记 | §7 增行：滑窗作废 + recursion_limit 机制替换自数步数 + 子图直挂（方案 A）/ wrapper fallback（方案 B） |
| `docs/dev/03-graph-skeleton/DEV.md` | 改 | T3/T5 任务描述删滑窗；T6 验收含超限测试与乒乓用例 |

**不动的**：`contracts/` 三契约（冻结有效）、`Route.next` 四分支、`TaskContract` 四件套、`ResultSummary`、checkpointer/SessionStore、REPL 命令注册表。

---

## 5. 执行顺序（v2 修订，插入方案验证步骤）

1. **第 0 步（新增，先行验证）**：最小实验——主图声明 `contract`/`subagent_results` 共享键 → 子图直挂 `add_node` → `Send("retriever", {"contract": ...})` → 验证：① payload 经子图 schema 校验可正常进入；② `stream(subgraphs=True)` 可见子图内部节点；③ checkpoint 落子图命名空间。**实验通过 → 全按方案 A 走；不通过 → 启用方案 B wrapper**（登记三项代价）；
2. 按 §4 逐文件修改（先 supervisor.py + stub.py + build.py 三件套，后 service.py + repl.py 两处小改）；
3. `uv run python -c "...nodes..."` 七节点冒烟（supervisor + answer + ask + memory + 3 子图节点）；
4. T6：tests/test_graph.py（含乒乓与直挂对照用例）；
5. T7：REPL 接入验证真模型两路由；
6. 文档三处（PROMPT-DESIGN / ROADMAP / 03-DEV）同步。

---

## 6. 遗留与 backlog（v2 修订）

- **上下文压缩**（R1 替代方案，**优先级提升**）：建议排在 06 HITL 之前或并行（HITL 后多轮场景更多）。方向：阈值触发（>N 条或 >M token）时 LLM 摘要折叠早期消息。**过渡保险**：全量保留期间，在 service.py 增加"本轮 messages 条数/token 超阈值"日志告警，不阻断但可观测；
- **共享键直挂**：由 v1 的"05 演进方向"**提前为 03 优先验证**（§5 第 0 步）；05 模块仅做多子图并行压力验证；
- recursion_limit=25 为初值，若 10 模块并行多任务实测偏紧，上调至 40（仅 config 数值，无代码变更）；
- **Send 并发上限**：`max_parallel_subagents` 初值 3，按 10 模块实测调优。

---

**v2 相对 v1 的关键结论**：争议 A 的 wrapper 方案已降级——**官方直挂模式只需共享键，03 阶段即可采用"共享键直挂 + Send"**，这既忠实执行用户决议 R3，又免去 checkpoint/流式/异常三方面的妥协；wrapper 仅作为实验失败时的 fallback 并登记代价。建议先跑 §5 第 0 步最小实验再定稿执行。