"""模块 06 T2 重构(ADR-0011)单测:agents.md 固定 system + 记忆工具(memory-as-tool)。

原"每轮记忆注入 system"机制废除,改为:
- agents.md 仍进固定 system(supervisor/answer 两侧),字节级稳定;
- 长期记忆封装为 memory_search / store_memory 工具,由 answer 侧按需调用,
  结果以 ToolMessage 进消息流;测试用 monkeypatch _default_store 注入 FakeStore。
"""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.answer import answer_node
from agent.contracts import Route
from agent.memory_ctx import load_agents_md, memory_search, store_memory
from agent.supervisor import route_node


class FakeLLM:
    """fake ChatModel:记录 invoke 消息,返回预设 Route 或 AIMessage。"""

    def __init__(self, route=None, ai_content=None):
        self._route = route
        self._ai = AIMessage(content=ai_content) if ai_content is not None else None
        self.calls = []

    def with_structured_output(self, schema, **kwargs):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return self._route if self._route is not None else self._ai


class FakeStore:
    """fake PostgresStore:预设 hits + 记录写入。"""

    def __init__(self, hits=None):
        self._hits = hits or []
        self.last_namespace = None
        self.last_query = None
        self.written = []

    def search(self, namespace, query=None, limit=10):
        self.last_namespace = namespace
        self.last_query = query
        return self._hits

    def put(self, namespace, key, value):
        self.written.append((namespace, key, value))


class FakeMemoryLLM:
    """answer 记忆循环 fake:首帧返回 memory_search 工具调用,第二轮返回最终回答。"""

    def __init__(self):
        self.calls = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "memory_search",
                    "args": {"query": "用户偏好"},
                    "id": "mem_1",
                    "type": "tool_call",
                }],
            )
        return AIMessage(content="根据记忆,你偏好简洁回答。")


def _hit(content: str, source: str = "explicit"):
    return SimpleNamespace(value={
        "content": content, "source": source, "created_at": "2026-09-04T00:00:00+00:00",
    })


def _state(user_text: str = "你好"):
    return {"messages": [HumanMessage(content=user_text)], "subagent_results": []}


def _sys_prompt(llm) -> str:
    return llm.calls[0][0].content


# ---------- agents.md 固定 system ----------

AGENTS_MD_FIXTURE = "## 用户背景\n- 测试夹具背景,不依赖仓库根 agents.md"


def test_agents_md_injected_in_supervisor(monkeypatch):
    """agents.md 全文进入 supervisor 固定 system(夹具注入,不依赖仓库根文件)。"""
    from agent import supervisor

    monkeypatch.setattr(
        supervisor, "load_agents_md", lambda path="agents.md": AGENTS_MD_FIXTURE
    )
    llm = FakeLLM(route=Route(next="answer"))
    route_node(_state(), llm)
    sys = _sys_prompt(llm)
    assert "## 权威背景" in sys
    assert "用户背景" in sys


def test_agents_md_injected_in_answer(monkeypatch):
    """agents.md 全文进入 answer 固定 system(生成回答的一侧)。"""
    from agent import answer

    monkeypatch.setattr(
        answer, "load_agents_md", lambda path="agents.md": AGENTS_MD_FIXTURE
    )
    llm = FakeLLM(ai_content="好的。")
    answer_node(_state(), llm)
    assert "用户背景" in _sys_prompt(llm)


def test_agents_md_missing_placeholder(monkeypatch):
    """agents.md 缺失时给占位提示而非报错(monkeypatch 使用方命名空间的绑定)。"""
    from agent import supervisor

    monkeypatch.setattr(
        supervisor, "load_agents_md",
        lambda path="agents.md": "(未提供 agents.md,按默认行为运行)",
    )
    llm = FakeLLM(route=Route(next="answer"))
    route_node(_state(), llm)
    assert "未提供 agents.md" in _sys_prompt(llm)


def test_load_agents_md_missing_file_placeholder():
    """load_agents_md 对不存在的路径返回占位提示。"""
    assert "未提供 agents.md" in load_agents_md("__不存在的文件__.md")


def test_load_agents_md_reads_existing_file(tmp_path):
    """load_agents_md 读取真实存在的文件(tmp_path 夹具,不依赖仓库根 agents.md)。"""
    f = tmp_path / "agents.md"
    f.write_text("# 测试背景\n正文", encoding="utf-8")
    assert "测试背景" in load_agents_md(str(f))


# ---------- memory_search 工具(读) ----------


def test_memory_search_tool_hits(monkeypatch):
    """命中:返回 JSON 列表,含 content/source/created_at;namespace 与 query 正确。"""
    fake = FakeStore([_hit("用户偏好中文回复")])
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    out = memory_search.invoke({"query": "用户偏好"})
    assert "用户偏好中文回复" in out
    assert "explicit" in out
    assert fake.last_namespace == ("memory", "default")
    assert fake.last_query == "用户偏好"


def test_memory_search_tool_no_hits(monkeypatch):
    """无命中:返回空 JSON 数组。"""
    fake = FakeStore([])
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    assert memory_search.invoke({"query": "天气"}) == "[]"


def test_memory_search_tool_failure_is_visible(monkeypatch):
    """检索失败:返回可见错误文本,不吞异常返回空。"""
    class BoomStore:
        def search(self, namespace, query=None, limit=10):
            raise RuntimeError("embedding 服务挂了")

    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: BoomStore())
    out = memory_search.invoke({"query": "x"})
    assert "记忆检索不可用" in out


# ---------- store_memory 工具(写) ----------


def test_store_memory_tool_writes(monkeypatch):
    """写入:一条原子事实入库,source 默认 explicit,返回确认。"""
    fake = FakeStore()
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    out = store_memory.invoke({"content": "用户偏好简洁回答"})
    assert "已记住" in out
    assert len(fake.written) == 1
    ns, key, value = fake.written[0]
    assert ns == ("memory", "default")
    assert value["content"] == "用户偏好简洁回答"
    assert value["source"] == "explicit"


# ---------- answer 记忆工具循环(ADR-0011 核心) ----------


def test_answer_runs_memory_tool_loop(monkeypatch):
    """answer 在回答前按需调 memory_search,工具结果以 ToolMessage 回填,再收尾。"""
    fake = FakeStore([_hit("用户偏好简洁回答")])
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    llm = FakeMemoryLLM()
    result = answer_node(_state("你知道我喜欢什么风格"), llm)
    assert result["messages"][0].content == "根据记忆,你偏好简洁回答。"
    # 首帧之后,第二帧消息里回填了工具结果 ToolMessage
    assert any(isinstance(m, ToolMessage) for m in llm.calls[1])
    assert any("用户偏好简洁回答" in m.content for m in llm.calls[1] if isinstance(m, ToolMessage))
    # 工具结果不进主图 state(仅本轮消息流,不污染后续固定 system)
    assert len(result["messages"]) == 1


def test_answer_memory_loop_capped(monkeypatch):
    """answer 记忆循环达 MEMORY_LOOP_MAX 被截断,不死循环(双层防失控)。"""
    class AlwaysToolLLM:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "memory_search",
                    "args": {"query": "x"},
                    "id": "c0",
                    "type": "tool_call",
                }],
            )

    from agent.answer import MEMORY_LOOP_MAX

    fake = FakeStore([_hit("a")])
    monkeypatch.setattr("agent.memory_ctx._default_store", lambda: fake)
    result = answer_node(_state(), AlwaysToolLLM())
    # 循环在有限轮内终止,仍返回 AIMessage(而非无限/抛错)
    assert isinstance(result["messages"][0], AIMessage)
    assert MEMORY_LOOP_MAX >= 1
