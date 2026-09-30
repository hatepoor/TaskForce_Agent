# agent_opt_0.1 · 02-retriever 并入 answer(P1)

> 状态:**❌ 已否决(2026-09-28,用户裁决:retriever 保持独立子智能体,不并入 answer)。本篇仅存档,勿按其实施。**
> KB 问答的回传质量问题改由 01(成稿回传)覆盖:retriever 收尾协议改严格 JSON + report,见 01 §三/§四。

## 一、目标

删除 retriever 子图,`kb_search` 作为普通工具挂进 answer 的工具循环。收益:

- KB 问答从"子图隔离 → 有损摘要 → answer 重建"变成 **answer 一个循环内直达命中原文**,摘要环节消失(诊断 1 的管道对 KB 问答整体失效);
- 主图 9 节点 → 8 节点,BUILDERS/派发/plan 的 agent 枚举少一类,`TaskManager._run` 的兜底分支简化;
- `prompts/subagents/retriever.md`(326 行的协议提示词)退役。

不动:`kb_search` 工具本身(`tools/rag/kb_search.py`,工具名与 JSON 五键契约是既有外部约定)、TaskManager 台账机制、research/executor 子图。

## 二、装配改动:`answer.py`

```python
from tools.rag.kb_search import make_kb_search

MEMORY_LOOP_MAX = 6  # answer 工具循环上限:kb 检索可能 2~3 次 + 记忆 1~2 次,4 不够用
_ANSWER_TOOLS_DEFAULT = None  # 惰性构造:模块 import 时不触发 rag_v01 解析栈(见 kb_search 同款理由)


def build_answer_tools(kbBackend=None) -> list:
    """answer 工具集工厂(c6 同款注入 seam):测试传假检索后端,不打桩模块符号。
    缺省后端在首次调用时才经 _default_search 惰性 import rag_v01。"""
    return [*MEMORY_TOOLS, get_current_time, make_kb_search(kbBackend)]


def _answer_tools() -> list:
    """进程内默认工具集(惰性单例):生产路径零成本,测试用 build_answer_tools 显式注入。"""
    global _ANSWER_TOOLS_DEFAULT
    if _ANSWER_TOOLS_DEFAULT is None:
        _ANSWER_TOOLS_DEFAULT = build_answer_tools()
    return _ANSWER_TOOLS_DEFAULT
```

`_answer_with_memory` 与 `answer_node` 加工具注入参数:

```python
def _answer_with_memory(llm, messages, tools) -> AIMessage:
    """answer 侧工具循环:记忆 + 时钟 + kb_search(原逻辑不变,工具集参数化)。"""
    llm_with_tools = llm.bind_tools(tools)
    # ...循环体逐行不动,只把 ANSWER_TOOLS 替换为 tools...


def answer_node(state: AgentState, llm, tools=None) -> dict:
    ...
    res = _answer_with_memory(llm, messages, tools if tools is not None else _answer_tools())
```

`build.py` 的挂接 `lambda s: answer_node(s, llm)` **不变**(缺省参数兜住)。

`answer.md`「可用工具」段追加一行:

```
- `kb_search(query, top_k=5)`:检索用户上传的知识库文档,返回命中片段列表(JSON 数组:
  doc_id/filename/seq/content/score,content 已含父块全文节选)。复合问题拆成多条名词短语
  查询分别检索;命中即引用《文件名》作答,禁止把常识伪装成检索结果。
```

## 三、契约收窄(两处 Literal,两档处理)

**直接收窄(LLM 输出侧,无存量风险):**

- `contracts/route.py` `Task.agent`:`Literal["retriever", "research", "executor"]` → `Literal["research", "executor"]`。旧 checkpoint 的 `last_route` 里有 `agent="retriever"` 的历史 dict——它**不再被校验回 Route**(repl `_print_route` 的还原要加容错,见第五节)。
- `contracts/plan.py` `PlanStepDraft.assignee` 同步收窄:planner LLM 从源头产不出 retriever 步骤。

**保留宽 Literal(持久化侧,防存量 checkpoint 崩):**

- `PlanStep.assignee` **不收窄**:旧计划里有 `assignee="retriever"` 的未完成步骤,`_advance_plan` 每轮 `Plan.model_validate(state['plan'])`,Literal 一收窄旧会话直接 ValidationError 崩轮。改为**派发防御**——`planner.py` 的 `_dispatch_ready` 在组装派发任务时跳过 BUILDERS 里不存在的 assignee:

```python
        if step.assignee not in BUILDERS:
            # 旧 checkpoint 的 retriever 步:子图已下线,诚实记失败而不是让后台线程 KeyError
            plan.mark_by_task(... )  # 该步直接落 failed,digest 写明"retriever 已并入 answer,请重新规划"
            continue
```

(以 `grep -n "Assignee\|assignee" src/agent/contracts/plan.py src/agent/planner.py` 实际结果为准,此处给的是落点与语义。)

**ROADMAP §7 契约变更登记先行。**

## 四、注册表与主图装配

- `subagents/registry.py`:import 与 `BUILDERS` 删 `retriever` 行(字典剩两项);文件头注释"三个子图"改"两个"。
- `build.py`:`b.add_node("retriever", get_subgraph(llm, "retriever"))` 删除;fan-in 循环 `for name in ("retriever", "research", "executor")` 去掉 `"retriever"`。
- `tasks.py` `_run` 兜底:`safe_agent = agent if agent in BUILDERS else "retriever"` → `else "research"`(retriever 已不存在,兜底语义改为"未知 agent 按 research 降级")。
- 主图节点数 9 → 8;`tests/test_graph.py`、`test_memory_inject.py` 等处对节点清单/口径的断言同步(智能体改)。

## 五、提示词与 REPL

- `prompts/supervisor.md`:
  - 「子智能体能力清单」删 retriever 条目,标题"只能派以下三个"改"两个";
  - 输出格式的 `"retriever|research|executor"` 改 `"research|executor"`;
  - 规则与能力描述里"知识库检索"类指引改口径:**知识库问答不再派发,由 answer 直接检索**(如规则 1 举例、plan/dispatch 界线段落里涉及 retriever 的句子);
  - `prompts/planner.md` 若有派发对象枚举/清单,同步删(以 `grep -n retriever src/prompts/` 实际结果为准)。
- `cli/repl.py` `_print_route`:Route 还原加 try/except,失败退回打印原始 dict(旧 checkpoint 的 last_route 含 retriever 时不崩)。

## 六、退役文件

- `src/agent/subagents/retriever.py` 删除;
- `src/prompts/subagents/retriever.md` 删除;
- `tests/test_retriever.py` 删除,其测试意图(命中/空命中/超限 partial)迁移为 answer 侧用例(第七节)。

历史文档不删:`docs/guide/`、troubleshooting 里的 retriever 叙述属存档口径,新文档另述。

## 七、测试(智能体负责)

- answer + kb_search 联测:经 `build_answer_tools(假后端)` 注入,fake LLM 产 tool_calls → 断言 ToolMessage 内容 = 假后端命中(复用 test_kb_search 的假件形态,不 monkeypatch);
- 循环上限 6 下多轮 kb + memory 混合调用收尾正常;
- 路由枚举:fake 路由输出 agent=retriever 应被 Pydantic 拒绝 → 走 route None 回退 answer;
- plan 存量步骤防御:含 `assignee="retriever"` 的 Plan 走 `_advance_plan` 不崩、该步落 failed;
- 全量回归(删 test_retriever 后总数 -N,基线在 TODO.md 记录)。

## 八、验收

1. 全量 pytest 绿;`uv run ruff check .` 干净;
2. 冒烟:KB 问答(`❯ 总结一下知识库里这份年报...`)回答直接引用命中原文细节,REPL 轨迹无 retriever 事件;
3. 旧会话(含 retriever 派发史)切回不崩:历史回填、轨迹打印、plan 恢复三条路径都过一遍。
