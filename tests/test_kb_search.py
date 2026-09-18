"""R-T1 单测:kb_search 工具(FakeStore 注入,不依赖 DB/embedding)。"""

import json

from tools.rag.kb_search import SNIPPET_LIMIT, kb_search


class FakeStore:
    """假 RAGStore:按查询词返回固定命中。"""

    def __init__(self, per_query):
        self._per_query = per_query

    def search(self, query, top_k=5):
        return self._per_query.get(query, [])[:top_k]


HIT_A = {"doc_id": "d1", "filename": "a.md", "seq": 0,
         "content": "昆玉河沿岸有玉渊潭公园。", "score": 0.1}


def test_kb_search_returns_json_hits(monkeypatch):
    monkeypatch.setattr(
        "tools.rag.kb_search._default_store", lambda: FakeStore({"昆玉河": [HIT_A]})
    )
    hits = json.loads(kb_search.invoke({"query": "昆玉河"}))
    assert hits[0]["doc_id"] == "d1"
    assert hits[0]["filename"] == "a.md"
    assert "玉渊潭" in hits[0]["content"]


def test_kb_search_empty_returns_empty_array(monkeypatch):
    monkeypatch.setattr(
        "tools.rag.kb_search._default_store", lambda: FakeStore({})
    )
    assert kb_search.invoke({"query": "没有的东西"}) == "[]"


def test_kb_search_truncates_content(monkeypatch):
    monkeypatch.setattr(
        "tools.rag.kb_search._default_store",
        lambda: FakeStore({"q": [{**HIT_A, "content": "长" * 1000}]}),
    )
    hits = json.loads(kb_search.invoke({"query": "q"}))
    assert len(hits[0]["content"]) == SNIPPET_LIMIT


def test_kb_search_top_k_clamped(monkeypatch):
    """异常 top_k 被钳制到 1-10,防模型给大值拖垮检索。"""
    store = FakeStore({"q": [dict(HIT_A, seq=i) for i in range(20)]})
    monkeypatch.setattr("tools.rag.kb_search._default_store", lambda: store)
    hits = json.loads(kb_search.invoke({"query": "q", "top_k": 99}))
    assert len(hits) == 10
