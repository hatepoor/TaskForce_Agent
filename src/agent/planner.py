"""计划节点:plan_draft(LLM 生成计划)与 plan_confirm(HITL 确认 + 首批派发)。

本文件作用:
    Plan-and-Execute 的两个主图节点(plan_0.1)——
    plan_draft 调一次结构化输出把用户目标变成 PlanDraft,校验后装配成 Plan 落 state;
    plan_confirm 是**纯确定性节点**:interrupt 挂起等用户确认,批准后把首批(无依赖步)
    交 TaskManager 后台派发。

    拆成两个节点是硬约束:interrupt 的 resume 会让节点整体重跑,若把"调 LLM 生成计划"
    和"挂起确认"放同一节点,resume 后会再调一次 LLM(温度 0.7,计划漂移),见
    docs/20-决策与方案/modules/plan_0.1/02-规划与确认节点.md 与 ADR-0012。

使用位置:
    - agent/build.py:build_graph 挂两节点(plan_draft -> plan_confirm 静态边);
    - agent/supervisor.py:route_node 的 next=="plan" 分支经 Command(goto="plan_draft") 进入;
    - tests/test_planner.py / tests/test_plan_confirm.py。
"""
import sys

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from langgraph.types import Command, interrupt

from agent.contracts import Plan, PlanDraft, TaskContract, plan_payload
from agent.state import AgentState

# 派发上限与 supervisor 共用一处常量(planner -> supervisor 单向 import,无环)
from agent.supervisor import MAX_PARALLEL_SUBAGENTS
from settings.loader import load_prompt

# resume 值判定为"批准"的词表;其余一律取消(计划有误宁可让用户重问,不猜意图)
_APPROVE_WORDS = {"y", "yes", "ok", "确认", "确认执行", "同意", "可以"}


def _approved(decision) -> bool:
    """interrupt 的 resume 值 -> 是否批准。"""
    return str(decision).strip().lower() in _APPROVE_WORDS


def _last_user_text(state: AgentState) -> str:
    """取最近一条真实用户消息作为规划目标(意图锚点,防重构失真)。"""
    for m in reversed(state.get("messages") or []):
        if getattr(m, "type", "") == "human":
            content = m.content
            return content if isinstance(content, str) else str(content)
    return ""


def _step_contract(plan: Plan, step) -> TaskContract:
    """单步 -> 任务契约:detail 即自包含任务;依赖步的结论摘要拼进任务文本,
    否则下游子图拿不到前序产出(子图只看契约,没有对话历史)。"""
    prior = {
        s.id: s.result_digest
        for s in plan.steps
        if s.id in step.depends_on and s.result_digest
    }
    task = step.detail
    if prior:
        ctx = ";".join(f"{k} 结论:{v}" for k, v in prior.items())
        task = f"{step.detail}\n(前序步骤结论:{ctx})"
    return TaskContract(
        task=task,
        user_utterance=plan.goal,
        input_data={},
        output_schema_hint="按 ResultSummary 返回:conclusion / key_points / data / sources",
    )


def _dispatch_ready(
        plan: Plan,
        tasks,
        thread_id: str,
        limit: int = MAX_PARALLEL_SUBAGENTS
    ) -> list[str]:
    """把当前 ready 步交后台派发,返回派出的 task_id 列表(空=无可派)。

    submit 返回的 task_ids 与 jobs 顺序严格对应(tasks.py:36-49),对账全靠它:
    回填到 PlanStep.task_id,后续用 ResultSummary.task_id 匹配。
    """
    if tasks is None:
        return []
    ready = plan.ready_steps()[:limit]
    if not ready:
        return []
    jobs = [(s.assignee, _step_contract(plan, s)) for s in ready]
    ids = tasks.submit(jobs, thread_id=thread_id)
    for s, tid in zip(ready, ids, strict=False):
        s.task_id = tid
        s.status = "running"
    return ids


def plan_draft_node(state: AgentState, llm) -> Command:
    """LLM 生成计划:结构化输出 -> 结构校验 -> 落 state.plan(不派发,交 plan_confirm)。"""
    if state.get("plan"):
        # 已有计划进行中:不再生成新计划(否则旧 plan 的 task_id 对账丢失、running 步成孤儿)
        return Command(
            goto="answer",
            update={
                "messages": [
                    AIMessage(
                        content="当前已有一个计划在执行中,等它跑完我再规划新的(会自动推进);"
                                "如需换方向,请明确说明放弃当前计划。"
                    )
                ]
            },
        )
    goal = _last_user_text(state)
    try:
        # method 必须显式指定(实测坑):默认走 json_schema response_format,
        # DeepSeek 端点不支持该类型(400),会被下面兜底成 answer——表现为 plan 永不触发。
        draft = llm.with_structured_output(PlanDraft, method="function_calling").invoke(
            [SystemMessage(content=load_prompt("planner")), HumanMessage(content=goal)]
        )
        draft.validate_structure()
    except Exception as e:
        print(f"[planner] 计划生成/校验失败,回退 answer:{e}", file=sys.stderr)
        return Command(
            goto="answer",
            update={
                "messages": [
                    AIMessage(content=f"这个需求我没能拆成计划({e}),先按单步来处理。")
                ]
            },
        )
    return Command(goto="plan_confirm", update={"plan": draft.to_plan().model_dump()})


def plan_confirm_node(state: AgentState, tasks, config=None) -> Command:
    """HITL 计划确认:挂起 -> 批准(派发首批)/ 取消(清计划回 answer)。

    纯确定性节点:resume 后重跑时不调 LLM,只按 resume 值分支(ADR-0012 决策 2)。
    """
    plan = Plan.model_validate(state["plan"])
    if tasks is None:
        # 无后台管理器(单测等场景):不支持串行推进,直接放弃而不是挂着(ADR-0012 决策 6)
        return Command(
            goto="answer",
            update={"plan": None, "messages": [AIMessage(
                content=f"当前运行方式不支持分批执行计划,已放弃:\n{plan.snapshot()}"
            )]},
        )
    decision = interrupt(
        plan_payload(plan.snapshot() + "\n\n回复 y 确认执行;其他任意输入视为取消。")
    )
    if not _approved(decision):
        return Command(
            goto="answer",
            update={"plan": None, "messages": [AIMessage(
                content=f"已取消该计划执行(你的回复:{decision})。需要调整目标请直接说明。"
            )]},
        )
    thread_id = ((config or {}).get("configurable") or {}).get("thread_id") or ""
    ids = _dispatch_ready(plan, tasks, thread_id)
    if not ids:  # 兜底:计划里没有任何可起步的步骤(理论上被 validate_structure 拦住)
        return Command(
            goto="answer",
            update={
                "plan": None,
                "messages": [AIMessage(content="计划里没有可执行的步骤,已终止。")],
            },
        )
    return Command(
        goto=END,
        update={
            "plan": plan.model_dump(),
            "messages": [AIMessage(
                content=f"计划已确认,已派发首批 {len(ids)} 步:\n{plan.snapshot()}"
            )],
        },
    )
