"""模块 03 单测:loader 渲染 + supervisor 路由 + 全图 dispatch 轨迹(T4)。

T6 在此文件补全:摘要累积/清空/回退/递归超限/路由乒乓。
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command, Send

from agent.answer import (
    EVIDENCE_ITEM_CHARS,
    EVIDENCE_ITEMS_MAX,
    EVIDENCE_TOTAL_CHARS,
    _render_results,
)
from agent.build import build_graph
from agent.contracts import ResultSummary, Route, Task
from agent.service import run_turn
from agent.supervisor import (
    MAX_PARALLEL_SUBAGENTS,
    build_contract,
    dispatch_sends,
    route_node,
)
from settings.loader import load_prompt

# ---------- loader 单测(T1 验收补充) ----------

def test_load_prompt_renders_slots():
    # supervisor.md 固定 system 仅两个动态插槽:skills_meta / agents_md(ADR-0011 移除 $memory)
    text = load_prompt("supervisor", skills_meta="SKILL_META", agents_md="AGENTS")
    assert "SKILL_META" in text
    assert "AGENTS" in text


def test_load_prompt_missing_slot_raises():
    with pytest.raises(KeyError):
        load_prompt("supervisor")


def test_load_prompt_json_braces_ok():
    # md 内的字面 JSON 花括号不应引发渲染错误
    text = load_prompt("supervisor", skills_meta="", memory="", agents_md="")
    assert "{" in text and "}" in text


# ---------- supervisor 路由单测 ----------

class FakeStructuredLLM:
    """fake ChatModel:with_structured_output 返回自身,invoke 返回预设 Route/None/抛异常。"""

    def __init__(self, route=None, exc=None):
        self._route = route
        self._exc = exc

    def with_structured_output(self, schema, **kwargs):
        return self

    def invoke(self, messages):
        if self._exc:
            raise self._exc
        return self._route


def _state(messages=None):
    return {
        "messages": messages or [HumanMessage(content="你好")],
        "subagent_results": [],
    }


def test_route_answer():
    r = route_node(_state(), FakeStructuredLLM(Route(next="answer")))
    assert isinstance(r, Command) and r.goto == "answer"


def test_route_ask():
    r = route_node(_state(), FakeStructuredLLM(Route(next="ask", question="要哪一年的?")))
    assert isinstance(r, Command) and r.goto == "ask"


def test_route_memory():
    r = route_node(_state(), FakeStructuredLLM(Route(next="memory")))
    assert isinstance(r, Command) and r.goto == "memory"


def test_route_dispatch_single_send():
    tasks = [Task(agent="retriever", task="查知识库中的 X", reason="需引用资料")]
    r = route_node(_state(), FakeStructuredLLM(Route(next="dispatch", tasks=tasks)))
    assert isinstance(r, Command)
    assert len(r.goto) == 1
    s = r.goto[0]
    assert isinstance(s, Send) and s.node == "retriever"
    assert s.arg["contract"]["task"] == "查知识库中的 X"


def test_route_dispatch_multi_send():
    """T4 多任务并行派发:同一子智能体可多实例,一次返回多个 Send(≤ 上限)。"""
    tasks = [
        Task(agent="research", task="调研A", reason="r1"),
        Task(agent="research", task="调研B", reason="r2"),
        Task(agent="retriever", task="查X", reason="r3"),
    ]
    r = route_node(_state(), FakeStructuredLLM(Route(next="dispatch", tasks=tasks)))
    assert len(r.goto) == 3
    assert [s.node for s in r.goto] == ["research", "research", "retriever"]


def test_dispatch_clamps_over_limit():
    """T4 超过 MAX_PARALLEL_SUBAGENTS 的任务被截断,不超并发上限。"""
    tasks = [Task(agent="research", task=f"调研{i}", reason="r") for i in range(5)]
    r = route_node(_state(), FakeStructuredLLM(Route(next="dispatch", tasks=tasks)))
    assert len(r.goto) == MAX_PARALLEL_SUBAGENTS


def test_dispatch_contract_uses_user_utterance():
    state = _state(
        messages=[HumanMessage(content="上一句"), HumanMessage(content="当前问题")]
    )
    tasks = [Task(agent="research", task="调研 Y", reason="时效信息")]
    s = dispatch_sends(tasks, state).goto[0]
    assert s.arg["contract"]["user_utterance"] == "当前问题"


def test_build_contract_fields():
    state = _state(messages=[HumanMessage(content="我的原始问题")])
    c = build_contract(Task(agent="executor", task="写脚本", reason="执行"), state)
    assert c.user_utterance == "我的原始问题"
    assert c.input_data == {}
    assert c.output_schema_hint


def test_route_fallback_on_none():
    r = route_node(_state(), FakeStructuredLLM(route=None))
    assert isinstance(r, Command) and r.goto == "answer"


def test_route_fallback_on_exception():
    r = route_node(_state(), FakeStructuredLLM(exc=ValueError("bad json")))
    assert isinstance(r, Command) and r.goto == "answer"


def test_route_node_injects_subagent_results():
    """子结果回收后 supervisor 调用注入结果消息(防乒乓:让 LLM 知道该汇总)。"""
    seen = {}

    class RecordingLLM(FakeStructuredLLM):
        def invoke(self, messages):
            seen["messages"] = messages
            return self._route

    summary = ResultSummary(
        agent="retriever", task_id="s1", task="查X", status="success", conclusion="找到了"
    )
    state = _state()
    state["subagent_results"] = [summary]
    route_node(state, RecordingLLM(Route(next="answer")))
    texts = [getattr(m, "content", "") for m in seen["messages"]]
    assert any("子智能体结果已回收" in t for t in texts)


# ---------- T4 全图接线测试(第 0 步实验已通过,方案 A 直挂) ----------

class FakeScriptedLLM:
    """fake ChatModel,按消息形态分发(bind_tools 在建图时调用,不能靠它标记模式):
    - pending=route(with_structured_output(Route),单发)→ routes 脚本(supervisor 路由);
    - 首条系统提示含 kb_search(retriever agent 首帧)→ 返回下一个 tool_round;
    - 消息含 ToolMessage(react 续轮)→ tool_rounds 按序,耗尽自动返回收尾消息;
    - 其余普通 invoke → routes 脚本(answer 节点)。
    """

    def __init__(self, routes, tool_rounds=None):
        self._routes = iter(routes)
        self._tool_rounds = list(tool_rounds or [
            AIMessage(content="", tool_calls=[{
                "name": "kb_search", "args": {"query": "昆玉河"},
                "id": "call_1", "type": "tool_call",
            }]),
        ])
        self._pending = None
        self._round_i = 0
        self.inputs: list[list] = []  # 记录每次 invoke 的输入(回收注入断言用)

    def with_structured_output(self, schema, **kwargs):
        self._pending = "route"
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.inputs.append(list(messages))
        if self._pending == "route":
            self._pending = None
            return next(self._routes)
        first = getattr(messages[0], "content", "") or ""
        # 子图判定用 base 底座特征串(勿用 "web_search":answer 提示词经 mcp_meta 也含该词)
        is_subagent = "只拥有本系统提示与任务契约" in first or any(
            isinstance(m, ToolMessage) for m in messages
        )
        if is_subagent:
            if self._round_i < len(self._tool_rounds):
                msg = self._tool_rounds[self._round_i]
                self._round_i += 1
                return msg
            return AIMessage("子任务完成")  # research 等子图帧直接收尾,不吞 supervisor 的 routes
        return next(self._routes)


class _FakeKbStore:
    """假知识库:任何查询都返回一条固定命中(retriever ReAct 子图测试用)。"""

    def search(self, query, top_k=5):
        return [{"doc_id": "d1", "filename": "kb.md", "seq": 0,
                 "content": "知识库命中:昆玉河沿岸有玉渊潭公园。", "score": 0.1}][:top_k]


@pytest.fixture(autouse=True)
def _fake_retriever_store(monkeypatch):
    """retriever 子图不依赖真实 DB/embedding:统一替换 kb_search 的默认 store。"""
    monkeypatch.setattr("tools.rag.kb_search._default_store", lambda: _FakeKbStore())


def _trace(graph, text="帮我查X"):
    events = []
    for _ns, ev in graph.stream(
        {"messages": [("user", text)]},
        {"recursion_limit": 25},
        stream_mode="updates",
        subgraphs=True,
    ):
        events.append((_ns, ev))
    return events


class _FakeTasks:
    """假 TaskManager(方案 A):submit 记录 jobs 与线程归属;drain_done 按线程过滤。

    结果列表存 (thread_id, ResultSummary) 二元组,模拟真实现里"结果带归属"的记账。
    """

    def __init__(self, results=None, thread_id=""):
        self.submitted: list = []
        self.thread_ids: list[str] = []
        self.results: list[tuple[str, ResultSummary]] = [
            (thread_id, r) for r in (results or [])
        ]

    def submit(self, jobs, thread_id=""):
        self.submitted.extend(jobs)
        self.thread_ids.append(thread_id)
        return [f"t{i}" for i in range(len(jobs))]

    def drain_done(self, thread_id=None):
        take = [r for t, r in self.results if thread_id is None or t == thread_id]
        self.results = [p for p in self.results if not (thread_id is None or p[0] == thread_id)]
        return take

    def has_done(self, thread_id=None):
        return any(thread_id is None or t == thread_id for t, _ in self.results)

    def status(self, thread_id):
        return {
            "pending": 0,
            "done": sum(1 for t, _ in self.results if t == thread_id),
        }


def test_full_dispatch_async_submits_then_ends():
    """异步派发(方案 A):dispatch 提交后台任务后立即 END,不跑子图,用户可继续交互。"""
    from langgraph.checkpoint.memory import InMemorySaver

    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[Task(agent="retriever", task="查知识库X", reason="需引用")]),
    ])
    fake_tasks = _FakeTasks()
    graph = build_graph(llm=fake, checkpointer=InMemorySaver(), tasks=fake_tasks)
    config = {"configurable": {"thread_id": "t-asy-0"}, "recursion_limit": 25}
    names = [
        next(iter(ev))
        for ev in graph.stream({"messages": [("user", "问")]}, config, stream_mode="updates")
    ]
    assert names == ["supervisor"]  # 派发轮只有 supervisor,图即结束(不再进入子图)
    assert len(fake_tasks.submitted) == 1
    assert fake_tasks.submitted[0][0] == "retriever"
    final = graph.get_state(config).values["messages"][-1]
    assert "已派发" in final.content


def test_full_dispatch_recovery_injects_then_answer():
    """回收轮:supervisor drain 到完成结果 → 注入 subagent_results → answer 汇总消费即清。"""
    from langgraph.checkpoint.memory import InMemorySaver

    summary = ResultSummary(
        agent="research", task_id="s1", task="调研Y",
        status="success", conclusion="LangGraph 偏底层编排", key_points=["图状态"],
    )
    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[Task(agent="research", task="调研Y", reason="r")]),
        Route(next="answer"),
        AIMessage("汇总。"),
    ])
    fake_tasks = _FakeTasks()
    graph = build_graph(llm=fake, checkpointer=InMemorySaver(), tasks=fake_tasks)
    config = {"configurable": {"thread_id": "t-asy-1"}, "recursion_limit": 40}

    # 第一轮:dispatch → 确认消息 END,结果未注入
    list(graph.stream({"messages": [("user", "调研Y")]}, config, stream_mode="updates"))
    msgs = graph.get_state(config).values["messages"]
    assert "已派发" in msgs[-1].content
    assert graph.get_state(config).values["subagent_results"] == []

    # 第二轮前:后台任务"完成"写入结果;回收轮注入 → answer 汇总,消费即清
    fake_tasks.results = [("t-asy-1", summary)]
    events = list(graph.stream(
        {"messages": [("user", "结果怎么样")]}, config, stream_mode="updates"
    ))
    names = [next(iter(ev)) for ev in events]
    assert names == ["supervisor", "answer"]
    # 注入结果必须真正到达 answer 帧(实测坑:注入只落在 supervisor 局部 state,
    # Command.update 未写回主图 → answer 汇总时仍空)
    answer_input = fake.inputs[-1]
    assert any("LangGraph 偏底层编排" in getattr(m, "content", "")
               for m in answer_input)
    assert graph.get_state(config).values["subagent_results"] == []
    assert graph.get_state(config).values["messages"][-1].content == "汇总。"


def test_dispatch_recovery_clears_after_answer():
    """回收消费即清:answer 后 subagent_results 为空,不会泄漏到下一轮。"""
    from langgraph.checkpoint.memory import InMemorySaver

    s1 = ResultSummary(agent="research", task_id="s1", task="查X",
                       status="success", conclusion="A")
    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[Task(agent="research", task="查X", reason="r")]),
        Route(next="answer"),
        AIMessage("第一轮汇总。"),
    ])
    fake_tasks = _FakeTasks()
    graph = build_graph(llm=fake, checkpointer=InMemorySaver(), tasks=fake_tasks)
    config = {"configurable": {"thread_id": "t-asy-2"}, "recursion_limit": 40}

    list(graph.stream({"messages": [("user", "第一问")]}, config, stream_mode="updates"))
    fake_tasks.results = [("t-asy-2", s1)]  # 后台任务完成,下一轮回收
    list(graph.stream({"messages": [("user", "结果呢")]}, config, stream_mode="updates"))
    assert graph.get_state(config).values["subagent_results"] == []
    # 后台结果已被 drain 消费,第二轮 supervisor 不再注入
    assert fake_tasks.results == []


def test_dispatch_results_are_thread_scoped():
    """线程归属:后台结果只被派发它的会话回收,别的会话轮次不消费(多线程不串)。"""
    from langgraph.checkpoint.memory import InMemorySaver

    s1 = ResultSummary(agent="research", task_id="s1", task="查X",
                       status="success", conclusion="A 线程的结论")
    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[Task(agent="research", task="查X", reason="r")]),
        Route(next="answer"),
        AIMessage("B 线程应答。"),
        Route(next="answer"),
        AIMessage("A 线程汇总。"),
    ])
    fake_tasks = _FakeTasks()
    graph = build_graph(llm=fake, checkpointer=InMemorySaver(), tasks=fake_tasks)
    cfg_a = {"recursion_limit": 40, "configurable": {"thread_id": "t-scope-a"}}
    cfg_b = {"recursion_limit": 40, "configurable": {"thread_id": "t-scope-b"}}

    list(graph.stream({"messages": [("user", "调研X")]}, cfg_a, stream_mode="updates"))
    assert fake_tasks.thread_ids == ["t-scope-a"]  # submit 带线程归属

    fake_tasks.results = [("t-scope-a", s1)]  # 后台任务完成
    # B 线程轮次:不消费 A 的结果,answer 也拿不到
    list(graph.stream({"messages": [("user", "在吗")]}, cfg_b, stream_mode="updates"))
    assert [t for t, _ in fake_tasks.results] == ["t-scope-a"]
    assert graph.get_state(cfg_b).values["subagent_results"] == []

    # 回到 A 线程:回收注入 → answer 汇总
    list(graph.stream({"messages": [("user", "结果呢")]}, cfg_a, stream_mode="updates"))
    assert fake_tasks.results == []


# ---------- T5 answer 消费即清 ----------

def test_render_results_format():
    r = ResultSummary(
        agent="retriever",
        task_id="s1",
        task="查X",
        status="success",
        conclusion="找到了",
        key_points=["A", "B"],
        needs_clarification=["年份"],
    )
    text = _render_results([r])
    assert "agent=retriever" in text
    assert "任务:查X" in text
    assert "结果:找到了 A B" in text
    assert "澄清:年份" in text


def test_render_results_keeps_all_and_order():
    """多条结果全部渲染且保持顺序(防止 append 误移出循环的回归)。"""
    r1 = ResultSummary(
        agent="retriever", task_id="s1", task="查X", status="success", conclusion="A"
    )
    r2 = ResultSummary(
        agent="research", task_id="s2", task="调研Y", status="success", conclusion="B"
    )
    text = _render_results([r1, r2])
    assert "查X" in text and "调研Y" in text
    assert text.index("查X") < text.index("调研Y")


def test_render_results_evidence_renders_hits_and_sources():
    """answer 侧:retriever 的 hits 正文与 sources 必须进提示词(只给 100 字结论会丢正文)。"""
    r = ResultSummary(
        agent="retriever",
        task_id="s1",
        task="查 LangGraph",
        status="success",
        conclusion="找到两份文档",
        data={
            "hits": [
                {
                    "doc_id": "d1",
                    "filename": "04-LangGraph中断与工具与部署.md",
                    "seq": 3,
                    "content": "动态中断用 interrupt() 实现",
                    "score": 0.9,
                },
                {
                    "doc_id": "d2",
                    "filename": "05-LangGraph高级特性.md",
                    "seq": 7,
                    "content": "stream_mode 有七种",
                    "score": 0.8,
                },
            ]
        },
        sources=["d1", "d2"],
    )
    text = _render_results([r], with_evidence=True)
    assert "依据:" in text and "来源:" in text
    assert "《04-LangGraph中断与工具与部署.md》#3:动态中断用 interrupt() 实现" in text
    assert "《05-LangGraph高级特性.md》#7:stream_mode 有七种" in text
    assert "来源:d1 d2" in text


def test_render_results_default_stays_decision_only():
    """supervisor 的回收提示保持精简:不带依据正文(路由只看决策字段)。"""
    r = ResultSummary(
        agent="retriever",
        task_id="s1",
        task="查X",
        status="success",
        conclusion="找到了",
        data={"hits": [{"filename": "f.md", "content": "正文片段"}]},
        sources=["d1"],
    )
    text = _render_results([r])
    assert "依据:" not in text
    assert "正文片段" not in text
    assert "来源:" not in text


def test_render_results_evidence_budget():
    """依据有预算:条数 ≤4、单条 ≤250 字、整块 ≤1200 字,防多任务叠加撑爆 answer 上下文。"""
    hits = [
        {"doc_id": f"d{i}", "filename": f"{i}.md", "seq": i, "content": "长" * 500}
        for i in range(8)
    ]
    r = ResultSummary(
        agent="retriever",
        task_id="s1",
        task="查X",
        status="success",
        conclusion="c",
        data={"hits": hits},
    )
    text = _render_results([r], with_evidence=True)
    assert text.count("    - ") == EVIDENCE_ITEMS_MAX == 4
    body = text.split("依据:\n", 1)[1]
    lines = body.splitlines()
    assert len(lines) == EVIDENCE_ITEMS_MAX
    assert all(len(ln.split(":", 1)[1]) == EVIDENCE_ITEM_CHARS for ln in lines)
    assert len(body) <= EVIDENCE_TOTAL_CHARS


def test_render_results_evidence_research_shape_and_warnings():
    """research 形状(title/url/snippet)可渲染;warnings(执行侧效应)必须出现。"""
    r = ResultSummary(
        agent="research",
        task_id="s2",
        task="查天气",
        status="success",
        conclusion="小雨",
        sources=["https://weather.com.cn"],
        warnings=["联网检索:1 条来源"],
        data={
            "results": [
                {
                    "title": "中国天气网",
                    "url": "https://weather.com.cn",
                    "snippet": "18 日南阳小雨 17~25℃",
                }
            ]
        },
    )
    text = _render_results([r], with_evidence=True)
    assert "中国天气网(https://weather.com.cn):18 日南阳小雨" in text
    assert "执行提示:联网检索:1 条来源" in text


def test_full_dispatch_submits_two_jobs():
    """多任务异步派发:一次 dispatch 提交多个后台任务(submit 收到全部 jobs)。"""
    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[
            Task(agent="retriever", task="查X", reason="r1"),
            Task(agent="research", task="调研Y", reason="r2"),
        ]),
    ])
    fake_tasks = _FakeTasks()
    graph = build_graph(llm=fake, tasks=fake_tasks)
    list(graph.stream(
        {"messages": [("user", "问两件事")]},
        {"recursion_limit": 25, "configurable": {"thread_id": "t6-acc"}},
        stream_mode="updates",
    ))
    assert len(fake_tasks.submitted) == 2
    assert {a for a, _ in fake_tasks.submitted} == {"retriever", "research"}


# ---------- T6 全图回归基线(后续模块的回归保险) ----------

class FakeInfiniteDispatchLLM:
    """fake 持续返回 dispatch:验证异步派发下不再路由乒乓——每轮 dispatch 立即 END。"""

    def with_structured_output(self, schema, **kwargs):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return Route(
            next="dispatch", tasks=[Task(agent="retriever", task="循环任务", reason="r")]
        )


def test_full_dispatch_submits_three_jobs():
    """黄金剧本式异步派发:2×research + 1×retriever 一次提交全部 jobs。"""
    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[
            Task(agent="research", task="调研A", reason="r1"),
            Task(agent="research", task="调研B", reason="r2"),
            Task(agent="retriever", task="查X", reason="r3"),
        ]),
    ])
    fake_tasks = _FakeTasks()
    graph = build_graph(llm=fake, tasks=fake_tasks)
    list(graph.stream(
        {"messages": [("user", "问三件事")]},
        {"recursion_limit": 40, "configurable": {"thread_id": "t6-3"}},
        stream_mode="updates",
    ))
    assert len(fake_tasks.submitted) == 3
    assert [a for a, _ in fake_tasks.submitted] == ["research", "research", "retriever"]


def test_full_router_fallback_to_answer():
    """supervisor 路由解析失败(返回 None)时回退 answer,图不挂死。"""
    fake = FakeScriptedLLM([None, AIMessage("兜底回答。")])
    graph = build_graph(llm=fake)
    names = [k for _ns, ev in _trace(graph) for k in ev]
    assert names == ["supervisor", "answer"]


def test_run_turn_recursion_limit_fallback():
    """run_turn 兜底:图执行超限(GraphRecursionError)返回兜底消息,不炸给调用方。"""
    from langgraph.errors import GraphRecursionError

    class _BoomGraph:
        def stream(self, *a, **kw):
            raise GraphRecursionError("step limit exceeded")

    final = run_turn(
        _BoomGraph(), {"recursion_limit": 25, "configurable": {"thread_id": "t6-rec"}}, "你好"
    )
    assert isinstance(final, AIMessage)
    assert "循环" in final.content


def test_run_turn_dispatch_returns_confirmation():
    """异步派发:持续 dispatch 不再乒乓,每轮立即返回"已派发"确认消息。"""
    from langgraph.checkpoint.memory import InMemorySaver

    graph = build_graph(llm=FakeInfiniteDispatchLLM(), checkpointer=InMemorySaver())
    final = run_turn(
        graph, {"recursion_limit": 25, "configurable": {"thread_id": "t6-ping"}}, "你好"
    )
    assert isinstance(final, AIMessage)
    assert "已派发" in final.content


# ---------- T7 run_turn 路由回调 ----------

def test_run_turn_on_route_reports_dispatch():
    """run_turn 的 on_route 回调:异步派发轮报告一次 dispatch 路由(轨迹打印的数据源)。"""
    from langgraph.checkpoint.memory import InMemorySaver

    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[Task(agent="retriever", task="查X", reason="r")]),
    ])
    graph = build_graph(llm=fake, checkpointer=InMemorySaver())
    seen = []
    final = run_turn(
        graph,
        {"recursion_limit": 25, "configurable": {"thread_id": "t7"}},
        "问",
        on_route=seen.append,
    )
    assert len(seen) == 1
    first = Route(**seen[0])
    assert first.next == "dispatch" and first.tasks[0].agent == "retriever"
    assert "已派发" in final.content


# ---------- 回归:空 dispatch 与超长任务(审查修复) ----------

def test_empty_dispatch_falls_back_to_answer():
    """tasks 为空的 dispatch 不能空转结束(否则 run_turn 把用户消息当回复),应退化走 answer。"""
    from langgraph.checkpoint.memory import InMemorySaver

    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[]),
        AIMessage("没有可派发的任务,我直接回答。"),
    ])
    graph = build_graph(llm=fake, checkpointer=InMemorySaver())
    final = run_turn(
        graph,
        {"recursion_limit": 25, "configurable": {"thread_id": "t8-empty"}},
        "帮我查一下X",
    )
    assert isinstance(final, AIMessage)  # 不能是 HumanMessage(用户自己的话回显)
    assert "直接回答" in final.content


def test_long_task_does_not_crash_subgraph():
    """超长任务:异步提交不崩主图(子图边界 ValidationError 由后台兜底为 failed)。"""
    from langgraph.checkpoint.memory import InMemorySaver

    long_task = "查知识库" + "很长的内容" * 30
    fake = FakeScriptedLLM([
        Route(next="dispatch", tasks=[Task(agent="retriever", task=long_task, reason="r")]),
    ])
    graph = build_graph(llm=fake, checkpointer=InMemorySaver())
    final = run_turn(
        graph,
        {"recursion_limit": 25, "configurable": {"thread_id": "t8-long"}},
        "问",
    )
    assert isinstance(final, AIMessage)
    assert "已派发" in final.content


# ---------- 回归:结构化路由必须显式 method='function_calling'(实测坑) ----------

def test_route_node_uses_function_calling_structured_output():
    """回归:with_structured_output 必须显式 method='function_calling'。

    langchain-openai 1.x 默认走 json_schema response_format,DeepSeek 端点不支持
    (400 invalid_request_error),会被静默兜底成 answer——表现为 SSE 无 route 帧、
    dispatch/ask/memory 永不上线。本测试锁死修复:method 必须显式传入。
    """

    class _Recorder:
        def __init__(self):
            self.method = None

        def with_structured_output(self, schema, method=None):
            self.method = method
            return self

        def invoke(self, messages):
            return Route(next="answer")

    llm = _Recorder()
    cmd = route_node(_state(), llm)
    assert llm.method == "function_calling"
    assert (cmd.update or {}).get("last_route", {}).get("next") == "answer"
