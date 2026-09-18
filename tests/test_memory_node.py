"""模块 06 T3/T5 单测:memory 节点显式写入与确认写入(fake model,不依赖真实 DB/LLM)。

memory 节点用普通 invoke + JSON 解析(非 with_structured_output,防流式 JSON 泄漏);
fake LLM 返回带 JSON content 的 AIMessage 模拟模型响应。
"""

import json

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.build import build_graph
from agent.contracts import Route
from agent.memory import _last_user_text, memory_node


class FakeStore:
    """fake PostgresStore:只记录写入。"""

    def __init__(self):
        self.written = []

    def put(self, namespace, key, value):
        self.written.append((namespace, key, value))


class FakeProposalLLM:
    """fake ChatModel:普通 invoke 返回 JSON 字符串(模拟 memory 节点调用)。"""

    def __init__(self, content: str, source: str = "explicit"):
        self._ai = AIMessage(
            content=json.dumps({"content": content, "source": source}, ensure_ascii=False),
            usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        )
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return self._ai


def _state(user_text: str):
    return {"messages": [HumanMessage(content=user_text)], "subagent_results": []}


def test_memory_node_explicit_write(monkeypatch):
    """显式写入:压缩后的原子事实落库(memory, default),回确认消息且带 usage。"""
    fake = FakeStore()
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    llm = FakeProposalLLM("用户偏好中文回复", "explicit")
    result = memory_node(_state("记住我偏好中文回复"), llm)
    assert result["messages"][0].content == "已记住:用户偏好中文回复"
    assert result["messages"][0].usage_metadata["input_tokens"] == 5
    assert len(fake.written) == 1
    ns, key, value = fake.written[0]
    assert ns == ("memory", "default")
    assert value["content"] == "用户偏好中文回复"
    assert value["source"] == "explicit"


def test_memory_node_empty_content_skips_write(monkeypatch):
    """提炼不出有效事实(content 空):跳过写入并如实告知(显式分支)。"""
    fake = FakeStore()
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    llm = FakeProposalLLM("", "explicit")
    result = memory_node(_state("帮我记住一下"), llm)
    assert "未写入" in result["messages"][0].content
    assert fake.written == []


def test_memory_node_last_user_text_skips_internal():
    """写入输入取最后一条真实用户消息,跳过"子智能体结果已回收"内部消息。"""
    state = {
        "messages": [
            HumanMessage(content="真实问题"),
            HumanMessage(content="子智能体结果已回收:..."),
        ],
        "subagent_results": [],
    }
    assert _last_user_text(state) == "真实问题"


# ---------- T5:确认写入(自主提案 interrupt,图级往返) ----------


class FakeMemoryFlowLLM:
    """fake:supervisor 路由 memory;memory 节点普通 invoke 返回 JSON。"""

    def __init__(self, content: str):
        self._json = json.dumps({"content": content, "source": "explicit"}, ensure_ascii=False)
        self._routed = False

    def with_structured_output(self, schema, **kwargs):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if not self._routed:
            self._routed = True
            return Route(next="memory")
        return AIMessage(
            content=self._json,
            usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        )


def _mem_graph(llm, tid):
    g = build_graph(llm, InMemorySaver())
    return g, {"recursion_limit": 25, "configurable": {"thread_id": tid}}


def _ask(graph, config, text):
    """发一轮用户消息(updates 流收集完毕),不关心事件明细。"""
    list(graph.stream({"messages": [("user", text)]}, config, stream_mode="updates"))


def test_memory_proposal_interrupt_then_confirm_yes(monkeypatch):
    """自主提案:interrupt 挂起;resume=True 落库且 source=confirmed。"""
    fake = FakeStore()
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    llm = FakeMemoryFlowLLM("用户每天晨跑五公里")
    graph, config = _mem_graph(llm, "t5-yes")

    _ask(graph, config, "我每天六点起床跑步")
    st = graph.get_state(config)
    assert st.interrupts and st.interrupts[0].value["proposal"] == "用户每天晨跑五公里"
    assert len(st.interrupts) == 1  # 单一挂起点(ADR-0008):任意时刻至多一个挂起

    list(graph.stream(Command(resume=True), config, stream_mode="updates"))
    assert len(fake.written) == 1
    _, _, value = fake.written[0]
    assert value["content"] == "用户每天晨跑五公里"
    assert value["source"] == "confirmed"
    assert "已记住" in graph.get_state(config).values["messages"][-1].content


def test_memory_proposal_confirm_no_skips_write(monkeypatch):
    """/confirm no:resume=False,不落库,回"没有记入"。"""
    fake = FakeStore()
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    llm = FakeMemoryFlowLLM("用户每天晨跑五公里")
    graph, config = _mem_graph(llm, "t5-no")

    _ask(graph, config, "我每天六点起床跑步")
    list(graph.stream(Command(resume=False), config, stream_mode="updates"))
    assert fake.written == []
    assert "没有记入" in graph.get_state(config).values["messages"][-1].content


def test_memory_explicit_write_no_interrupt(monkeypatch):
    """显式写入(用户说"记住"):直接落库且不产生挂起(无 interrupt)。"""
    fake = FakeStore()
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    llm = FakeMemoryFlowLLM("用户偏好中文回复")
    graph, config = _mem_graph(llm, "t5-explicit")

    _ask(graph, config, "记住我偏好中文回复")
    assert len(fake.written) == 1
    _, _, value = fake.written[0]
    assert value["source"] == "explicit"
    assert not graph.get_state(config).interrupts  # 显式路径不挂起
