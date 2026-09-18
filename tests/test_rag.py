"""模块 04 单测:parse/split 纯本地直测;embed 与 RAGStore roundtrip 需 DB+智谱,未配置自动 skip。"""

import pytest

from tools.rag.parse import parse_document
from tools.rag.split import split_text


# ---------- T1 parse ----------
def _make(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_txt_and_md(tmp_path):
    for name in ("a.txt", "b.md"):
        p = _make(tmp_path, name, "知识库测试内容")
        assert "知识库测试内容" in parse_document(p)


def test_parse_docx(tmp_path):
    from docx import Document

    doc = Document()
    doc.add_paragraph("Word 段落内容")
    p = tmp_path / "c.docx"
    doc.save(str(p))
    assert "Word 段落内容" in parse_document(p)


def test_parse_pdf(tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)  # 空白页无文本层 -> 应报空文本错
    p = tmp_path / "d.pdf"
    with open(p, "wb") as f:
        writer.write(f)
    with pytest.raises(ValueError, match="为空"):
        parse_document(p)


def test_parse_unknown_suffix_raises(tmp_path):
    p = _make(tmp_path, "e.xyz", "内容")
    with pytest.raises(ValueError, match="不支持的文档格式"):
        parse_document(p)


def test_parse_empty_text_raises(tmp_path):
    p = _make(tmp_path, "f.txt", "   \n  ")
    with pytest.raises(ValueError, match="为空"):
        parse_document(p)


# ---------- T2 split ----------


def test_split_long_text_multiple_chunks():
    text = "这是一段测试文本。" * 300  # 远超 500 字
    chunks = split_text(text)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_split_short_text_single_chunk():
    chunks = split_text("短文本")
    assert len(chunks) == 1 and chunks[0] == "短文本"


# ---------- T2 embed(需智谱配置,未配置自动 skip) ----------

def _embedding_ready() -> bool:
    from settings.config import get_settings

    s = get_settings()
    return bool(s.embedding_api_key)


@pytest.mark.skipif(not _embedding_ready(), reason="EMBEDDING 未配置")
def test_embedding_dim_positive():
    from tools.rag.embed import embedding_dim

    assert embedding_dim() > 0


# ---------- T3/T4 RAGStore roundtrip(需 DB + 智谱,不可用自动 skip) ----------

@pytest.fixture(scope="module")
def store():
    """隔离 schema 中的 RAGStore:测试建表/上传不污染 public 下的真实知识库。

    模块 04 原版直接操作 public 表——维度测试的 DROP TABLE 曾把用户上传的文档清空
    (2026-09-04 实测踩坑,见 docs/troubleshooting/R-react-refactor.md #4)。
    """
    import uuid as _uuid

    from settings.config import get_settings
    from settings.db.base import get_conn
    from tools.rag.store import RAGStore

    url = get_settings().database_url
    schema = f"test_rag_{_uuid.uuid4().hex[:8]}"
    sep = "&" if "?" in url else "?"
    scoped = f"{url}{sep}options=-csearch_path%3D{schema}%2Cpublic"
    try:
        with get_conn(url) as conn:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.commit()
        s = RAGStore(database_url=scoped)
    except Exception as e:  # DB 未起 / embedding 未配置
        pytest.skip(f"RAGStore 依赖不可用:{e}")
    yield s
    with get_conn(url) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        conn.commit()


_FIXTURE_TEXT = "昆玉河是北京城内的河道,沿岸有玉渊潭公园与紫竹院公园。"


def _upload_fixture(store, name: str, content: str = _FIXTURE_TEXT) -> str:
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        path = f.name
    doc_id, _created = store.upload(Path(path), name)
    return doc_id


def test_upload_chunks_count(store):
    doc_id = _upload_fixture(store, "pytest-上传计数.txt")
    docs = [d for d in store.list_docs() if d["doc_id"] == doc_id]
    assert len(docs) == 1 and docs[0]["chunks"] >= 1


def test_search_roundtrip(store):
    _upload_fixture(store, "pytest-检索命中.txt")
    hits = store.search("昆玉河沿岸有什么公园", top_k=5)
    # RRF 融合重排后 top-1 可能变化,断言放宽为 top_k 内命中(05 模块)
    assert hits and any("昆玉河" in h["content"] for h in hits)


def test_search_score_降序且为正(store):
    """RRF 融合分语义:越大越相关,返回列表按 score 降序(05 模块)。"""
    _upload_fixture(store, "pytest-分数语义.txt")
    hits = store.search("昆玉河沿岸有什么公园", top_k=5)
    assert hits
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)


def test_hybrid_专名词面命中(store):
    """混合检索:专名/词面重合查询命中(05 模块)。"""
    _upload_fixture(store, "pytest-专名命中.txt")
    hits = store.search("紫竹院公园 荷花", top_k=5)
    assert hits and any("紫竹院" in h["content"] for h in hits)


def test_upload_后立即检索命中(store):
    """脏标记懒重建:upload 置脏,下次 search 重建后立即命中新文档(05 模块)。"""
    doc_id = _upload_fixture(store, "pytest-脏重建上传.txt", "脏重建测试文档:龙潭湖公园。")
    hits = store.search("龙潭湖公园", top_k=5)
    assert any(h["doc_id"] == doc_id for h in hits)


def test_delete_后不再命中(store):
    """脏标记懒重建:delete 置脏,重建后不再返回已删文档(05 模块)。"""
    doc_id = _upload_fixture(store, "pytest-脏重建删除.txt", "脏重建测试文档:龙潭湖公园。")
    store.delete(doc_id)
    hits = store.search("龙潭湖公园", top_k=5)
    assert all(h["doc_id"] != doc_id for h in hits)


def test_delete_removes_doc(store):
    doc_id = _upload_fixture(store, "pytest-待删除.txt")
    store.delete(doc_id)
    assert all(d["doc_id"] != doc_id for d in store.list_docs())


def test_dim_mismatch_raises(store):
    """伪造维度不符的 chunks 表,RAGStore 初始化应抛 RuntimeError(维度断言)。

    全程发生在隔离 schema 内(经 search_path),不再触碰 public 下的真实表。
    """
    from settings.db.base import get_conn
    from tools.rag.store import RAGStore

    db = store.database_url
    with get_conn(db) as conn:
        # 钉死当前 schema:全部 DDL 显式限定,不受 public 残留同名表的脏状态干扰
        schema = conn.execute("SELECT current_schema()").fetchone()[0]
        conn.execute(f'DROP TABLE IF EXISTS "{schema}".chunks')
        conn.execute(f'DROP TABLE IF EXISTS "{schema}".documents')
        conn.execute(
            f'CREATE TABLE "{schema}".chunks (id BIGSERIAL PRIMARY KEY, doc_id TEXT,'
            ' seq INT, content TEXT, embedding vector(4))'
        )
        conn.commit()
    with pytest.raises(RuntimeError, match="维度不一致"):
        RAGStore(db)
    # 清掉伪表并重建正常表:RAGStore 在维度断言处抛错,不会自己恢复,
    # 不恢复会让排在后面的用例撞上 "documents 不存在"
    with get_conn(db) as conn:
        conn.execute(f'DROP TABLE IF EXISTS "{schema}".chunks')
        conn.execute(f'DROP TABLE IF EXISTS "{schema}".documents')
        conn.commit()
    RAGStore(db)
    # 伪表与重建的表都在隔离 schema 内,由模块级 fixture 的 DROP SCHEMA CASCADE 收走


# ---------- 内容级防重(2026-09-04,upload 返回 (doc_id, created)) ----------


def _tmp_txt(content: str):
    import tempfile
    from pathlib import Path

    # newline="":禁用换行翻译,让 CRLF 原样落盘(否则 Windows 会写成 \r\r\n)
    f = tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8", newline=""
    )
    f.write(content)
    f.close()
    return Path(f.name)


def test_duplicate_upload_reuses_doc(store):
    """同内容重复上传:同一 doc_id、created=False,库中不新增。"""
    p = _tmp_txt("防重测试:玉渊潭与紫竹院。")
    doc_id1, created1 = store.upload(p, "防重-第一次.txt")
    doc_id2, created2 = store.upload(p, "防重-第二次.txt")
    assert created1 is True
    assert (doc_id2, created2) == (doc_id1, False)
    assert len([d for d in store.list_docs() if d["doc_id"] == doc_id1]) == 1


def test_duplicate_same_content_different_name(store):
    """同内容不同文件名:仍判重命中(内容级判定,不依赖文件名)。"""
    id1, _ = store.upload(_tmp_txt("同文异名内容。"), "甲.txt")
    id2, created = store.upload(_tmp_txt("同文异名内容。"), "乙.txt")
    assert created is False and id2 == id1


def test_same_name_different_content_new_doc(store):
    """同名不同内容(改稿重传):正常入库为新文档。"""
    id1, c1 = store.upload(_tmp_txt("版本甲的内容。"), "同名.txt")
    id2, c2 = store.upload(_tmp_txt("版本乙的内容完全不同。"), "同名.txt")
    assert c1 and c2 and id1 != id2


def test_content_hash_line_ending_normalization(store):
    """仅换行符差异(CRLF vs LF):规范化后视为同内容,判重命中。"""
    id1, _ = store.upload(_tmp_txt("行一\n行二"), "换行-a.txt")
    id2, created = store.upload(_tmp_txt("行一\r\n行二"), "换行-b.txt")
    assert created is False and id2 == id1


def test_unique_index_on_user_hash(store):
    """(user_id, content_hash) 唯一索引存在:竞态兜底的数据库级保障。"""
    from settings.db.base import get_conn

    with get_conn(store.database_url) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'uk_documents_user_hash'"
        ).fetchone()
    assert row is not None
