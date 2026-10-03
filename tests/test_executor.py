"""模块 09 单测:executor ReAct 子图(fake model 脚本化 + 沙箱底层 monkeypatch)。

不连真沙箱/真 MCP:底层 client 函数与 MCPToolProvider 全部 monkeypatch;
真沙箱冒烟在 test_sandbox.py(隧道依赖),此处聚焦子图行为与 warnings 纪律。
"""

from types import SimpleNamespace

from langchain_core.messages import AIMessage

import agent.subagents.executor as ex
from agent.contracts import SubgraphContract
from agent.subagents.executor import (
    _gather_tools,
    build_executor_graph,
    execute_python,
    get_tool_detail,
    load_skill,
)
from tools.tool.files import list_files, read_file, write_file

_BUILTIN = [read_file, write_file, list_files, execute_python, load_skill, get_tool_detail]


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
    """统一 stub:沙箱底层按脚本返回(工具列表由测试显式注入, c3)。返回 (calls, run_results)。"""
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
        # 收尾带合格 report(≥80 字):M1 后 success 收尾不合格会触发 finalize 重试
        AIMessage('{"conclusion": "统计完成,总额 2", "key_points": ["总额 2"], '
                  '"report": "任务执行成稿:经 execute_python 对 CSV 逐行求和,总额为 2;'
                  '脚本一次跑通无报错,结果文件 a.txt 已写入沙箱工作区,关键输出与解读如上。"}'),
    ])
    final = build_executor_graph(llm, tools=_BUILTIN).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.agent == "executor"
    assert summary.status == "success"
    assert summary.conclusion == "统计完成,总额 2"
    assert summary.report.startswith("任务执行成稿")  # 成稿随摘要回传(M1)
    assert any("a.txt" in w for w in summary.warnings)
    assert any("1 段" in w for w in summary.warnings)


def test_prose_fallback_no_effects(monkeypatch):
    """纯收尾无工具调用:status success,warnings 为空(无执行效应)。"""
    _setup(monkeypatch)
    llm = FakeReActLLM(rounds=[])
    final = build_executor_graph(llm, tools=_BUILTIN).invoke({"contract": _contract()})
    (summary,) = final["subagent_results"]
    assert summary.status == "success"
    assert summary.warnings == []


def test_partial_when_iteration_limit(monkeypatch):
    """永远想调工具:12 轮上限掐断为 partial,warnings 含上限提示 + 效应。"""
    _setup(monkeypatch)
    final = build_executor_graph(FakeAlwaysToolLLM(), tools=_BUILTIN).invoke(
        {"contract": _contract()}
    )
    (summary,) = final["subagent_results"]
    assert summary.status == "partial"
    assert any("上限" in w for w in summary.warnings)
    assert any("13 段" in w for w in summary.warnings)
    assert summary.report == ""  # partial 无成稿(spec §七)


def test_gather_tools_builtin_set(monkeypatch):
    """MCP 降级为空时,装配结果恰为 8 个内置工具(含时钟与 skill 引用读取)。"""
    monkeypatch.setattr(ex, "MCPToolProvider", FakeEmptyMCP)
    names = {t.name for t in _gather_tools()}
    assert names == {
            "read_file",
            "write_file",
            "list_files",
            "execute_python",
            "load_skill",
            "load_skill_reference",
            "get_tool_detail",
            "get_current_time",
        }


def test_tool_layer_uses_sandbox_client(monkeypatch):
    """@tool 壳调用沙箱 client:write_file 工具走 _write_file(参数透传)。"""
    _setup(monkeypatch)
    from tools.tool.files import write_file

    out = write_file.invoke({"filename": "t.txt", "content": "x"})
    assert "'path': 't.txt'" in out


def test_injected_tools_single_source_for_meta_and_bind(monkeypatch):
    """c3:注入 tools 时 _gather_tools 不被调,meta 与 bind_tools 与注入列表同源。"""
    fake = [SimpleNamespace(name="fake_tool", description="假工具描述")]

    def _boom():
        raise AssertionError("_gather_tools 不应在注入 tools 时被调")

    monkeypatch.setattr(ex, "_gather_tools", _boom)
    slots: dict = {}

    def fake_load_prompt(name, **kw):
        slots[name] = kw
        return "P"

    monkeypatch.setattr(ex, "load_prompt", fake_load_prompt)
    captured: dict = {}

    class CapLLM(FakeReActLLM):
        def bind_tools(self, tools):
            captured["tools"] = tools
            return self

    build_executor_graph(CapLLM(rounds=[]), tools=fake).invoke({"contract": _contract()})
    assert captured["tools"] == fake
    assert "fake_tool" in slots["subagents/executor"]["tools_meta"]


def test_default_path_gathers_tools_exactly_once(monkeypatch):
    """c3:缺省路径 _gather_tools 只调一次(回归锁:原实现调两次,双倍 MCP 发现)。"""
    monkeypatch.setattr(ex, "MCPToolProvider", FakeEmptyMCP)
    n = {"c": 0}
    orig = ex._gather_tools

    def counting():
        n["c"] += 1
        return orig()

    monkeypatch.setattr(ex, "_gather_tools", counting)
    build_executor_graph(FakeReActLLM(rounds=[])).invoke({"contract": _contract()})
    assert n["c"] == 1
