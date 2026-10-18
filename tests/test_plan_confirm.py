"""plan_confirm 节点测试(M3 验收):首批派发纯函数 + interrupt 挂起/确认/取消往返。

_interrupt 往返用整图 + InMemorySaver,模式参照 tests/test_ask.py;
派发细节用 FakeTasks 记录 submit,不起真线程池。
"""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.build import build_graph
from agent.contracts import PlanDraft, Route
from agent.planner import _dispatch_ready, _step_contract, plan_confirm_node


class FakeTasks:
    """假 TaskManager:记录 submit 并按 jobs 长度返回固定 id 序列。"""

    def __init__(self):
        self.submits = []
        self._n = 0

    def submit(self, jobs, thread_id=""):
        self.submits.append((thread_id, list(jobs)))
        ids = []
        for _ in jobs:
            self._n += 1
            ids.append(f"t{self._n}")
        return ids

    def drain_done(self, thread_id=None):
        return []

    def has_done(self, thread_id=None):
        return False


class FakePlanLLM:
    """fake:首轮路由 next="plan",plan_draft 阶段返回草案,之后给兜底回答。"""

    def __init__(self, draft):
        self._draft = draft
        self._routed = False
        self.schema = None

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        # 消费即重置 schema:否则 answer 节点再调时会误把草案当回答返回
        # (LangGraph 会把 PlanDraft 当消息类型抛 NotImplementedError)
        schema, self.schema = self.schema, None
        if schema is PlanDraft:
            return self._draft
        if not self._routed:
            self._routed = True
            return Route(next="plan")
        return AIMessage(content="已按计划汇总。")


def _draft() -> PlanDraft:
    return PlanDraft(
        goal="对比宁德时代与比亚迪 2024 年毛利率",
        steps=[
            {
                "id": "s1",
                "title": "查两家公司年报毛利率",
                "detail": "自包含描述",
                "assignee": "research",
            },
            {
                "id": "s2",
                "title": "计算差值与趋势",
                "detail": "自包含描述",
                "assignee": "executor",
                "depends_on": ["s1"],
            },
        ],
    )


# ---------------- _dispatch_ready:派发纯函数 ----------------

def test_dispatch_ready_dispatches_only_ready_steps():
    plan = _draft().to_plan()
    tasks = FakeTasks()
    ids = _dispatch_ready(plan, tasks, "th-1")
    assert ids == ["t1"]  # 只有 s1(无依赖)可派
    assert plan.steps[0].status == "running" and plan.steps[0].task_id == "t1"
    assert plan.steps[1].status == "pending" and plan.steps[1].task_id == ""
    thread_id, jobs = tasks.submits[0]
    assert thread_id == "th-1"
    assert [agent for agent, _c in jobs] == ["research"]
    assert jobs[0][1].task == "自包含描述"  # 契约 task=step.detail


def test_dispatch_ready_respects_limit():
    draft = PlanDraft(
        goal="g",
        steps=[
            {"id": f"s{i}", "title": f"步{i}", "detail": "d", "assignee": "research"}
            for i in range(1, 5)
        ],
    )
    plan = draft.to_plan()
    assert len(_dispatch_ready(plan, FakeTasks(), "th", limit=3)) == 3
    assert [s.status for s in plan.steps] == ["running", "running", "running", "pending"]


def test_step_contract_carries_prior_digest():
    """下游步契约必须带上前序步结论:子图只看契约、没有对话历史,
    拿不到 s1 的产出就没法计算(改动 3 的验收,2026-09-24 冒烟补)。"""
    plan = _draft().to_plan()
    plan.steps[0].status = "done"
    plan.steps[0].result_digest = "宁德 24.4%、比亚迪 20.1%"
    c = _step_contract(plan, plan.steps[1])
    assert "自包含描述" in c.task  # detail 原文保留(task 取的是 detail,不是 title)
    assert "s1 结论:宁德 24.4%、比亚迪 20.1%" in c.task  # 前序结论拼入任务文本


def test_dispatch_ready_without_manager_returns_empty():
    assert _dispatch_ready(_draft().to_plan(), None, "th") == []


def test_plan_confirm_without_manager_falls_back_to_answer():
    """tasks=None:不进入确认挂起(无后台管理器时直接放弃计划,ADR-0012)。"""
    cmd = plan_confirm_node({"plan": _draft().to_plan().model_dump()}, tasks=None)
    assert cmd.goto == "answer"
    assert cmd.update["plan"] is None


# ---------------- 整图:interrupt 挂起 -> 确认/取消 ----------------

def _run_to_interrupt(tasks, thread_id):
    graph = build_graph(FakePlanLLM(_draft()), InMemorySaver(), tasks=tasks)
    config = {"recursion_limit": 25, "configurable": {"thread_id": thread_id}}
    list(
        graph.stream(
            {"messages": [("user", "对比宁德时代与比亚迪 2024 年毛利率")]},
            config,
            stream_mode="updates",
        )
    )
    return graph, config


def test_plan_confirm_interrupts_before_dispatch():
    tasks = FakeTasks()
    graph, config = _run_to_interrupt(tasks, "plan-1")
    st = graph.get_state(config)
    assert st.interrupts and st.interrupts[0].value["kind"] == "plan"
    assert "📋 计划" in st.interrupts[0].value["text"]
    # 确认前:计划已落 state 但一步都没派发
    assert st.values["plan"]["steps"][0]["status"] == "pending"
    assert tasks.submits == []


def test_plan_confirm_approve_dispatches_first_batch():
    tasks = FakeTasks()
    graph, config = _run_to_interrupt(tasks, "plan-2")
    list(graph.stream(Command(resume="y"), config, stream_mode="updates"))
    st = graph.get_state(config)
    assert st.values["plan"]["steps"][0]["status"] == "running"
    assert st.values["plan"]["steps"][0]["task_id"] == "t1"
    assert st.values["plan"]["steps"][1]["status"] == "pending"  # 依赖 s1,第一批不派
    assert [agent for agent, _c in tasks.submits[0][1]] == ["research"]
    assert "已派发首批 1 步" in st.values["messages"][-1].content


def test_plan_confirm_reject_clears_plan():
    tasks = FakeTasks()
    graph, config = _run_to_interrupt(tasks, "plan-3")
    list(graph.stream(Command(resume="不执行,换个思路"), config, stream_mode="updates"))
    st = graph.get_state(config)
    assert st.values["plan"] is None
    assert tasks.submits == []  # 取消不派发
    # 取消提示进消息历史(reject 后图继续走到 answer,末条会是回答,故查任意一条)
    texts = [m.content for m in st.values["messages"] if isinstance(m.content, str)]
    assert any("已取消" in t for t in texts)


# ---------------- 回归:planner 400 回退不得被拉进 plan_confirm ----------------

class BoomPlanLLM:
    """路由到 plan,但计划生成抛 400(模拟思考模式不支持强制 tool_choice)。"""

    def __init__(self):
        self._routed = False
        self.schema = None

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        schema, self.schema = self.schema, None
        if schema is PlanDraft:
            raise Exception("Error code: 400 - Thinking mode does not support this tool_choice")
        if not self._routed:
            self._routed = True
            return Route(next="plan")
        return AIMessage(content="已按单步处理")


class AnswerOnlyLLM:
    """只会回答的 LLM:被 planner 用于结构化输出即断言失败。"""

    def with_structured_output(self, schema, **kwargs):
        if schema is PlanDraft:
            raise AssertionError("planner 不应使用回答 LLM(思考模式会 400)")
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return AIMessage(content="回答")


class RouteAndPlanLLM:
    """routeLlm 替身:路由到 plan,并返回计划草案。"""

    def __init__(self, draft):
        self._draft = draft
        self._routed = False
        self.schema = None

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        schema, self.schema = self.schema, None
        if schema is PlanDraft:
            return self._draft
        if not self._routed:
            self._routed = True
            return Route(next="plan")
        return AIMessage(content="回答")


def test_plan_confirm_missing_plan_returns_answer_not_keyerror():
    """state 无 plan 时给可读兜底,不再 KeyError('plan')(实测坑)。"""
    cmd = plan_confirm_node({}, tasks=None)
    assert cmd.goto == "answer"
    assert cmd.update["plan"] is None
    assert "计划状态已丢失" in cmd.update["messages"][0].content


def test_plan_draft_failure_falls_back_without_plan_confirm():
    """planner 结构化调用 400 回退 answer:不得再被静态边拉进 plan_confirm。"""
    graph = build_graph(BoomPlanLLM(), InMemorySaver(), tasks=FakeTasks())
    config = {"recursion_limit": 25, "configurable": {"thread_id": "plan-boom"}}
    list(
        graph.stream(
            {"messages": [("user", "对比宁德时代与比亚迪 2024 年毛利率")]},
            config,
            stream_mode="updates",
        )
    )
    st = graph.get_state(config)
    assert not st.interrupts  # 没有 plan 挂起
    assert not st.values.get("plan")  # 回退路径不落计划
    texts = [m.content for m in st.values["messages"] if isinstance(m.content, str)]
    assert any("没能拆成计划" in t for t in texts)


def test_plan_draft_uses_route_llm_for_forced_tool_choice():
    """planner 与 supervisor 一样必须用关思考的 routeLlm,否则真实端点 400。"""
    graph = build_graph(
        AnswerOnlyLLM(),
        InMemorySaver(),
        tasks=FakeTasks(),
        routeLlm=RouteAndPlanLLM(_draft()),
    )
    config = {"recursion_limit": 25, "configurable": {"thread_id": "plan-route-llm"}}
    list(
        graph.stream(
            {"messages": [("user", "对比宁德时代与比亚迪 2024 年毛利率")]},
            config,
            stream_mode="updates",
        )
    )
    st = graph.get_state(config)
    assert st.interrupts and st.interrupts[0].value["kind"] == "plan"
