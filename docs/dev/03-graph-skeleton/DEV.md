# 03-Graph-Skeleton 模块开发文档:多智能体骨架(契约冻结)

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`agent/`(contracts、state、supervisor、answer、subagents/stub)+ `settings/loader.py` + `prompts/`
> 一句话:做完本模块,主图从单节点变成完整的 Supervisor 骨架--结构化路由、Send 派发通道、reducer、answer 消费即清全部就位,子智能体用桩代替;**全部共享契约(contracts)与提示词文件组织方式在本模块冻结**。

## 1. 目标与范围

- **做什么**:`agent/contracts/` 定稿三份契约(Route/Task、TaskContract、ResultSummary);`agent/state.py` 增加 `contract`/`subagent_results` 共享键(后者带哨兵 reducer);supervisor 节点(结构化输出路由 + 失败回退 + `build_contract` 纯函数;防死循环用原生 `recursion_limit`,见 ADR-0009);dispatch 用 **Send 通道(先单发)**;answer 节点(汇总 + 消费即清);ask/memory 占位桩节点;三个桩子图(**真实编译 StateGraph**,收契约、回固定摘要;共享键直挂优先,见 T4);**`settings/loader.py` 实现 `load_prompt(name, **slots)`**;**首批提示词 md 文件落地**(`prompts/supervisor.md`、`prompts/answer.md`);fake ChatModel 全图接线测试。
- **范围外**:不实现真实子智能体(05/09/10)、不实现 HITL 真逻辑(06)、不接 RAG。**契约与提示词组织方式一经本模块验收即冻结**,后续模块只能消费不能私改(改要走 ROADMAP §7 登记)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [02-persistence-cli](../02-persistence-cli/DEV.md) | checkpointer、REPL 骨架、run_turn |
| [01-minimal-agent](../01-minimal-agent/DEV.md) | `agent/build.py` 的 build_graph / make_llm |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `agent/contracts/route.py` | `Task`、`Route`(Pydantic) |
| `agent/contracts/task_contract.py` | `TaskContract`(任务契约四件套) |
| `agent/contracts/summary.py` | `ResultSummary`(结果摘要) |
| `agent/contracts/__init__.py` | 导出三个契约(对外唯一定义处) |
| `agent/state.py`(扩展) | `contract`/`subagent_results` 共享键;后者 `Annotated[list, _add_or_reset]`(哨兵重置 reducer) |
| `agent/contracts/subgraph.py` | `SubgraphContract`(子图输入校验 schema, Send payload 经它进入共享 contract 键;ADR-0009 §4) |
| `agent/subagents/stub.py` | 桩子图(真实编译 StateGraph,模拟执行回固定 ResultSummary) |
| `agent/supervisor.py` | 路由节点(结构化输出 + 回退;防死循环由 LangGraph 原生 `recursion_limit` + `GraphRecursionError` 兜底,见 ADR-0009 §2 争议 B)+ `build_contract()` |
| `agent/answer.py` | 汇总作答 + 消费即清 |
| `agent/subagents/stub.py` | 桩子图(真实编译 StateGraph,模拟执行回固定 ResultSummary) |
| `agent/build.py`(重构) | 六节点主图 + 回环边(子图按 ADR-0009 方案 A 直挂) |
| `settings/loader.py` | `load_prompt(name, **slots)`:importlib.resources 读 md + `$` 占位符渲染 |
| `prompts/supervisor.md` | 主智能体系统提示词(静态段 + `$skills_meta`/`$memory` 插槽;`$subagent_results` 已移至 answer 消息流,ROADMAP §7 登记) |
| `prompts/answer.md` | 汇总作答指令 |
| `tests/test_graph.py` | fake ChatModel 全图接线测试(核心资产)+ loader 单测 |

## 4. 分步任务清单

### T1:实现 settings/loader.py + 首批 md
```python
# settings/loader.py 要点
from importlib import resources
from string import Template

def load_prompt(name: str, **slots: str) -> str:
    """读 prompts/<name>.md 并渲染 $ 占位符。
    例:load_prompt("supervisor", agents_md=..., memory=..., skills_meta=..., subagent_results=...)"""
    text = resources.files("prompts").joinpath(f"{name}.md").read_text(encoding="utf-8")
    return Template(text).substitute(**slots)
```
- 占位符**必须用 `$name` 形式**(string.Template):提示词内有 JSON 示例花括号,str.format 会炸。
- [ ] 按设计写 `prompts/supervisor.md`(七段结构:人设 / agents.md 插槽 / 路由与子智能体能力清单 / Skills 元数据插槽 / 长期记忆插槽 / 子智能体结果插槽 / 输出格式约束,内容见 PROMPT-DESIGN.md §1.1)与 `prompts/answer.md`。
- 验收:单测--`load_prompt("supervisor", agents_md="X")` 返回含 "X" 的文本;缺失插槽时报 KeyError;md 内字面 JSON 花括号不引发渲染错误。

### T2:冻结三份契约(contracts/)
```python
# agent/contracts/route.py
class Task(BaseModel):
    agent: Literal["retriever", "research", "executor"]
    task: str; reason: str

class Route(BaseModel):
    next: Literal["answer", "memory", "dispatch", "ask"]
    question: str | None = None
    tasks: list[Task] | None = None

# agent/contracts/task_contract.py
class TaskContract(BaseModel):
    task: str; user_utterance: str
    input_data: dict; output_schema_hint: str

# agent/contracts/summary.py
class ResultSummary(BaseModel):
    agent: Literal["retriever", "research", "executor"]
    task_id: str; task: str
    status: Literal["success", "partial", "need_clarification", "failed"]
    conclusion: str; key_points: list[str] = []
    data: dict = {}; sources: list[str] = []
    needs_clarification: list[str] = []; warnings: list[str] = []
```
- 验收:pydantic 校验单测(合法/非法各一组)通过;`from agent.contracts import Route, TaskContract, ResultSummary` 可用。

### T3:扩展 AgentState + supervisor 节点
- [ ] 路由调用使用**全量 messages**(滑窗已废除,见 ADR-0009 R1;上下文压缩为 backlog);动态插槽 $memory 与 $skills_meta 在对应模块(06/07)落地前传空字符串。
- [ ] `subagent_results` 用带哨兵的自定义 reducer(`_add_or_reset`,见 T5);supervisor:`llm.with_structured_output(Route)` 解析(系统提示词经 `load_prompt("supervisor", ...)` 渲染),解析失败/校验失败 -> 回退 `next="answer"`;**不自己维护步数计数**——防死循环由运行时 `recursion_limit`(config 顶层键,初值 25)+ `run_turn` 捕获 `GraphRecursionError` 兜底(ADR-0009 §2 争议 B);`build_contract(task, state)` 纯函数(任务描述自包含 + 用户原话 + 结构化输入 + 输出提示);dispatch 时返回 `[Send(t.agent, {"contract": build_contract(t, state).model_dump()})]`。
- 验收:fake model 返回固定 Route 的单测:分别验证四条路由与回退分支。

### T4:桩子图 + 主图重构
- [ ] **先跑 ADR-0009 §5 第 0 步最小实验**(共享键直挂验证):主图 AgentState 与子图 SubgraphState 都声明 `contract`/`subagent_results` 共享键,编译子图直接 `add_node` 挂入主图,`Send("子图名", {"contract": ...})` 直达子图;验证 payload 经子图 schema 校验进入、`stream(subgraphs=True)` 可见子图内部节点。**实验通过按方案 A 直挂;失败降级方案 B wrapper(invoke 编译图 + try/except + 输出键校验),并登记三项代价**(checkpoint 不共享/流式不保证/异常不传播,见 ADR-0009 §2 争议 A)。桩子图 = 真实编译 StateGraph(内部 1 个节点回固定 ResultSummary),不再是单函数假桩。
- 验收:fake model 驱动 dispatch 路由,图中出现"supervisor->子图->supervisor->answer"完整轨迹(用 `graph.stream(stream_mode="updates")` 断言节点序列;方案 A 下 `subgraphs=True` 可断言子图内部节点)。

### T5:answer 消费即清
- [ ] answer 节点生成最终回答(提示词 `load_prompt("answer", ...)`,messages 用**全量**;子智能体结果作为对话流消息注入,不进系统提示词——ROADMAP §7 已登记),同时清空 `subagent_results`。
- **注意**:operator.add 加空列表不改变原值,清空需用"重置通道"实现(给 `subagent_results` 配自定义 reducer:收到哨兵值则重置为该值),实现前先在测试里验证行为。
- 验收:两轮 dispatch 后断言第二轮开始时 subagent_results 仅含本轮结果。

### T6:fake ChatModel 全图接线测试(test_graph.py)
- [ ] fake model 按脚本依次返回:Route(dispatch)-> 桩执行 -> Route(answer)-> 最终回复;断言轨迹、摘要累积、清空、回退、**递归超限(`recursion_limit=3` 触发 `GraphRecursionError` → run_turn 兜底消息)与路由乒乓(fake 持续 dispatch)**全部正确。**此测试是后续所有模块的回归基线。**
- 验收:`uv run pytest tests/test_graph.py -q` 全绿,零 API 成本、不 flake。

### T7:REPL 接入新图
- [ ] REPL 走重构后的 build_graph;终端打印路由轨迹一行(如 `[路由] dispatch -> retriever: <task>`,来自 Route.tasks[].reason)。
- 验收:真模型下问一个简单问题,看到轨迹与回答;问一个"需要查资料"的问题,看到 dispatch 到桩并诚实汇总。

## 5. 验收标准(整模块)

- [ ] fake 测试全绿(轨迹/累积/清空/回退/上限五类断言)+ loader 单测全绿;
- [ ] 真模型 REPL:两条消息分别触发 answer 直答与 dispatch 桩回路;
- [ ] contracts 三文件与两份 md 冻结,ROADMAP §6 契约表与代码一致;
- [ ] `ruff check .` 通过。

## 6. 核心概念速查

- **结构化输出 + 回退**:`with_structured_output(Route)`;失败兜底进 answer,保证图永不因解析错误挂死。
- **`Command(goto=...)` vs `Send(node, state)`**:前者单目标静态路由(answer/ask/memory);后者动态并行派发,Send 的第二个参数**直接成为目标节点的输入**(这就是子图独立上下文的机制)。
- **`_add_or_reset` reducer**(含 `operator.add` 语义):并行分支各自返回摘要列表,引擎自动合并;哨兵重置见 T5。
- **`recursion_limit`**:LangGraph 原生递归上限(config 顶层键,非 `configurable`),父图+子图 super-step 总和;超限抛 `GraphRecursionError`,由 `run_turn` 捕获兜底(ADR-0009 §2 争议 B)。
- **共享键直挂 vs wrapper**(ADR-0009 §2 争议 A):直挂只需父子共享键(contract/subagent_results),schema 不必相同;wrapper 仅作 fallback。
- **fan-in**:同一轮所有 Send 完成后才走下一节点,无需手写等待。
- 详见 DESIGN.md §2、ADR-0006 与 ADR-0009。

## 7. 常见坑与规避

| 坑 | 表现 | 规避 |
|---|---|---|
| 消费即清用空列表无效 | operator.add 加空列表不改变原值 | 自定义 reducer + 哨兵重置,见 T5 |
| 自己数消息防死循环 | 与官方机制重复且易错 | 用 `recursion_limit` + 捕获 `GraphRecursionError`,见 T3/T6 |
| prompt 占位符用 `{}` | md 内 JSON 花括号引发 format 崩溃 | 一律 `$name` + Template,loader 单测覆盖 |
| Send 的输入绕过主图 state | 子图拿不到 messages | 这是**特性**不是 bug:契约必须自包含,缺信息说明 build_contract 写漏 |
| 路由 JSON 不合法 | 图挂死 | 回退 answer + 记日志,见 T3 |
| 并行分支共享 state 可变对象 | 数据竞争 | 子图只读契约副本,输出只经 reducer |
| 子结果只渲染 `conclusion` 等决策字段 | 子智能体查到的正文永远到不了 answer(异步派发下"每次都被截断") | 正文必须经 `ResultSummary.data` / `sources` 回传;`_render_results(..., with_evidence=True)` 由 answer 侧开启(带预算),supervisor 侧保持精简。见 troubleshooting/03 §14 |

## 8. 契约接口

**本模块定义并冻结**(全项目唯一权威,见 ROADMAP §6):`Route`/`Task`/`TaskContract`/`ResultSummary`(`agent/contracts/`)、`AgentState`(`agent/state.py`)、`build_contract()`(`agent/supervisor.py`)、`load_prompt()`(`settings/loader.py`)、主图六节点名称(`supervisor`/`answer`/`ask`/`memory`/`retriever`/`research`/`executor`)、prompts md 文件的命名与占位符规范。

**本模块消费**:`build_graph`/`run_turn`(01)、checkpointer(02)。
