"""模块 06 T4 单测:ask 问询 interrupt 挂起/恢复往返(fake model,不依赖真实 LLM/DB)。

流程:supervisor 路由 ask(last_route.question)-> ask 节点 interrupt 挂起 ->
外部以 Command(resume=text) 恢复 -> ask 节点把答案作为 user message 追加 ->
ask -> supervisor 继续路由(ADR-0008 单一挂起点,任意时刻至多一个挂起)。
"""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.build import build_graph
from agent.contracts import Route
from agent.service import run_turn


class FakeAskLLM:
    """fake ChatModel:路由 ask(带问题)-> 路由 answer -> answer 节点返回最终回答。"""

    def __init__(self):
        self._routes = iter([
            Route(next="ask", question="请告诉我城市?"),
            Route(next="answer"),
        ])
        self.calls = []

    def with_structured_output(self, schema, **kwargs):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        try:
            return next(self._routes)
        except StopIteration:
            return AIMessage(content="好的,已按北京查询。")


def test_ask_interrupt_then_resume_roundtrip():
    """完整往返:第一轮触发 ask 挂起,第二轮 resume 恢复,答案进消息流并继续到 answer。"""
    graph = build_graph(FakeAskLLM(), InMemorySaver())
    config = {"recursion_limit": 25, "configurable": {"thread_id": "t4-ask"}}

    # 第一轮:触发 ask 挂起
    list(graph.stream({"messages": [("user", "帮我查天气")]}, config, stream_mode="updates"))
    st = graph.get_state(config)
    assert st.next  # 图挂起,有未完成节点
    assert st.interrupts and st.interrupts[0].value["question"] == "请告诉我城市?"

    # 第二轮:resume 恢复,答案作为 user message 进消息流,继续到 answer
    list(graph.stream(Command(resume="北京"), config, stream_mode="updates"))
    final = graph.get_state(config).values["messages"][-1]
    assert final.content == "好的,已按北京查询。"
    # 用户回答进入了主图消息历史(ask 节点追加)
    texts = [m.content for m in graph.get_state(config).values["messages"]]
    assert any("[用户回答]:北京" in t for t in texts)


def test_run_turn_interrupt_returns_none_and_callback():
    """run_turn 遇 interrupt:on_interrupt 回调拿到问题,返回 None(REPL 据此进入挂起态)。"""
    graph = build_graph(FakeAskLLM(), InMemorySaver())
    config = {"recursion_limit": 25, "configurable": {"thread_id": "t4-rt"}}
    seen = []
    result = run_turn(graph, config, "帮我查天气", on_interrupt=lambda intrs: seen.append(intrs))
    assert result is None  # 挂起:无最终消息
    assert seen and seen[0][0].value["question"] == "请告诉我城市?"

    # resume 恢复:最终返回 AIMessage
    final = run_turn(graph, config, resume="北京")
    assert isinstance(final, AIMessage)
    assert "已按北京查询" in final.content


def test_run_turn_without_interrupt_still_returns_message():
    """不触发 interrupt 的普通轮:run_turn 仍正常返回 AIMessage(resume=None 兼容)。"""
    fake = FakeAskLLM()
    # 覆盖:不走 ask,直接 answer
    fake._routes = iter([Route(next="answer")])
    graph = build_graph(fake, InMemorySaver())
    config = {"recursion_limit": 25, "configurable": {"thread_id": "t4-plain"}}
    final = run_turn(graph, config, "你好")
    assert isinstance(final, AIMessage)
