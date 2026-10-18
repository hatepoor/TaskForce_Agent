"""模块 04 store 层单测(建表侧)。

`client` 用假对象注入(`monkeypatch get_client`), **不连真 Milvus**; 但 schema / index 对象是
pymilvus 真实构造的本地对象(不发网络请求), 所以字段类型、分析器配置、HNSW 参数都是真断言,
不是断言"我们自己的 dict"。

几处容易写错的形态(已实测, 别照直觉写):
- `FieldSchema.params["analyzer_params"]` 存的是 **JSON 字符串**而不是 dict;
- `IndexParams` 是 list 子类, 但每项是 `IndexParam` **对象**(属性访问 + `get_index_configs()`),
  不是 dict —— 它的 `repr` 长得像 dict, 别被骗着去下标取值;
- `dtype` 是 `DataType` 枚举(Python 3.11+ 的 IntEnum `str()` 会打印数字, 别被 "21" 骗到)。
"""
from __future__ import annotations

import json
from dataclasses import fields

import pytest

pymilvus = pytest.importorskip("pymilvus")  # store 只在 rag2 extra 下可用

from pymilvus import DataType, FunctionType  # noqa: E402

from rag_v01 import store  # noqa: E402
from rag_v01.config import Config  # noqa: E402
from rag_v01.contracts import (  # noqa: E402
    TYPE_IMAGE,
    TYPE_TEXT,
    ChildChunk,
    IngestReport,
    ParentChunk,
)

DOC = "0123456789abcdef"
FIXED_TIME = "2026-09-21T00:00:00+00:00"

# ---------------------------------------------------------------- 假 client


class FakeClient:
    """假 MilvusClient: 只实现 store.py 用到的方法, 把入参原样记下来。

    `search_results` / `query_results` 由用例注入: search 返回 `list[list[hit]]`(一次查询一行),
    query 返回行列表 —— 形状与真客户端一致, 这样 `_hit` / `get_parents` 的解析逻辑是真被测的,
    而不是只测了"我们调了哪些方法"。
    """

    def __init__(
        self,
        *,
        existing=(),
        dim: int = 1024,
        functions=("text_bm25",),
        analyzer_params: str = "current",
        search_results=(),
        query_results=(),
    ) -> None:
        self.collections: set[str] = set(existing)
        self.dim = dim
        self.function_names = list(functions)
        # "current" = 当前 schema 那份词表; 传字符串可造"旧表"(比如只有 tokenizer)或坏值
        self.analyzer_params = (
            json.dumps(store._analyzer_params())
            if analyzer_params == "current"
            else analyzer_params
        )
        self.search_results = list(search_results)
        self.query_results = list(query_results)
        self.created: list[tuple[str, dict]] = []
        self.loaded: list[str] = []
        self.flushed: list[str] = []
        self.upserts: list[tuple[str, list[dict]]] = []
        self.deletes: list[tuple[str, str]] = []
        self.searches: list[dict] = []
        self.queries: list[dict] = []

    def has_collection(self, name: str) -> bool:
        return name in self.collections

    def create_collection(self, name: str, **kwargs) -> None:
        self.created.append((name, kwargs))
        self.collections.add(name)

    def load_collection(self, name: str) -> None:
        self.loaded.append(name)

    def flush(self, name: str) -> None:
        self.flushed.append(name)

    def describe_collection(self, name: str) -> dict:
        """只回 store.py 会读的键: dense 的 dim、text 的 analyzer_params、functions。"""
        return {
            "fields": [
                {"name": "dense", "params": {"dim": self.dim}},
                {"name": "text", "params": {"analyzer_params": self.analyzer_params}},
            ],
            "functions": [{"name": n} for n in self.function_names],
        }

    def upsert(self, name: str, data) -> dict:
        self.upserts.append((name, list(data)))
        return {"upsert_count": len(data)}

    def delete(self, name: str, filter: str) -> dict:  # noqa: A002  (参数名对齐真客户端)
        self.deletes.append((name, filter))
        return {"delete_count": 1}

    def search(self, name: str, **kwargs):
        self.searches.append({"collection": name, **kwargs})
        return [self.search_results]

    def query(self, name: str, **kwargs):
        self.queries.append({"collection": name, **kwargs})
        return self.query_results


@pytest.fixture
def wired_client(monkeypatch):
    """注入假 client: `client = wired_client(dim=1024)`。"""

    def _install(**kw) -> FakeClient:
        fake = FakeClient(**kw)
        monkeypatch.setattr(store, "get_client", lambda: fake)
        return fake

    return _install


def field(schema, name: str):
    return next(f for f in schema.fields if f.name == name)


def index_of(idx, field_name: str):
    """取某字段的索引项: 返回 pymilvus 的 `IndexParam` 对象(属性访问, 不是 dict)。"""
    return next(item for item in list(idx) if item.field_name == field_name)


# ---------------------------------------------------------------- children schema


def test_child_schema_fields_and_types():
    schema = store._child_schema(1024)

    assert [f.name for f in schema.fields] == [
        "chunk_id",
        "parent_id",
        "doc_id",
        "source",
        "chunk_type",
        "page_no",
        "text",
        "dense",
        "sparse",
        "metadata",
    ]
    assert field(schema, "chunk_id").is_primary is True
    assert field(schema, "page_no").dtype == DataType.INT64
    assert field(schema, "dense").dtype == DataType.FLOAT_VECTOR
    assert field(schema, "sparse").dtype == DataType.SPARSE_FLOAT_VECTOR
    assert field(schema, "metadata").dtype == DataType.JSON


def test_child_schema_dense_dim_follows_argument():
    assert field(store._child_schema(768), "dense").params["dim"] == 768
    assert field(store._child_schema(1024), "dense").params["dim"] == 1024


def test_child_schema_text_field_carries_jieba_analyzer_with_stop_words():
    """analyzer 是 schema 级配置: 写在 text 字段上, 入库与查询两侧共用(坑位 1)。

    `stop` 词表不是可选项: 实测 jieba 会把空格当 token, 而空格几乎存在于每一块 —— 不删它,
    带空格的 query 会在 sparse 路命中一大批无关子块, RRF 只吃名次所以噪声票与真信号票等值。
    """
    params = field(store._child_schema(1024), "text").params

    assert params["max_length"] == store._CHILD_TEXT_MAX
    assert params["enable_analyzer"] is True
    # 注意: 这里存的是 JSON **字符串**, 不是 dict
    analyzer = json.loads(params["analyzer_params"])
    assert analyzer["tokenizer"] == "jieba"
    (stop,) = [flt for flt in analyzer["filter"] if flt["type"] == "stop"]
    stop_words = set(stop["stop_words"])
    assert {" ", "\n", "的", "|", "。"} <= stop_words  # 空白/标点/中文虚词都在
    assert "*" in stop_words and "a" in stop_words  # 由 string 模块展开, 不是手敲
    assert "苹果" not in stop_words and "检索" not in stop_words  # 实词一个都不能误删


def test_child_schema_declares_bm25_function():
    (fn,) = store._child_schema(1024).functions

    assert fn.name == store._BM25_FUNCTION
    assert fn.type == FunctionType.BM25
    assert list(fn.input_field_names) == ["text"]
    assert list(fn.output_field_names) == ["sparse"]


def test_child_index_hnsw_and_sparse_inverted():
    idx = store._child_index()

    dense = index_of(idx, "dense")
    assert dense.index_type == "HNSW"
    # get_index_configs() 是"索引参数 + index_type + metric_type"的合集, 按需取键
    configs = dense.get_index_configs()
    assert configs["M"] == store._HNSW_M == 16
    assert configs["efConstruction"] == store._HNSW_EF_CONSTRUCTION == 200
    assert configs["metric_type"] == "COSINE"

    sparse = index_of(idx, "sparse")
    assert sparse.index_type == "SPARSE_INVERTED_INDEX"
    assert sparse.get_index_configs()["metric_type"] == "BM25"


# ---------------------------------------------------------------- parents schema


def test_parent_schema_is_minimal_plus_dummy_vector():
    """parents 只做点查: 字段刻意最少, 唯一的向量字段是**占位**(见文件头事实 1/3)。"""
    schema = store._parent_schema()

    assert [f.name for f in schema.fields] == ["parent_id", "text", "doc_id", "metadata", "dense"]
    assert field(schema, "parent_id").is_primary is True
    assert field(schema, "text").params["max_length"] == store._PARENT_TEXT_MAX
    assert field(schema, "dense").dtype == DataType.FLOAT_VECTOR
    assert field(schema, "dense").params["dim"] == store.PARENT_DUMMY_DIM == 2
    assert schema.functions == []  # 没有 BM25 Function: 它不做检索
    assert store.PARENT_DUMMY_VECTOR == [0.0, 0.0]


def test_parent_index_flat_dummy_and_doc_id_inverted():
    idx = store._parent_index()

    assert index_of(idx, "dense").index_type == "FLAT"  # 只为满足"向量字段必须有索引"
    assert index_of(idx, "doc_id").index_type == "INVERTED"  # 按文档整删/过滤要它


# ---------------------------------------------------------------- ensure_collections


def test_ensure_collections_creates_both_then_loads(wired_client):
    client = wired_client(existing=())

    store.ensure_collections(dim=1024)

    assert [name for name, _ in client.created] == [store.COLL_CHILDREN, store.COLL_PARENTS]
    child_kwargs = dict(client.created)[store.COLL_CHILDREN]
    assert field(child_kwargs["schema"], "dense").params["dim"] == 1024
    assert child_kwargs["index_params"] is not None
    assert client.loaded == [store.COLL_CHILDREN, store.COLL_PARENTS]


def test_ensure_collections_is_idempotent(wired_client):
    """已存在: 不重建, 但照样 load(Milvus 重启后 load 状态会丢, 幂等调用是恢复手段)。"""
    client = wired_client(existing=(store.COLL_CHILDREN, store.COLL_PARENTS), dim=1024)

    store.ensure_collections(dim=1024)

    assert client.created == []
    assert client.loaded == [store.COLL_CHILDREN, store.COLL_PARENTS]


def test_ensure_collections_rejects_dim_mismatch(wired_client):
    client = wired_client(existing=(store.COLL_CHILDREN,), dim=1024)

    with pytest.raises(ValueError, match="RAG2_EMBED_DIM=768"):
        store.ensure_collections(dim=768)

    assert store.COLL_PARENTS not in client.collections  # 自检不通过就别再往下建


def test_ensure_collections_rejects_missing_bm25_function(wired_client):
    """Function 不在 → sparse 路会静默查不到东西, 必须在建表自检里拦住。"""
    wired_client(existing=(store.COLL_CHILDREN,), dim=1024, functions=())

    with pytest.raises(ValueError, match="text_bm25"):
        store.ensure_collections(dim=1024)


def test_ensure_collections_rejects_stale_analyzer(wired_client):
    """加停用词之前建的表: sparse 路被空格噪声淹没, 而且只有重建能修 —— 必须报错指路。"""
    wired_client(
        existing=(store.COLL_CHILDREN,),
        dim=1024,
        analyzer_params=json.dumps({"tokenizer": "jieba"}),
    )

    with pytest.raises(ValueError, match="停用词"):
        store.ensure_collections(dim=1024)


@pytest.mark.parametrize("bad", ["", "not-json", "null"])
def test_ensure_collections_rejects_unreadable_analyzer(wired_client, bad):
    """analyzer_params 读不出来时按"没有停用词"处理: 宁可让人重建, 不赌它是好的。"""
    wired_client(existing=(store.COLL_CHILDREN,), dim=1024, analyzer_params=bad)

    with pytest.raises(ValueError, match="停用词"):
        store.ensure_collections(dim=1024)


def test_ensure_collections_falls_back_to_config_dim(wired_client, monkeypatch):
    monkeypatch.setattr(store, "_cfg", lambda: Config(embed_dim=768))
    client = wired_client(existing=(store.COLL_CHILDREN,), dim=768)

    store.ensure_collections()  # 不传参 → 用 RAG2_EMBED_DIM

    assert store.COLL_PARENTS in client.collections


def test_load_and_flush_touch_both_collections(wired_client):
    client = wired_client()

    store.load()
    store.flush()

    assert client.loaded == [store.COLL_CHILDREN, store.COLL_PARENTS]
    assert client.flushed == [store.COLL_CHILDREN, store.COLL_PARENTS]


def test_get_client_uses_configured_uri(monkeypatch):
    """客户端 URI 只能来自 config(模块内不直读 os.environ), 且必须走懒加载单例。"""
    seen: dict[str, str] = {}

    class FakeMilvusClient:
        def __init__(self, uri: str) -> None:
            seen["uri"] = uri

    monkeypatch.setattr(pymilvus, "MilvusClient", FakeMilvusClient)
    monkeypatch.setattr(store, "_cfg", lambda: Config(milvus_uri="http://probe:19530"))
    store.get_client.cache_clear()
    try:
        client = store.get_client()
        again = store.get_client()
    finally:
        store.get_client.cache_clear()

    assert isinstance(client, FakeMilvusClient)
    assert client is again  # 单例: 不重复握手
    assert seen["uri"] == "http://probe:19530"


# ---------------------------------------------------------------- 写入侧


def child_row(
    chunk_id: str,
    *,
    text: str | None = None,
    chunk_type: str = TYPE_TEXT,
    page_no: int | None = 3,
    image_path: str | None = None,
) -> ChildChunk:
    return ChildChunk(
        chunk_id=chunk_id,
        text=text if text is not None else f"内容-{chunk_id}",
        parent_id=f"{DOC}:p001",
        doc_id=DOC,
        source="a.md",
        page_no=page_no,
        heading_path="一 > 二",
        chunk_type=chunk_type,
        created_at=FIXED_TIME,
        image_path=image_path,
    )


def parent_row(parent_id: str, *, text: str = "父块全文") -> ParentChunk:
    return ParentChunk(
        chunk_id=parent_id,
        text=text,
        doc_id=DOC,
        source="a.md",
        page_no=None,
        heading_path="一",
        created_at=FIXED_TIME,
    )


def payloads(client: FakeClient, collection: str) -> list[dict]:
    """把某 collection 的分批 upsert 摊平成 payload 列表。"""
    return [row for name, batch in client.upserts if name == collection for row in batch]


def test_upsert_children_payload_has_no_sparse_and_maps_vectors(wired_client):
    client = wired_client()
    rows = [child_row("c1"), child_row("c2")]
    vectors = [[1.0, 0.0], [0.0, 1.0]]

    written = store.upsert_children(rows, vectors)

    assert written == 2
    assert client.upserts[0][0] == store.COLL_CHILDREN
    data = payloads(client, store.COLL_CHILDREN)
    assert [row["dense"] for row in data] == vectors  # 顺序与 rows 一一对应
    assert "sparse" not in data[0]  # 由 Function 生成, 手填会被拒/被忽略(坑位 2)
    assert set(data[0]) == {
        "chunk_id",
        "parent_id",
        "doc_id",
        "source",
        "chunk_type",
        "page_no",
        "text",
        "dense",
        "metadata",
    }


def test_upsert_children_converts_missing_page_no_to_sentinel(wired_client):
    client = wired_client()

    rows = [child_row("c1", page_no=None), child_row("c2", page_no=7)]
    store.upsert_children(rows, [[0.0], [0.0]])

    assert [row["page_no"] for row in payloads(client, store.COLL_CHILDREN)] == [-1, 7]


def test_upsert_children_metadata_carries_source_and_image_path(wired_client):
    client = wired_client()
    rows = [
        child_row("c1"),
        child_row("c2", chunk_type=TYPE_IMAGE, image_path="doc/p0001_i001.png"),
    ]

    store.upsert_children(rows, [[0.0], [0.0]])

    meta_text, meta_image = [row["metadata"] for row in payloads(client, store.COLL_CHILDREN)]
    assert set(meta_text) == {"source", "page_no", "heading_path", "char_len", "created_at"}
    assert meta_text["source"] == "a.md"
    assert meta_text["page_no"] == 3
    assert meta_text["char_len"] == len("内容-c1")
    assert meta_image["image_path"] == "doc/p0001_i001.png"


def test_upsert_children_skips_oversized_text_and_warns(wired_client):
    """8192 是**字节**上限: 2730 汉字 = 8190 字节照样收, 2800 汉字被跳过并进 warnings。"""
    client = wired_client()
    warnings: list[str] = []
    rows = [child_row("ok", text="中" * 2730), child_row("huge", text="中" * 2800)]

    written = store.upsert_children(rows, [[0.0], [0.0]], warnings=warnings)

    assert written == 1
    assert [row["chunk_id"] for row in payloads(client, store.COLL_CHILDREN)] == ["ok"]
    assert len(warnings) == 1
    assert "huge" in warnings[0]


def test_upsert_children_rejects_length_mismatch(wired_client):
    """错位写库是最难查的故障: 数量对不上必须在入口就抛(坑位 10)。"""
    wired_client()

    with pytest.raises(ValueError, match="不一致"):
        store.upsert_children([child_row("c1"), child_row("c2")], [[0.0]])


def test_upsert_children_batches_by_upsert_batch(wired_client):
    client = wired_client()
    rows = [child_row(f"c{i}") for i in range(store.UPSERT_BATCH + 1)]

    written = store.upsert_children(rows, [[0.0]] * len(rows))

    assert written == store.UPSERT_BATCH + 1
    assert [len(batch) for name, batch in client.upserts if name == store.COLL_CHILDREN] == [500, 1]


def test_upsert_parents_writes_dummy_vector(wired_client):
    client = wired_client()

    written = store.upsert_parents([parent_row("p001"), parent_row("p002")])

    assert written == 2
    data = payloads(client, store.COLL_PARENTS)
    assert [row["parent_id"] for row in data] == ["p001", "p002"]
    assert set(data[0]) == {"parent_id", "text", "doc_id", "metadata", "dense"}
    assert data[0]["dense"] == store.PARENT_DUMMY_VECTOR
    assert data[0]["metadata"]["page_no"] == -1  # 父块无页码概念 → 哨兵


# ---------------------------------------------------------------- 删除


def test_delete_doc_filters_both_collections_then_flushes(wired_client):
    client = wired_client()

    store.delete_doc(DOC)

    assert client.deletes == [
        (store.COLL_CHILDREN, f'doc_id == "{DOC}"'),
        (store.COLL_PARENTS, f'doc_id == "{DOC}"'),
    ]
    assert client.flushed == [store.COLL_CHILDREN, store.COLL_PARENTS]


def test_quote_rejects_values_that_would_break_the_expression():
    for bad in ('a" or doc_id != "', "a\\b", "a\nb"):
        with pytest.raises(ValueError, match="非法字符"):
            store._quote(bad)

    assert store._quote(DOC) == f'"{DOC}"'


# ---------------------------------------------------------------- 检索侧


HIT_ROW = {
    "id": "c1",
    "distance": 0.87,
    "entity": {
        "chunk_id": "c1",
        "parent_id": f"{DOC}:p001",
        "text": "命中文本",
        "chunk_type": TYPE_TEXT,
        "metadata": {"source": "a.md", "page_no": 3},
    },
}


def test_dense_search_passes_ef_and_maps_hits(wired_client, monkeypatch):
    monkeypatch.setattr(store, "_cfg", lambda: Config())  # 默认 ef=RAG2_HNSW_EF=96
    client = wired_client(search_results=[HIT_ROW])

    hits = store.dense_search([0.1] * 8, 20)

    call = client.searches[0]
    assert call["collection"] == store.COLL_CHILDREN
    assert call["anns_field"] == "dense"
    assert call["limit"] == 20
    assert call["search_params"] == {"metric_type": "COSINE", "params": {"ef": 96}}
    assert call["output_fields"] == store._HIT_FIELDS
    assert call["consistency_level"] == "Strong"  # 刚 ingest 完就查也要看得见(坑位 8)
    assert hits == [
        store.Hit(
            chunk_id="c1",
            parent_id=f"{DOC}:p001",
            text="命中文本",
            chunk_type=TYPE_TEXT,
            score=0.87,
            metadata={"source": "a.md", "page_no": 3},
        )
    ]


def test_dense_search_accepts_explicit_ef(wired_client):
    client = wired_client(search_results=[])

    store.dense_search([0.1] * 8, 5, ef=64)

    assert client.searches[0]["search_params"]["params"]["ef"] == 64


def test_sparse_search_sends_raw_query(wired_client):
    """不自己分词: 原样送服务端, 由 schema 上的 jieba analyzer 处理(坑位 1)。"""
    client = wired_client(search_results=[HIT_ROW])

    hits = store.sparse_search("向量数据库 混合检索", 20)

    call = client.searches[0]
    assert call["data"] == ["向量数据库 混合检索"]
    assert call["anns_field"] == "sparse"
    assert call["search_params"] == {"metric_type": "BM25"}
    assert len(hits) == 1


def test_get_parents_empty_list_makes_no_request(wired_client):
    client = wired_client()

    assert store.get_parents([]) == {}
    assert client.queries == []


def test_get_parents_builds_in_filter_and_keys_by_id(wired_client):
    client = wired_client(
        query_results=[
            {"parent_id": "p001", "text": "父块全文", "doc_id": DOC, "metadata": {"k": 1}},
            {"parent_id": "p002", "text": "另一段", "doc_id": DOC, "metadata": None},
        ]
    )

    result = store.get_parents(["p001", "p002"])

    call = client.queries[0]
    assert call["collection"] == store.COLL_PARENTS
    assert call["filter"] == 'parent_id in ["p001", "p002"]'
    assert call["output_fields"] == store._PARENT_FIELDS
    assert set(result) == {"p001", "p002"}
    assert result["p001"].text == "父块全文"
    assert result["p001"].metadata == {"k": 1}
    assert result["p002"].metadata == {}  # 服务端回 None 时不能把 None 透出去


def test_hit_tolerates_missing_entity_fields():
    """在线路径上少一个字段不该整批崩: 缺的用空值兜住, 分数仍要拿到。"""
    hit = store._hit({"id": "c9", "distance": 2.5})

    assert hit.chunk_id == "c9"
    assert (hit.parent_id, hit.text, hit.chunk_type, hit.metadata) == ("", "", "", {})
    assert hit.score == 2.5


# ---------------------------------------------------------------- 运维面(模块 07 的服务面)


def test_ingest_report_field_names_are_frozen():
    """报告是 CLI 与调用方的接口面: 字段改名等于悄悄改协议, 在这里钉死。"""
    assert [f.name for f in fields(IngestReport)] == [
        "ok_sources",
        "failed",
        "total_parents",
        "total_children",
        "warnings",
    ]


def test_ingest_report_defaults_are_independent():
    """`warnings` 用 default_factory: 两个报告绝不能共享同一个 dict。"""
    first = IngestReport(ok_sources=[], failed={})
    second = IngestReport(ok_sources=[], failed={})
    first.warnings["a.md"] = ["x"]

    assert second.warnings == {}


def test_list_docs_aggregates_children_per_doc(wired_client):
    rows = [
        {
            "doc_id": "doc-b",
            "source": "b.md",
            "metadata": {"created_at": "2025-01-01T00:00:00+00:00"},
        },
        {
            "doc_id": "doc-a",
            "source": "a.md",
            "metadata": {"created_at": "2025-01-01T00:00:00+00:00"},
        },
        {
            "doc_id": "doc-a",
            "source": "a.md",
            "metadata": {"created_at": "2025-01-02T00:00:00+00:00"},
        },
        {
            "doc_id": "doc-a",
            "source": "a.md",
            "metadata": {"created_at": "2024-12-31T00:00:00+00:00"},
        },
    ]
    client = wired_client(query_results=rows)

    docs = store.list_docs()

    assert docs == [
        {
            "doc_id": "doc-a",
            "source": "a.md",
            "children": 3,
            "created_at": "2025-01-02T00:00:00+00:00",
        },
        {
            "doc_id": "doc-b",
            "source": "b.md",
            "children": 1,
            "created_at": "2025-01-01T00:00:00+00:00",
        },
    ]
    assert client.queries[0]["collection"] == store.COLL_CHILDREN
    assert client.queries[0]["output_fields"] == ["doc_id", "source", "metadata"]


def test_list_docs_tolerates_missing_source(wired_client):
    """老数据里 source 可能取不到: 不能让 KeyError 把 `list` 子命令带崩。"""
    wired_client(query_results=[{"doc_id": "doc-a"}])

    assert store.list_docs() == [
        {"doc_id": "doc-a", "source": "", "children": 1, "created_at": None}
    ]


def test_list_docs_empty(wired_client):
    wired_client(query_results=[])

    assert store.list_docs() == []


def test_purge_stale_deletes_older_versions_from_both_collections(wired_client):
    """重灌一个改过的文件: 旧版本(同 source、不同 doc_id)必须一起清掉, 否则检索会同时命中两份。"""
    client = wired_client(query_results=[{"doc_id": "old"}, {"doc_id": "old"}, {"doc_id": "new"}])

    stale = store.purge_stale("a.md", keep_doc_id="new")

    assert stale == ["old"]
    assert client.queries[0]["filter"] == 'source == "a.md"'
    assert client.deletes == [
        (store.COLL_CHILDREN, 'doc_id in ["old"]'),
        (store.COLL_PARENTS, 'doc_id in ["old"]'),
    ]


def test_purge_stale_is_a_noop_when_content_unchanged(wired_client):
    """文件没改 → doc_id 不变 → 一个版本都不该删(防"每次 ingest 都清库")。"""
    client = wired_client(query_results=[{"doc_id": "same"}])

    assert store.purge_stale("a.md", keep_doc_id="same") == []
    assert client.deletes == []


def test_purge_stale_handles_absent_source(wired_client):
    """首次入库: 库里还没有这个 source, 不该报错也不该发 delete。"""
    client = wired_client(query_results=[])

    assert store.purge_stale("new.md", keep_doc_id="abc") == []
    assert client.deletes == []


def test_purge_stale_sorts_and_dedupes_stale_ids(wired_client):
    client = wired_client(query_results=[{"doc_id": "b"}, {"doc_id": "a"}, {"doc_id": "b"}])

    stale = store.purge_stale("a.md", keep_doc_id="keep")

    assert stale == ["a", "b"]  # 去重 + 排序 → filter 字符串可复现
    assert client.deletes[0][1] == 'doc_id in ["a", "b"]'
