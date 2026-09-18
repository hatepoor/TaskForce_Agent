"""混合检索评测:hybrid(RRF 融合)vs 纯向量基线,Recall@5/MRR@5 防退化(05 模块)。

评测库: tests/fixtures/rag_eval/ 下 8 篇固定中文文档;
查询按四类(专名 / 口语化 / 关键词组合 / 同义改写),gold 以文档级判定。
依赖 DB + 智谱 embedding,未配置自动 skip(隔离 schema,不污染 public 知识库)。
"""

from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent / "fixtures" / "rag_eval"

# (查询类型, 查询, gold 文档文件名)
QUERIES = [
    ("专名", "颐和园的长廊与十七孔桥", "颐和园.md"),
    ("专名", "豆包和智谱的 API 兼容吗", "大模型API.md"),
    ("口语化", "春天去哪看樱花", "玉渊潭公园.md"),
    ("口语化", "周末想打羽毛球怎么订场", "羽毛球.md"),
    ("关键词组合", "Python requests 反爬限速", "Python爬虫.md"),
    ("关键词组合", "B+树 哈希索引 区别", "数据库索引.md"),
    ("关键词组合", "亿通行 一卡通 哪个方便", "北京地铁.md"),
    ("同义改写", "皇家园林 昆明湖 在北京吗", "颐和园.md"),
    ("同义改写", "国产大模型厂商有哪些 API", "大模型API.md"),
]


@pytest.fixture(scope="module")
def eval_store():
    """隔离 schema 的 RAGStore + 上传全部评测文档;不可用自动 skip。"""
    import uuid as _uuid

    from settings.config import get_settings
    from settings.db.base import get_conn
    from tools.rag.store import RAGStore

    url = get_settings().database_url
    schema = f"test_rag_eval_{_uuid.uuid4().hex[:8]}"
    sep = "&" if "?" in url else "?"
    scoped = f"{url}{sep}options=-csearch_path%3D{schema}%2Cpublic"
    try:
        with get_conn(url) as conn:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.commit()
        store = RAGStore(database_url=scoped)
        for path in sorted(EVAL_DIR.glob("*.md")):
            store.upload(path, path.name)
    except Exception as e:
        pytest.skip(f"评测依赖不可用:{e}")
    yield store
    with get_conn(url) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        conn.commit()


def _gold_id(store) -> dict[str, str]:
    return {d["filename"]: d["doc_id"] for d in store.list_docs()}


def _recall5(hits: list[dict], gold_id: str) -> float:
    return 1.0 if any(h["doc_id"] == gold_id for h in hits[:5]) else 0.0


def _mrr5(hits: list[dict], gold_id: str) -> float:
    for rank, h in enumerate(hits[:5], start=1):
        if h["doc_id"] == gold_id:
            return 1.0 / rank
    return 0.0


def test_评测库上传完整(eval_store):
    docs = eval_store.list_docs()
    assert len(docs) == len(list(EVAL_DIR.glob("*.md")))


@pytest.mark.parametrize(
    "qtype, query, gold_file",
    QUERIES,
    ids=[q[1] for q in QUERIES],
)
def test_hybrid_不劣化于纯向量(eval_store, qtype, query, gold_file):
    """防退化断言:hybrid Recall@5 / MRR@5 均 >= 纯向量基线(白盒取 _search_vector)。"""
    gold = _gold_id(eval_store)[gold_file]
    hybrid = eval_store.search(query, top_k=5)
    vector = eval_store._search_vector(query, 5)

    r_h, r_v = _recall5(hybrid, gold), _recall5(vector, gold)
    m_h, m_v = _mrr5(hybrid, gold), _mrr5(vector, gold)
    assert r_h >= r_v, f"[{qtype}] {query!r}: hybrid Recall@5 {r_h} < 纯向量 {r_v}"
    assert m_h >= m_v, f"[{qtype}] {query!r}: hybrid MRR@5 {m_h} < 纯向量 {m_v}"


def test_融合分降序且为正(eval_store):
    hits = eval_store.search("颐和园的长廊与十七孔桥", top_k=5)
    assert hits
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)
