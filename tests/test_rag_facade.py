"""rag_v01 管理面 facade 单测(c4):上传上限/原名落盘/判重快照/删除存在性 —— 全程不连 Milvus。

打桩点在最底层(`rag_v01.ingest` 流水线与 `rag_v01.store` 存储面),
facade 自身语义(上限早返回、临时文件原名、created 判定、404 布尔)全部真实执行。
"""

import hashlib

import rag_v01
import rag_v01.store as store_mod


class _FakeReport:
    def __init__(self, failed=None):
        self.failed = failed or {}


def _setup_store(monkeypatch, sources: dict[str, str]):
    """sources: {filename: doc_id},让 store 返回内核口径的行;返回删除记录列表。"""
    def fake_list():
        return [{"source": name, "doc_id": did, "children": 3} for name, did in sources.items()]

    deleted: list[str] = []
    monkeypatch.setattr(store_mod, "list_docs", fake_list)
    monkeypatch.setattr(store_mod, "delete_doc", lambda did: deleted.append(did))
    return deleted


def test_upload_rejects_oversize_before_touching_kernel(monkeypatch):
    """20MB 上限在 facade 最前面:超限早返回,ingest/store 一次都不调。"""
    def _boom(*a, **k):
        raise AssertionError("超限不应触达内核")

    monkeypatch.setattr(rag_v01, "ingest", _boom)
    monkeypatch.setattr(store_mod, "list_docs", _boom)
    r = rag_v01.upload(b"x" * (rag_v01.MAX_UPLOAD_BYTES + 1), "big.md")
    assert r["ok"] is False
    assert "20MB" in r["error"]
    assert r["name"] == "big.md"


def test_upload_preserves_original_name_and_judges_created(monkeypatch):
    """带原名落临时文件(source 语义)+ created 判定(新名 True/复用 False)+ 临时目录清理。"""
    sources = {"a.md": "d1"}
    _setup_store(monkeypatch, sources)
    seen: dict = {}

    def fake_ingest(paths):
        p = paths[0]
        seen["name"] = p.name
        seen["parent"] = p.parent
        seen["parent_existed"] = p.parent.exists()
        sources.setdefault(p.name, "d2")  # 内容寻址的简化:新名即新文档
        return _FakeReport()

    monkeypatch.setattr(rag_v01, "ingest", fake_ingest)

    r1 = rag_v01.upload(b"# hi", "报告 2024.md")
    assert r1 == {"ok": True, "error": "", "doc_id": "d2", "created": True, "name": "报告 2024.md"}
    assert seen["name"] == "报告 2024.md"  # 原名落盘,列表不会变乱码名
    assert seen["parent_existed"] is True  # ingest 执行时临时目录在
    assert not seen["parent"].exists()     # finally 已清理

    r2 = rag_v01.upload(b"# hi", "报告 2024.md")
    assert r2["ok"] is True and r2["created"] is False and r2["doc_id"] == "d2"


def test_upload_duplicate_content_returns_before_ingest(monkeypatch):
    """内容已存在: 不落临时文件、不 parse/embed, 直接返回已有 doc_id。"""
    content = b"# hi"
    doc_id = hashlib.sha256(content).hexdigest()[:16]
    _setup_store(monkeypatch, {"a.md": doc_id})

    def _boom(paths):
        raise AssertionError("重复内容不应再进 ingest")

    monkeypatch.setattr(rag_v01, "ingest", _boom)
    r = rag_v01.upload(content, "换个名字.md")

    assert r == {
        "ok": True,
        "error": "",
        "doc_id": doc_id,
        "created": False,
        "name": "a.md",
    }


def test_upload_failure_maps_ingest_error(monkeypatch):
    """入库失败:report.failed 的原因原样进 error(入口直接当 400 文案)。"""
    _setup_store(monkeypatch, {"a.md": "d1"})
    monkeypatch.setattr(
        rag_v01, "ingest",
        lambda paths: _FakeReport(failed={paths[0].name: "ValueError: 解析失败"}),
    )
    r = rag_v01.upload(b"xx", "bad.bin")
    assert r["ok"] is False
    assert r["error"] == "ValueError: 解析失败"


def test_delete_doc_missing_returns_false(monkeypatch):
    """存在性判定收编 facade:不存在返 False(404 文案归入口),存在清理后返 True。"""
    deleted = _setup_store(monkeypatch, {"a.md": "d1"})
    assert rag_v01.delete_doc("nope") is False
    assert deleted == []
    assert rag_v01.delete_doc("d1") is True
    assert deleted == ["d1"]


def test_list_docs_shapes_and_sorts(monkeypatch):
    """管理面列表定型:条目四键 + 按文件名排序;created_at 原样透传。"""
    monkeypatch.setattr(store_mod, "list_docs", lambda: [
        {"source": "b.md", "doc_id": "d2", "children": 5,
         "created_at": "2025-01-02T00:00:00+00:00"},
        {"source": "a.md", "doc_id": "d1", "children": 3},
    ])
    docs = rag_v01.list_docs()
    assert [d["filename"] for d in docs] == ["a.md", "b.md"]
    assert docs[0] == {"doc_id": "d1", "filename": "a.md", "chunks": 3, "created_at": None}
    assert docs[1]["created_at"] == "2025-01-02T00:00:00+00:00"
