"""模块 10 T2 单测:research ReAct 子图(fake model 脚本化 tool_calls + mock httpx)。"""

import json
from types import SimpleNamespace

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import tools.websearch.search as search
from agent.contracts import SubgraphContract
from agent.subagents.react import WRAPUP_HINT
from agent.subagents.research import (
    _collect_results,
    _sources_of,
    build_research_graph,
)


def _call(query, cid="c1"):
    return {"name": "web_search", "args": {"query": query}, "id": cid, "type": "tool_call"}


def _contract(task="调研 LangGraph 与 CrewAI"):
    return SubgraphContract(task=task, user_utterance="对比 LangGraph 与 CrewAI?").model_dump()


RESULT_A = {"title": "LangGraph 文档", "url": "https://langchain-ai.github.io/langgraph/",
            "snippet": "LangGraph 是低层编排框架。"}
RESULT_B = {"title": "CrewAI", "url": "https://crewai.com",
            "snippet": "CrewAI 是角色扮演式多智能体框架。"}


def _mock_search(monkeypatch, results=None, raise_network=False):
    monkeypatch.setattr(
        search, "get_settings", lambda: SimpleNamespace(anysearch_api_key="k1")
    )

    def fake_post(url, **kw):
        if raise_network:
            raise httpx.ConnectError("refused")
        return httpx.Response(
            status_code=200,
            json={"code": 0, "data": {"results": results or []}},
        )

    monkeypatch.setattr(search.httpx, "post", fake_post)


class FakeReActLLM:
    """bind_tools 后按脚本返回 AIMessage;脚本耗尽自动返回无工具调用的收尾消息。"""

    def __init__(self, rounds):
        self._rounds = list(rounds)
        self._i = 0
        self.inputs: list[list] = []  # 记录每次 invoke 的消息列表(闸门断言用)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.inputs.append(list(messages))
        if self._i < len(self._rounds):
            msg = self._rounds[self._i]
            self._i += 1
            return msg
        return AIMessage("调研完成")


class FakeAlwaysToolLLM:
    """永远想再调工具:验证轮数上限掐断为 partial。"""

    def __init__(self):
        self._n = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self._n += 1
        return AIMessage(content="", tool_calls=[_call("q", cid=f"c{self._n}")])


def _graph(llm):
    return build_research_graph(llm)


def test_success_flow_parses_json_answer(monkeypatch):
    """一轮搜索 + 模型自发摘要 JSON:success,来源 URL 从 ToolMessage 确定性重建。"""
    _mock_search(monkeypatch, results=[RESULT_A, RESULT_B])
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("LangGraph")]),
        AIMessage('```json\n{"conclusion": "LangGraph 偏底层编排", "key_points": ["图状态"]}\n```'),
    ])
    final = _graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.agent == "research"
    assert summary.status == "success"
    assert summary.conclusion == "LangGraph 偏底层编排"
    assert summary.key_points == ["图状态"]
    assert summary.sources == ["https://langchain-ai.github.io/langgraph/", "https://crewai.com"]
    # 检索正文随 data 回传:answer 汇总时据此作答(只给 100 字结论会丢正文,troubleshooting/03 §14)
    assert [r["title"] for r in summary.data["results"]] == ["LangGraph 文档", "CrewAI"]
    assert "低层编排框架" in summary.data["results"][0]["snippet"]


def test_two_rounds_search_research(monkeypatch):
    """搜-评-再搜:两次搜索再收尾,来源跨调用去重。"""
    _mock_search(monkeypatch, results=[RESULT_A])
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("LangGraph 优点")]),
        AIMessage(content="", tool_calls=[_call("LangGraph 缺点")]),
        AIMessage("两次检索后认为 LangGraph 适合复杂状态流。"),
    ])
    final = _graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "success"
    assert summary.sources == ["https://langchain-ai.github.io/langgraph/"]  # 去重


def test_no_sources_need_clarification(monkeypatch):
    """搜索结果为空(查不到):诚实返回 need_clarification,不依赖 LLM。"""
    _mock_search(monkeypatch, results=[])
    llm = FakeReActLLM(rounds=[AIMessage(content="", tool_calls=[_call("q")])])
    final = _graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "need_clarification"
    assert summary.needs_clarification
    assert summary.sources == []


def test_tool_network_error_does_not_crash(monkeypatch):
    """搜索网络故障:web_search 返回 "[]",收尾时无来源 → 诚实 need_clarification。"""
    _mock_search(monkeypatch, raise_network=True)
    llm = FakeReActLLM(rounds=[AIMessage(content="", tool_calls=[_call("q")])])
    final = _graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "need_clarification"


def test_iteration_cap_partial(monkeypatch):
    """模型无限要求调工具:MAX_ITERATIONS 轮后被条件边掐断,partial + warnings。"""
    _mock_search(monkeypatch, results=[RESULT_A])
    llm = FakeAlwaysToolLLM()
    final = _graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "partial"
    assert summary.warnings
    assert "上限" in summary.warnings[0]


def test_node_trace(monkeypatch):
    """子图节点轨迹:agent → tools → agent → finalize。"""
    _mock_search(monkeypatch, results=[RESULT_A])
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("q")]),
        AIMessage("检索到了 LangGraph 资料。"),
    ])
    names = [
        next(iter(ev))
        for ev in _graph(llm).stream({"contract": _contract()}, stream_mode="updates")
    ]
    assert names == ["agent", "tools", "agent", "finalize"]


def test_context_budget_injects_wrapup(monkeypatch):
    """上下文膨胀闸门(T3):react_msgs 超字符预算时注入一次收尾提示,不重复注入。"""
    _mock_search(monkeypatch, results=[RESULT_A])
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("q")]),
        AIMessage("已有足够信息,收尾。"),
    ])
    big = SystemMessage(content="背景。" * 7000)  # 21k 字符,越过 16k 预算
    _graph(llm).invoke({
        "contract": _contract(),
        "react_msgs": [big, HumanMessage(content="任务:调研 X")],
    })
    counts = [
        sum(1 for m in msgs if getattr(m, "content", "") == WRAPUP_HINT)
        for msgs in llm.inputs
    ]
    assert counts[0] == 1  # 第一帧越过预算注入
    assert all(c == 1 for c in counts)  # 提示持久化在历史里,后续帧不重复追加


def test_collect_results_dedup_and_skip_non_json():
    """_collect_results:JSON 解析、跨调用去重、非 JSON 文本跳过、无 url 条目按 title 保留。"""
    msgs = [
        ToolMessage(
            content=json.dumps([RESULT_A, RESULT_B, {"title": "no url", "snippet": "x"}],
                               ensure_ascii=False),
            tool_call_id="c1",
        ),
        ToolMessage(content="工具执行出错:boom", tool_call_id="c2"),
        ToolMessage(content=json.dumps([RESULT_A], ensure_ascii=False), tool_call_id="c3"),
    ]
    results = _collect_results(msgs)
    assert [r["url"] for r in results] == [
        "https://langchain-ai.github.io/langgraph/",
        "https://crewai.com",
        "",
    ]
    assert results[2]["title"] == "no url"  # 无 url 但有 title:保留(靠 title 去重)
    assert _sources_of(results) == [  # 来源只取有 URL 的
        "https://langchain-ai.github.io/langgraph/",
        "https://crewai.com",
    ]
