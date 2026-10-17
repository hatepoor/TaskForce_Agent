"""模块 09 T1 单测:沙箱客户端(E2B 内核,mock 解析/降级/截断 + 真沙箱冒烟 skipif)。

mock 策略:client 从 get_settings() 取配置、从 _sandbox() 取实例,全显式无环境变量——
替换这两个入口即全链路可控:fake Sandbox 记录 run_code 调用,files 走内存 store,
不真连腾讯云。
"""

from types import SimpleNamespace

import pytest

from settings.config import get_settings
from tools.sandbox import client
from tools.sandbox.client import (
    execute_python,
    list_files,
    read_file,
    sandbox_health,
    write_file,
)


def _mock_settings(monkeypatch):
    monkeypatch.setattr(
        client, "get_settings",
        lambda: SimpleNamespace(
            e2b_api_key="e2b_k1", e2b_domain="sbx.example.com", ags_template="T",
        ),
    )


def _mock_unconfigured(monkeypatch):
    monkeypatch.setattr(
        client, "get_settings",
        lambda: SimpleNamespace(e2b_api_key="", e2b_domain="", ags_template=""),
    )


def _execution(out="", err=(), text="", error=None):
    """拼一个 e2b Execution 的形状:client 消费 logs.stdout/stderr、text、error。"""
    return SimpleNamespace(
        text=text,
        logs=SimpleNamespace(stdout=[out] if out else [], stderr=list(err)),
        error=error,
    )


class _FakeFiles:
    def __init__(self, store):
        self._store = store

    def write(self, path, content):
        self._store[path] = content
        return path

    def read(self, path):
        if path not in self._store:
            raise FileNotFoundError(path)
        return self._store[path]


class _FakeSandbox:
    """client._sandbox 的替身:记录 run_code 调用,files 走内存 store。"""

    def __init__(self, execution=None):
        self._execution = execution
        self.exec_calls: list[tuple] = []
        self.store: dict[str, str] = {}
        self.files = _FakeFiles(self.store)

    def run_code(self, code, **kw):
        self.exec_calls.append((code, kw))
        return self._execution


def _patch_sandbox(monkeypatch, fake):
    monkeypatch.setattr(client, "_sandbox", lambda: fake)


def test_unconfigured_returns_error_not_raise(monkeypatch):
    """未配置 E2B_API_KEY:返回结构化错误,绝不抛异常(工具侧纪律)。"""
    _mock_unconfigured(monkeypatch)
    r = execute_python("print(1)")
    assert r["ok"] is False
    assert "未配置" in r["error"]


def test_execute_success_parse(monkeypatch):
    _mock_settings(monkeypatch)
    fake = _FakeSandbox(_execution(out="2"))
    _patch_sandbox(monkeypatch, fake)
    r = execute_python("print(1+1)")
    assert r["ok"] is True and r["stdout"] == "2" and r["exit_code"] == 0
    assert r["truncated"] is False
    code, _kw = fake.exec_calls[0]
    assert code == "print(1+1)"


def test_execute_text_fallback(monkeypatch):
    """无 print、代码以表达式结尾:stdout 兜底取富结果的主结果文本。"""
    _mock_settings(monkeypatch)
    _patch_sandbox(monkeypatch, _FakeSandbox(_execution(text="42")))
    r = execute_python("1+1")
    assert r["ok"] is True and r["stdout"] == "42"


def test_execute_stdout_truncated(monkeypatch):
    _mock_settings(monkeypatch)
    big = "x" * (client.STDOUT_LIMIT + 500)
    _patch_sandbox(monkeypatch, _FakeSandbox(_execution(out=big)))
    r = execute_python("print('x')")
    assert r["truncated"] is True
    assert len(r["stdout"]) == client.STDOUT_LIMIT


def test_execute_code_error_exit_code_1(monkeypatch):
    """代码内异常:exit_code=1,traceback 进 stderr 与代码 stderr 合并。"""
    _mock_settings(monkeypatch)
    err = SimpleNamespace(
        name="ValueError", value="boom", traceback="Traceback ... ValueError: boom",
    )
    _patch_sandbox(monkeypatch, _FakeSandbox(_execution(err=["warn line"], error=err)))
    r = execute_python("raise ValueError('boom')")
    assert r["ok"] is True and r["exit_code"] == 1
    assert "warn line" in r["stderr"] and "ValueError: boom" in r["stderr"]


def test_execute_timeout_exit_code_124(monkeypatch):
    """SDK 抛 TimeoutException:exit_code 映射回旧契约 124。"""
    from e2b.exceptions import TimeoutException

    _mock_settings(monkeypatch)

    class _Boom:
        def run_code(self, code, **kw):
            raise TimeoutException("timed out")

    _patch_sandbox(monkeypatch, _Boom())
    r = execute_python("while True: pass")
    assert r["ok"] is False and r["exit_code"] == 124
    assert "超时" in r["error"]


def test_stale_instance_recreated_and_retried(monkeypatch):
    """实例被云端回收(TTL 到期/删除):丢弃旧引用、重建一次后重试成功。"""
    from e2b.exceptions import NotFoundException

    _mock_settings(monkeypatch)
    stale_calls = []

    class _Stale:
        def run_code(self, code, **kw):
            stale_calls.append(code)
            raise NotFoundException(
                '{"error":"Not Found","message":'
                '"The sandbox instance does not exist or has been deleted"}'
            )

    fresh = _FakeSandbox(_execution(out="2"))
    boxes = [_Stale(), fresh]
    monkeypatch.setattr(client, "_sandbox", lambda: boxes.pop(0))

    r = execute_python("print(1+1)")
    assert r["ok"] is True and r["stdout"] == "2"
    assert stale_calls == ["print(1+1)"]
    assert len(fresh.exec_calls) == 1


def test_missing_file_does_not_recreate(monkeypatch):
    """文件不存在(FileNotFoundException)不是实例失效,不得触发重建。"""
    from e2b.exceptions import FileNotFoundException

    _mock_settings(monkeypatch)

    class _Files:
        def read(self, path):
            raise FileNotFoundException(f"File {path} not found in sandbox")

    class _Sandbox:
        files = _Files()

    created = []

    def _fake_sandbox():
        created.append(1)
        return _Sandbox()

    monkeypatch.setattr(client, "_sandbox", _fake_sandbox)
    r = read_file("nope.txt")
    assert r["ok"] is False
    assert len(created) == 1


def test_network_error_structured(monkeypatch):
    _mock_settings(monkeypatch)

    class _Boom:
        def run_code(self, code, **kw):
            raise ConnectionError("refused")

    _patch_sandbox(monkeypatch, _Boom())
    r = sandbox_health()
    assert r["ok"] is False
    assert "不可达" in r["error"]


def test_write_read_roundtrip(monkeypatch):
    _mock_settings(monkeypatch)
    _patch_sandbox(monkeypatch, _FakeSandbox())
    assert write_file("a.txt", "hi") == {"ok": True, "path": "a.txt"}
    assert read_file("a.txt") == {"ok": True, "filename": "a.txt", "content": "hi"}


def test_read_missing_structured(monkeypatch):
    """读不存在的文件:SDK 抛 NotFound 类异常,统一转 ok=False,不抛。"""
    _mock_settings(monkeypatch)
    _patch_sandbox(monkeypatch, _FakeSandbox())
    r = read_file("nope.txt")
    assert r["ok"] is False


def test_list_files_parses_listdir(monkeypatch):
    """list_files 经 execute_python 组合:解析 stdout 最后一行的 JSON 数组。"""
    _mock_settings(monkeypatch)
    fake = _FakeSandbox(_execution(out='["a.txt", "b.py"]\n'))
    _patch_sandbox(monkeypatch, fake)
    assert list_files() == {"ok": True, "files": ["a.txt", "b.py"]}


# ---------- sandbox_meta 三态(模块 10 附带:执行能力对主智能体可见) ----------

def test_sandbox_meta_three_states(monkeypatch):
    # 未配置
    _mock_unconfigured(monkeypatch)
    client.sandbox_meta.cache_clear()
    assert "未配置" in client.sandbox_meta()
    # 已配置但不可达(探活失败返回 {ok: False, ...},无 status 键)
    _mock_settings(monkeypatch)
    monkeypatch.setattr(client, "sandbox_health", lambda: {"ok": False, "error": "x"})
    client.sandbox_meta.cache_clear()
    assert "不可达" in client.sandbox_meta()
    # 正常:给出能力概览
    monkeypatch.setattr(client, "sandbox_health", lambda: {"status": "ok"})
    client.sandbox_meta.cache_clear()
    m = client.sandbox_meta()
    assert "execute_python" in m and "腾讯云" in m


# ---------- 真沙箱冒烟(未配置自动 skip,主线不阻塞) ----------

_REAL = bool(get_settings().e2b_api_key and get_settings().e2b_domain)


@pytest.mark.skipif(not _REAL, reason="沙箱未配置(E2B_API_KEY/E2B_DOMAIN 为空)")
def test_sandbox_smoke_real():
    r = execute_python("print(1+1)")
    assert r["ok"] is True
    assert r["exit_code"] == 0
    assert "2" in r["stdout"]


@pytest.mark.skipif(not _REAL, reason="沙箱未配置(E2B_API_KEY/E2B_DOMAIN 为空)")
def test_sandbox_files_roundtrip_real():
    assert write_file("probe_t1_09.txt", "hello taskforce")["ok"] is True
    assert read_file("probe_t1_09.txt")["content"] == "hello taskforce"
    assert "probe_t1_09.txt" in list_files()["files"]
