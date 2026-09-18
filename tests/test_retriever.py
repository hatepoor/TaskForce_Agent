"""模块 R 单测:retriever ReAct 子图(fake model 脚本化 tool_calls + FakeStore)。"""

import json

from langchain_core.messages import AIMessage, ToolMessage

from agent.contracts import SubgraphContract
from agent.subagents.react import extract_answer
from agent.subagents.retriever import (
    _collect_hits,
    build_retriever_graph,
)


class FakeStore:
    """假 RAGStore:按查询词返回固定命中;raise_on_search=True 时模拟检索故障。"""

    def __init__(self, per_query=None, raise_on_search=False):
        self._per_query = per_query or {}
        self._raise = raise_on_search

    def search(self, query, top_k=5):
        if self._raise:
            raise RuntimeError("数据库连接失败")
        return self._per_query.get(query, [])[:top_k]


def _call(query, cid="c1"):
    """构造与真实模型一致的 tool_call dict(id 与 ToolMessage.tool_call_id 配对)。"""
    return {"name": "kb_search", "args": {"query": query}, "id": cid, "type": "tool_call"}


def _contract(task="查知识库里的昆玉河"):
    return SubgraphContract(task=task, user_utterance="昆玉河沿岸有什么公园?").model_dump()


HIT_A = {"doc_id": "d1", "filename": "a.md", "seq": 0,
         "content": "昆玉河沿岸有玉渊潭公园。", "score": 0.1}
HIT_B = {"doc_id": "d2", "filename": "b.md", "seq": 3,
         "content": "紫竹院公园也在沿岸。", "score": 0.2}


class FakeReActLLM:
    """bind_tools 后按脚本返回 AIMessage;脚本耗尽自动返回无工具调用的收尾消息。"""

    def __init__(self, rounds):
        self._rounds = list(rounds)
        self._i = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if self._i < len(self._rounds):
            msg = self._rounds[self._i]
            self._i += 1
            return msg
        return AIMessage("知识库检索完成")


class FakeAlwaysToolLLM:
    """永远想再调工具:验证轮数上限掐断为 partial。"""

    def __init__(self):
        self._n = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self._n += 1
        return AIMessage(content="", tool_calls=[_call("q", cid=f"c{self._n}")])


def _graph(llm, store):
    import tools.rag.kb_search as kb_mod

    kb_mod._default_store = lambda: store  # 直接替换,避免 lru_cache 残留
    return build_retriever_graph(llm)


def test_success_flow_parses_json_answer():
    """有命中 + 模型自发摘要 JSON(带围栏):finalize 零额外 LLM 调用,解析出结论要点。"""
    store = FakeStore({"昆玉河": [HIT_A]})
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("昆玉河")]),
        AIMessage('```json\n{"conclusion": "沿岸有玉渊潭公园", "key_points": ["玉渊潭"]}\n```'),
    ])
    final = _graph(llm, store).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.agent == "retriever"
    assert summary.status == "success"
    assert summary.conclusion == "沿岸有玉渊潭公园"
    assert summary.key_points == ["玉渊潭"]
    assert summary.task == "查知识库里的昆玉河"
    assert summary.data["hits"][0]["doc_id"] == "d1"
    assert summary.sources == ["d1"]


def test_success_prose_fallback():
    """模型最终输出普通文本(非 JSON):结论截断原文,要点为空,状态仍 success。"""
    store = FakeStore({"昆玉河": [HIT_A]})
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("昆玉河")]),
        AIMessage("知识库记载:昆玉河沿岸有玉渊潭公园。"),
    ])
    final = _graph(llm, store).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "success"
    assert summary.conclusion == "知识库记载:昆玉河沿岸有玉渊潭公园。"
    assert summary.key_points == []


def test_two_calls_cross_dedup():
    """跨两次工具调用命中同一 (doc_id, seq):finalize 重建 hits 时去重。"""
    store = FakeStore({"q1": [HIT_A], "q2": [HIT_A]})
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("q1", "c1")]),
        AIMessage(content="", tool_calls=[_call("q2", "c2")]),
    ])
    final = _graph(llm, store).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert len(summary.data["hits"]) == 1


def test_no_hits_need_clarification():
    """无命中:直接诚实返回 need_clarification,不依赖 LLM。"""
    store = FakeStore({})
    llm = FakeReActLLM(rounds=[AIMessage(content="", tool_calls=[_call("q")])])
    final = _graph(llm, store).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "need_clarification"
    assert summary.needs_clarification
    assert summary.data == {}


def test_iteration_cap_partial():
    """模型无限要求调工具:MAX_ITERATIONS 轮后被条件边掐断,partial + warnings。"""
    llm = FakeAlwaysToolLLM()
    final = _graph(llm, FakeStore({})).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "partial"
    assert summary.warnings
    assert "上限" in summary.warnings[0]


def test_tool_error_does_not_crash():
    """检索故障:错误兜底为 ToolMessage 文本交回模型,收尾时无命中 → 诚实 need_clarification。"""
    store = FakeStore(raise_on_search=True)
    llm = FakeReActLLM(rounds=[AIMessage(content="", tool_calls=[_call("q")])])
    final = _graph(llm, store).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "need_clarification"


def test_node_trace():
    """子图节点轨迹:agent → tools → agent → finalize。"""
    store = FakeStore({"q": [HIT_A]})
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[_call("q")]),
        AIMessage("命中了玉渊潭公园。"),
    ])
    names = [
        next(iter(ev))
        for ev in _graph(llm, store).stream({"contract": _contract()}, stream_mode="updates")
    ]
    assert names == ["agent", "tools", "agent", "finalize"]


def test_collect_hits_dedup_and_skip_non_json():
    """_collect_hits:ToolMessage JSON 解析、跨调用去重、非 JSON 文本跳过。"""
    msgs = [
        ToolMessage(content=json.dumps([HIT_A, HIT_B], ensure_ascii=False), tool_call_id="c1"),
        ToolMessage(content="工具执行出错:boom", tool_call_id="c2"),
        ToolMessage(content=json.dumps([HIT_A], ensure_ascii=False), tool_call_id="c3"),
    ]
    hits = _collect_hits(msgs)
    assert [h["doc_id"] for h in hits] == ["d1", "d2"]


def test_extract_answer_variants():
    """_extract_answer:围栏 JSON / 裸 JSON / 普通文本 / 空文本四分支。"""
    assert extract_answer('```json\n{"conclusion": "A", "key_points": ["k"]}\n```') == ("A", ["k"])
    assert extract_answer('{"conclusion": "B"}')[0] == "B"
    assert extract_answer("普通散文回答。") == ("普通散文回答。", [])
    assert extract_answer("") == ("(无文本输出)", [])
    # 超长结论截断到 100
    long = extract_answer("长" * 300)[0]
    assert len(long) == 100
