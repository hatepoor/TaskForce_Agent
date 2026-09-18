"""模块 09 T1 单测:沙箱客户端(mock 解析/降级/截断 + 真沙箱冒烟 skipif)。"""

from types import SimpleNamespace

import httpx
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
        lambda: SimpleNamespace(sandbox_url="http://sbx", sandbox_api_key="k1"),
    )


def _mock_http(monkeypatch, payload, status=200):
    """替换 httpx.request 返回假响应;记录调用入参供断言。"""
    calls: list[tuple] = []

    def fake_request(method, url, **kw):
        calls.append((method, url, kw))
        return httpx.Response(status_code=status, json=payload)

    monkeypatch.setattr(client.httpx, "request", fake_request)
    return calls


def test_unconfigured_returns_error_not_raise(monkeypatch):
    """未配置 SANDBOX_URL:返回结构化错误,绝不抛异常(工具侧纪律)。"""
    monkeypatch.setattr(
        client, "get_settings",
        lambda: SimpleNamespace(sandbox_url="", sandbox_api_key=""),
    )
    r = execute_python("print(1)")
    assert r["ok"] is False
    assert "未配置" in r["error"]


def test_execute_success_parse(monkeypatch):
    _mock_settings(monkeypatch)
    payload = {"stdout": "2", "stderr": "", "exit_code": 0, "duration_ms": 1.0}
    calls = _mock_http(monkeypatch, payload)
    r = execute_python("print(1+1)")
    assert r["ok"] is True and r["stdout"] == "2" and r["exit_code"] == 0
    assert r["truncated"] is False
    method, url, kw = calls[0]
    assert (method, url) == ("POST", "http://sbx/execute")
    assert kw["json"]["code"] == "print(1+1)"
    assert kw["headers"]["Authorization"] == "Bearer k1"


def test_execute_stdout_truncated(monkeypatch):
    _mock_settings(monkeypatch)
    big = "x" * (client.STDOUT_LIMIT + 500)
    _mock_http(monkeypatch, {"stdout": big, "stderr": "", "exit_code": 0, "duration_ms": 1.0})
    r = execute_python("print('x')")
    assert r["truncated"] is True
    assert len(r["stdout"]) == client.STDOUT_LIMIT


def test_execute_timeout_exit_code_kept(monkeypatch):
    """exit_code 124(超时)也原样透传,由 LLM 判断语义。"""
    _mock_settings(monkeypatch)
    payload = {"stdout": "", "stderr": "killed", "exit_code": 124, "duration_ms": 999.0}
    _mock_http(monkeypatch, payload)
    assert execute_python("while True: pass")["exit_code"] == 124


def test_http_error_structured(monkeypatch):
    _mock_settings(monkeypatch)
    _mock_http(monkeypatch, {"detail": "文件不存在"}, status=404)
    r = read_file("nope.txt")
    assert r["ok"] is False
    assert "404" in r["error"]


def test_network_error_structured(monkeypatch):
    _mock_settings(monkeypatch)

    def boom(*a, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(client.httpx, "request", boom)
    r = sandbox_health()
    assert r["ok"] is False
    assert "不可达" in r["error"]


def test_write_read_roundtrip(monkeypatch):
    _mock_settings(monkeypatch)
    calls = _mock_http(monkeypatch, {"ok": True, "path": "a.txt"})
    assert write_file("a.txt", "hi") == {"ok": True, "path": "a.txt"}
    assert calls[0][2]["json"] == {"filename": "a.txt", "content": "hi"}


def test_list_files_parses_listdir(monkeypatch):
    """list_files 经 execute_python 组合:解析 stdout 最后一行的 JSON 数组。"""
    _mock_settings(monkeypatch)
    payload = {"stdout": '["a.txt", "b.py"]\n', "stderr": "", "exit_code": 0, "duration_ms": 1.0}
    _mock_http(monkeypatch, payload)
    assert list_files() == {"ok": True, "files": ["a.txt", "b.py"]}


# ---------- sandbox_meta 三态(模块 10 附带:执行能力对主智能体可见) ----------

def test_sandbox_meta_three_states(monkeypatch):
    from tools.sandbox import client as sb

    # 未配置
    monkeypatch.setattr(
        sb, "get_settings", lambda: SimpleNamespace(sandbox_url="", sandbox_api_key="")
    )
    sb.sandbox_meta.cache_clear()
    assert "未配置" in sb.sandbox_meta()
    # 已配置但不可达(真实 /health 响应形状为 {status:...},无 ok 键)
    monkeypatch.setattr(
        sb, "get_settings", lambda: SimpleNamespace(sandbox_url="http://sbx", sandbox_api_key="k")
    )
    monkeypatch.setattr(sb, "sandbox_health", lambda: {"status": "error"})
    sb.sandbox_meta.cache_clear()
    assert "不可达" in sb.sandbox_meta()
    # 正常:给出能力概览
    monkeypatch.setattr(sb, "sandbox_health", lambda: {"status": "ok"})
    sb.sandbox_meta.cache_clear()
    m = sb.sandbox_meta()
    assert "http://sbx" in m and "execute_python" in m


# ---------- 真沙箱冒烟(未配置自动 skip,主线不阻塞) ----------

_REAL = bool(get_settings().sandbox_url)


@pytest.mark.skipif(not _REAL, reason="沙箱未配置(SANDBOX_URL 为空)")
def test_sandbox_smoke_real():
    r = execute_python("print(1+1)")
    assert r["ok"] is True
    assert r["exit_code"] == 0
    assert "2" in r["stdout"]


@pytest.mark.skipif(not _REAL, reason="沙箱未配置(SANDBOX_URL 为空)")
def test_sandbox_files_roundtrip_real():
    assert write_file("probe_t1_09.txt", "hello taskforce")["ok"] is True
    assert read_file("probe_t1_09.txt")["content"] == "hello taskforce"
    assert "probe_t1_09.txt" in list_files()["files"]
