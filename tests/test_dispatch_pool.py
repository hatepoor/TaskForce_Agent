"""回归:计划收口轮不吞用户请求 + 线程池给临时 dispatch 留位。

教学模式下先写红测试:用户誊写 supervisor/tasks 的改动后,本文件应全绿。
"""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.build import build_graph
from agent.contracts import PlanDraft, ResultSummary, Route, Task
from agent.service import AUTO_NOTICE
from agent.supervisor import MAX_PARALLEL_SUBAGENTS, _advance_plan
from agent.tasks import MAX_WORKERS


class _FakeTasks:
    """记录 submit,并可注入已完成结果供 drain_done 消费。"""

    def __init__(self):
        self.submitted = []
        self._results = {}
        self._n = 0

    def submit(self, jobs, thread_id=""):
        self.submitted.extend(jobs)
        ids = []
        for _ in jobs:
            self._n += 1
            ids.append(f"t{self._n}")
        return ids

    def complete(self, task_id: str) -> None:
        self._results[task_id] = ResultSummary(
            agent="research",
            task_id=task_id,
            task="任务回显",
            status="success",
            conclusion="完成",
        )

    def drain_done(self, thread_id=None):
        out = list(self._results.values())
        self._results.clear()
        return out

    def has_done(self, thread_id=None):
        return bool(self._results)

    def status(self, thread_id=None):
        return {"pending": 0, "done": len(self._results)}


def _finished_plan() -> dict:
    """单步计划,直接标 done:模拟最后一批结果已回收、计划已收口。"""
    draft = PlanDraft(
        goal="对比两家公司毛利率",
        steps=[
            {"id": "s1", "title": "取数", "detail": "自包含描述", "assignee": "research"},
        ],
    )
    plan = draft.to_plan()
    plan.steps[0].status = "done"
    plan.steps[0].result_digest = "完成"
    return plan.model_dump()


def _state(lastMessage: str) -> dict:
    return {
        "plan": _finished_plan(),
        "messages": [HumanMessage(content=lastMessage)],
        "subagent_results": [],
    }


def test_finished_plan_user_round_continues_routing():
    """计划收口与用户新消息同轮:返回 None,让 route_node 继续处理用户新话。"""
    goto, update = _advance_plan(_state("顺便查下后天扬州天气"), [], _FakeTasks())

    assert goto is None
    assert update["plan"] is None
    assert "计划执行完毕" in update["messages"][0].content


def test_finished_plan_wake_round_still_answers():
    """AUTO_NOTICE 唤醒轮没有用户新话:保持 goto answer 收口汇总。"""
    goto, update = _advance_plan(_state(AUTO_NOTICE), [], _FakeTasks())

    assert goto == "answer"
    assert update["plan"] is None


class _FourTaskLLM:
    """路由一次返回 4 个任务,用于验证异步分支的代码级截断。"""

    def with_structured_output(self, schema, **kwargs):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return Route(
            next="dispatch",
            tasks=[
                Task(agent="research", task=f"任务{i}", reason="r")
                for i in range(4)
            ],
        )


def test_async_dispatch_clamps_to_parallel_limit():
    """异步 dispatch 也要截断:不能把模型超发的任务全塞进线程池队列。"""
    fake_tasks = _FakeTasks()
    graph = build_graph(
        llm=_FourTaskLLM(),
        checkpointer=InMemorySaver(),
        tasks=fake_tasks,
    )
    list(
        graph.stream(
            {"messages": [("user", "一次问四件事")]},
            {"recursion_limit": 25, "configurable": {"thread_id": "pool-clamp"}},
            stream_mode="updates",
        )
    )

    assert len(fake_tasks.submitted) == MAX_PARALLEL_SUBAGENTS


def test_worker_pool_reserves_slot_for_interactive_dispatch():
    """plan 批次最多占 3 个 worker,池子至少留 1 个空位给用户临时 dispatch。"""
    assert MAX_WORKERS >= MAX_PARALLEL_SUBAGENTS + 1


def _one_step_draft() -> PlanDraft:
    return PlanDraft(
        goal="对比两家公司毛利率",
        steps=[
            {"id": "s1", "title": "取数", "detail": "自包含描述", "assignee": "research"},
        ],
    )


class _PlanThenDispatchLLM:
    """首次路由 plan;计划收口后的用户轮路由 dispatch(模拟"顺便查天气")。"""

    def __init__(self, draft: PlanDraft):
        self._draft = draft
        self._routes = 0
        self._schema = None

    def with_structured_output(self, schema, **kwargs):
        self._schema = schema
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        schema, self._schema = self._schema, None
        if schema is PlanDraft:
            return self._draft
        if schema is Route:
            self._routes += 1
            if self._routes == 1:
                return Route(next="plan")
            return Route(
                next="dispatch",
                tasks=[Task(agent="research", task="查扬州天气", reason="用户新请求")],
            )
        return AIMessage(content="汇总")


def test_finished_plan_user_message_still_dispatches_new_task():
    """端到端:计划最后一步完成与用户"查天气"同轮,新任务仍要被提交。"""
    tasks = _FakeTasks()
    graph = build_graph(
        llm=_PlanThenDispatchLLM(_one_step_draft()),
        checkpointer=InMemorySaver(),
        tasks=tasks,
    )
    config = {"recursion_limit": 40, "configurable": {"thread_id": "pool-user-turn"}}

    list(
        graph.stream(
            {"messages": [("user", "做个毛利率计划")]},
            config,
            stream_mode="updates",
        )
    )
    list(graph.stream(Command(resume="y"), config, stream_mode="updates"))
    assert len(tasks.submitted) == 1  # s1 已派发

    tasks.complete("t1")
    list(
        graph.stream(
            {"messages": [("user", "顺便查下后天扬州天气")]},
            config,
            stream_mode="updates",
        )
    )

    st = graph.get_state(config)
    assert st.values["plan"] is None  # 计划已收口
    assert len(tasks.submitted) == 2  # 天气任务确实被提交
    assert tasks.submitted[1][1].task == "查扬州天气"
    texts = [str(m.content) for m in st.values["messages"]]
    assert any("计划执行完毕" in t for t in texts)
    assert any("已派发 1 个后台任务" in t for t in texts)
