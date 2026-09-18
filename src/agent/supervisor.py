"""主智能体路由节点:结构化输出+失败回退;防死循环 recursion_limit 兜底。

本文件作用:
    supervisor 是主图的"唯一叙事者"——读取全量 messages 结构化路由到
    answer/ask/memory,或经 Send fan-out 派发任务契约给子智能体;
    同时提供 任务->契约 的装配与 fan-out 命令的构造。

使用位置:
    - agent/build.py:build_graph() 中以 lambda(s) -> route_node(s, llm) 挂 supervisor 节点;
    - cli/repl.py:间接经 build_graph 使用;tests/test_graph.py 验证路由行为。
"""
import sys

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from langgraph.types import Command, Send

from agent.answer import _render_results
from agent.contracts import Route, Task, TaskContract
from agent.memory_ctx import load_agents_md
from agent.state import AgentState
from settings.loader import load_prompt
from tools.skills.loader import _skills_meta

MAX_PARALLEL_SUBAGENTS = 3
def build_contract(task:Task,state:AgentState)->TaskContract:
    """会话 -> 任务契约的纯函数:自包含任务 + 用户原话 + 结构化输入 + 输出提示。"""
    last=state["messages"][-1] if state["messages"] else None

    return TaskContract(
        task=task.task,
        user_utterance=last.content if last else "",
        input_data={},
        output_schema_hint="按 ResultSummary 返回:conclusion / key_points / data / sources"
    )


def dispatch_sends(tasks: list[Task], state: AgentState, route: Route | None = None) -> Command:
    """任务列表 -> Command(goto=[Send...])。

    实测:裸 [Send] 作为节点返回值会被当 state update 抛 InvalidUpdateError;
    fan-out 必须包在 Command(goto=[...]) 里。
    """
    if len(tasks)>MAX_PARALLEL_SUBAGENTS:
        print(
            f"[supervisor] 一次派发 {len(tasks)} 个任务,超过上限 {MAX_PARALLEL_SUBAGENTS},"
            "截断至前几个(其余丢弃)",
            file=sys.stderr,
        )
        tasks = tasks[:MAX_PARALLEL_SUBAGENTS]  # 截断
    sends = [
        Send(t.agent, {"contract": build_contract(t, state).model_dump()})
        for t in tasks
    ]
    return Command(
        goto=sends,
        update={"last_route": route.model_dump()} if route else {}
    )


def route_node(state: AgentState, llm, tasks=None, config=None) -> Command:
    """supervisor 节点:全量 messages 结构化路由;解析失败/校验失败回退 answer。

    统一返回 Command:goto 为节点名(answer/ask/memory)、END(异步派发确认)或
    Send 列表(dispatch_sends 同步通道,方案 A 后为备胎);last_route 记录路由决策,
    供 REPL 轨迹打印(run_turn 经 updates 观察)。
    不自己数步数:超限时 LangGraph 抛 GraphRecursionError,由 run_turn 兜底。
    config 由 LangGraph 注入(build.py 的 lambda 声明同名形参):从中取 thread_id,
    派发时记归属、回收时按线程 drain,多线程的后台结果不互相串。
    """
    thread_id = ((config or {}).get("configurable") or {}).get("thread_id") or None
    injected: list = []
    if tasks is not None:  # 异步派发回收:后台完成结果注入,走既有"结果已回收"渲染
        done = tasks.drain_done(thread_id)
        if done:
            injected = done
            state = {**state, "subagent_results": [*state.get("subagent_results", []), *done]}
    # 固定 system(ADR-0011):仅静态内容(角色 + agents.md + 规则 + 输出格式),
    # 记忆检索/子结果等动态内容一律走消息流,不进 system(保前缀缓存)。
    system = load_prompt("supervisor", skills_meta=_skills_meta(), agents_md=load_agents_md())
    messages = [SystemMessage(content=system), *state["messages"]]
    if state.get("subagent_results"):
        results = state["subagent_results"]
        note = ""
        if all(any("桩" in w for w in (r.warnings or [])) for r in results):
            # 桩结果重派不会产生新信息,显式告知以防乒乓;真子图(05/09/10)上线后此分支自动失效
            note = "\n(以上为桩子图模拟结果,未真实执行;重派不会获得新信息,请选择 answer 如实转达。)"
        messages.append(
            HumanMessage(
                content="子智能体结果已回收:\n" + _render_results(results) + note
            )
        )
    try:
        # method 显式指定(实测坑):langchain-openai 1.x 默认走 json_schema response_format,
        # DeepSeek 端点不支持该类型(400 invalid_request_error),会被下面静默兜底成 answer
        # ——表现为 SSE 无 route 帧、dispatch/ask/memory 永不触发。
        route = llm.with_structured_output(Route, method="function_calling").invoke(messages)
    except Exception as e:
        print(f"[supervisor] 结构化路由失败,回退 answer:{e}", file=sys.stderr)
        route = None
    # 统一 update:注入的后台结果必须写回主图 state(answer 节点才能读到汇总,
    # 否则只有路由 LLM 看到"已回收"段,answer 汇总时 state 里仍是空——实测坑)
    update: dict = {"last_route": route.model_dump()} if route else {}
    if injected:
        update["subagent_results"] = injected
    if route is None:
        return Command(goto="answer", update=update)
    if route.next == "dispatch":
        # 空任务列表(LLM 输出 tasks 为空)不能空转结束:否则图停在 supervisor,
        # run_turn 会把用户自己的消息当成回复返回。退化走 answer。
        if not route.tasks:
            return Command(goto="answer", update=update)
        if tasks is None:  # 无后台管理器(单测/备胎):走同步 Send 通道
            return dispatch_sends(route.tasks, state, route=route)
        # 异步派发(方案 A):提交后台线程池立即返回确认消息,用户可继续交互;
        # 结果由后续轮次 supervisor 经 tasks.drain_done() 回收注入。
        jobs = [(t.agent, build_contract(t, state)) for t in route.tasks]
        task_ids = tasks.submit(jobs, thread_id=thread_id or "")
        detail = "、".join(
            f"{agent}:{tid}" for (agent, _), tid in zip(jobs, task_ids, strict=False)
        )
        return Command(
            goto=END,
            update={
                **update,
                "messages": [AIMessage(
                    content=f"已派发 {len(task_ids)} 个后台任务:[{detail}]。"
                    "预计 1-3 分钟完成;完成后我会自动汇总,期间你可以继续聊别的。"
                )],
            },
        )
    return Command(goto=route.next, update=update)
