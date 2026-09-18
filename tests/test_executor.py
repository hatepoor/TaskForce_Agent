"""模块 09 单测:executor ReAct 子图(fake model 脚本化 + 沙箱底层 monkeypatch)。

不连真沙箱/真 MCP:底层 client 函数与 MCPToolProvider 全部 monkeypatch;
真沙箱冒烟在 test_sandbox.py(隧道依赖),此处聚焦子图行为与 warnings 纪律。
"""

from langchain_core.messages import AIMessage

import agent.subagents.executor as ex
from agent.contracts import SubgraphContract
from agent.subagents.executor import _gather_tools, build_executor_graph


def _call(name, args, cid="c1"):
    """构造与真实模型一致的 tool_call dict。"""
    return {"name": name, "args": args, "id": cid, "type": "tool_call"}


def _contract(task="统计 CSV 总销售额"):
    return SubgraphContract(task=task, user_utterance="帮我统计这份 CSV 的总销售额").model_dump()


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
        return AIMessage("执行完成")


class FakeAlwaysToolLLM:
    """永远想再调工具:验证轮数上限掐断为 partial。"""

    def __init__(self):
        self._n = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self._n += 1
        call = _call("execute_python", {"code": "1"}, f"c{self._n}")
        return AIMessage(content="", tool_calls=[call])


class FakeEmptyMCP:
    """MCP 装配降级:发现不到任何工具(空配置等价形态)。"""

    def list_tools(self):
        return []

    def get_langchain_tools(self, names):
        return []


def _setup(monkeypatch, sandbox_results=None):
    """统一 stub:MCP 空 + 沙箱底层按脚本返回。返回 (calls, run_results)。"""
    monkeypatch.setattr(ex, "MCPToolProvider", FakeEmptyMCP)
    calls: list[tuple] = []

    def fake_execute(code, timeout=60):
        calls.append(("execute_python", code))
        return (sandbox_results or {}).get("execute", {"ok": True, "stdout": "2", "stderr": "",
                                                       "exit_code": 0, "duration_ms": 1.0,
                                                       "truncated": False})

    def fake_write(filename, content):
        calls.append(("write_file", filename))
        return {"ok": True, "path": filename}

    monkeypatch.setattr(ex, "_execute_python", fake_execute)
    import tools.tool.files as files_mod

    monkeypatch.setattr(files_mod, "_write_file", fake_write)
    return calls


def test_success_flow_tool_calls_then_finish(monkeypatch):
    """脚本化"一轮两个工具调用 + 收尾":warnings 强制列执行侧效应(T3 验收)。"""
    _setup(monkeypatch)
    llm = FakeReActLLM(rounds=[
        AIMessage(content="", tool_calls=[
            _call("execute_python", {"code": "print(1+1)"}, "c1"),
            _call("write_file", {"filename": "a.txt", "content": "hi"}, "c2"),
        ]),
        AIMessage("统计完成,总额 2"),
    ])
    final = build_executor_graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.agent == "executor"
    assert summary.status == "success"
    assert summary.conclusion == "统计完成,总额 2"
    assert any("a.txt" in w for w in summary.warnings)
    assert any("1 段" in w for w in summary.warnings)


def test_prose_fallback_no_effects(monkeypatch):
    """纯收尾无工具调用:status success,warnings 为空(无执行效应)。"""
    _setup(monkeypatch)
    llm = FakeReActLLM(rounds=[])
    final = build_executor_graph(llm).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "success"
    assert summary.warnings == []


def test_partial_when_iteration_limit(monkeypatch):
    """永远想调工具:12 轮上限掐断为 partial,warnings 含上限提示 + 效应。"""
    _setup(monkeypatch)
    final = build_executor_graph(FakeAlwaysToolLLM()).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "partial"
    assert any("上限" in w for w in summary.warnings)
    assert any("13 段" in w for w in summary.warnings)


def test_gather_tools_builtin_set(monkeypatch):
    """MCP 降级为空时,装配结果恰为 6 个内置工具。"""
    monkeypatch.setattr(ex, "MCPToolProvider", FakeEmptyMCP)
    names = {t.name for t in _gather_tools()}
    assert names == {"read_file", "write_file", "list_files",
                     "execute_python", "load_skill", "get_tool_detail"}


def test_tool_layer_uses_sandbox_client(monkeypatch):
    """@tool 壳调用沙箱 client:write_file 工具走 _write_file(参数透传)。"""
    _setup(monkeypatch)
    from tools.tool.files import write_file

    out = write_file.invoke({"filename": "t.txt", "content": "x"})
    assert "'path': 't.txt'" in out
