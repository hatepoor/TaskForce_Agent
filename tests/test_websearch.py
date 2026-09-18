"""web_search 工具单测(模块 10 T1,AnySearch 版):mock httpx 验证格式/截断/降级,不发真实网络请求。"""

import json
from types import SimpleNamespace

import httpx

import tools.websearch.search as search


def _setup(monkeypatch, key="k1"):
    monkeypatch.setattr(
        search, "get_settings", lambda: SimpleNamespace(anysearch_api_key=key)
    )


def _mock_post(monkeypatch, payload, status=200):
    """替换 httpx.post 返回假响应;记录调用入参供断言。"""
    calls: list[tuple] = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        return httpx.Response(status_code=status, json=payload)

    monkeypatch.setattr(search.httpx, "post", fake_post)
    return calls


def _invoke(query="langgraph", max_results=None):
    args = {"query": query}
    if max_results is not None:
        args["max_results"] = max_results
    return json.loads(search.web_search.invoke(args))


def _results():
    return [
        {
            "title": "  Go 1.26 Release Notes  ",
            "url": "https://go.dev/doc/go1.26",
            "snippet": "引言。" + "很长的描述" * 200,
        },
        {"title": "CrewAI", "url": "https://crewai.com", "snippet": "角色扮演式多智能体框架。"},
        {"title": "", "url": "", "snippet": "  只有摘要  "},
        {"title": "", "url": "", "snippet": ""},
        {"title": "第 5 条", "url": "https://five.example", "snippet": "溢出条目"},
        {"title": "第 6 条", "url": "https://six.example", "snippet": "第六条"},
    ]


def test_success_format_and_truncation(monkeypatch):
    _setup(monkeypatch)
    calls = _mock_post(
        monkeypatch, {"code": 0, "message": "success", "data": {"results": _results()}}
    )
    raw = _invoke(max_results=3)
    assert len(raw) == 3
    first = raw[0]
    assert set(first) == {"title", "url", "snippet"}
    assert first["title"] == "Go 1.26 Release Notes"  # 两端空白已剥
    assert first["url"] == "https://go.dev/doc/go1.26"
    assert len(first["snippet"]) == search.SNIPPET_MAX  # 超长摘要截断到上限
    url, kw = calls[0]
    assert url == f"{search.API_BASE}/v1/search"
    assert kw["json"] == {"query": "langgraph", "max_results": 3}
    assert kw["headers"]["Authorization"] == "Bearer k1"


def test_snippet_fallback_to_content(monkeypatch):
    _setup(monkeypatch)
    payload = {
        "code": 0,
        "data": {"results": [
            {"title": "no snippet", "url": "https://a", "content": "正文兜底内容。"},
        ]},
    }
    _mock_post(monkeypatch, payload)
    raw = _invoke()
    assert raw[0]["snippet"] == "正文兜底内容。"


def test_empty_field_skipped(monkeypatch):
    _setup(monkeypatch)
    _mock_post(monkeypatch, {"code": 0, "data": {"results": _results()}})
    raw = _invoke(max_results=5)
    assert len(raw) == 5  # title/snippet 全空的条目被跳过,未溢出
    assert raw[2]["title"] == "" and raw[2]["snippet"] == "只有摘要"
    assert raw[-1]["title"] == "第 6 条"


def test_max_results_clamp(monkeypatch):
    _setup(monkeypatch)
    calls = _mock_post(monkeypatch, {"code": 0, "data": {"results": _results()}})
    assert len(_invoke(max_results=10)) == search.MAX_RESULTS
    assert calls[-1][1]["json"]["max_results"] == search.MAX_RESULTS  # 上游也收到钳制后的值
    assert len(_invoke(max_results=1)) == 1
    assert len(_invoke(max_results=0)) == 1  # 下限钳到 1


def test_http_error_returns_empty(monkeypatch):
    _setup(monkeypatch)
    _mock_post(monkeypatch, {"message": "invalid api key"}, status=401)
    assert _invoke() == []


def test_business_error_returns_empty(monkeypatch):
    _setup(monkeypatch)
    _mock_post(monkeypatch, {"code": -1, "message": "Query is required."})
    assert _invoke() == []


def test_network_error_returns_empty(monkeypatch):
    _setup(monkeypatch)

    def boom(*a, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(search.httpx, "post", boom)
    assert _invoke() == []


def test_no_api_key_anonymous(monkeypatch):
    _setup(monkeypatch, key="")
    calls = _mock_post(monkeypatch, {"code": 0, "data": {"results": _results()[:1]}})
    raw = _invoke()
    assert len(raw) == 1  # 无 key 走匿名,仍能搜索
    assert "Authorization" not in calls[0][1]["headers"]
