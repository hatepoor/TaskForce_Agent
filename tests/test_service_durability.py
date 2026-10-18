"""run_turn 写入策略与 onDone 回调单测(不依赖真实 LLM/DB)。"""

from types import SimpleNamespace

from langchain_core.messages import AIMessage

from agent.service import run_turn


class _FakeGraph:
    """最小假图:只实现 run_turn 用到的 stream / get_state。"""

    def __init__(self, events=None):
        self.events = events or []
        self.kwargs = {}
        self.stateCalls = 0

    def stream(self, inputs, config=None, **kwargs):
        self.kwargs = dict(kwargs)
        yield from self.events

    def get_state(self, config):
        self.stateCalls += 1
        return SimpleNamespace(values={"messages": [AIMessage(content="ok")]})


def _config() -> dict:
    return {"configurable": {"thread_id": "sess-test"}}


def test_run_turn_uses_exit_durability():
    """普通轮必须显式传 exit:默认 async 只异步写,checkpoint 写入次数不变。"""
    graph = _FakeGraph()
    final = run_turn(graph, _config(), "你好")

    assert isinstance(final, AIMessage) and final.content == "ok"
    assert graph.kwargs["durability"] == "exit"


def test_run_turn_calls_on_done_after_normal_turn():
    """正常结束:onDone 在返回前调用一次,供 sessions 元数据落库。"""
    graph = _FakeGraph()
    calls = []

    final = run_turn(graph, _config(), "你好", onDone=lambda: calls.append("done"))

    assert isinstance(final, AIMessage)
    assert calls == ["done"]


def test_run_turn_calls_on_done_on_interrupt():
    """interrupt 挂起:run_turn 返回 None,但 onDone 仍必须调用(会话仍活跃)。"""
    interrupt = SimpleNamespace(value={"kind": "ask", "text": "要哪一年?"})
    graph = _FakeGraph([("updates", {"__interrupt__": [interrupt]})])
    done = []
    seen = []

    final = run_turn(
        graph,
        _config(),
        "查数据",
        on_interrupt=lambda updates: seen.append(updates),
        onDone=lambda: done.append("done"),
    )

    assert final is None
    assert seen and seen[0][0] is interrupt
    assert done == ["done"]


def test_run_turn_on_done_failure_does_not_break_turn():
    """元数据写失败是派生索引故障:只告警,不影响本轮返回。"""
    graph = _FakeGraph()

    def boom() -> None:
        raise RuntimeError("db down")

    final = run_turn(graph, _config(), "你好", onDone=boom)
    assert isinstance(final, AIMessage) and final.content == "ok"
