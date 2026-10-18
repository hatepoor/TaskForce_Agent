"""store.py —— Milvus 双 collection(children / parents)的建表与读写(04 篇)。

分工(04 篇 §2.3): children 承担召回(dense + sparse 双索引), parents 只承担回溯取全文
(按主键点查, 从不做向量检索)。两个 collection 名固定、不加前缀不改名(04 篇 §4.2)。

下面几处是**实机验证过的事实**(2026-09-21, 服务端 2.6.0 / pymilvus 2.6.17), 不是照文档猜的:
1. collection 必须至少有一个向量字段, 且**每个向量字段都必须建索引**才能 load:
   无向量字段 → 1100 schema does not contain vector field; 有向量字段无索引 → 65535
   there is no vector index on field。parents 因此要放一个占位向量 + 从不检索的 FLAT 索引;
2. 向量字段**不支持 nullable**(1100 vector type not support null), 标量字段才支持;
3. 向量维度下限是 2(1 报 65535 invalid dimension), 所以占位向量用 dim=2;
4. 内置 BM25 Function + jieba analyzer 可用, 且 `run_analyzer` 与本地
   `jieba.lcut_for_search(HMM=True)` 逐 token 一致; upsert payload 不带 sparse 成功。

本文件只 import 同级的 config / contracts, 不 import 项目其它包, 整目录可搬走。
"""
from __future__ import annotations

import json
import string
from dataclasses import dataclass, field
from functools import lru_cache

from .config import Config, load_config
from .contracts import ChildChunk, Chunk, ParentChunk

# collection 名固定: 05 / 07 篇与运维脚本都按这两个名字找数据, 改名等于换库
COLL_CHILDREN = "children"
COLL_PARENTS = "parents"

# VARCHAR 的 max_length 按**字节**算(04 篇坑位 7): 中文 UTF-8 约 3 字节/字。
# 子块上限 8192 字节(约 2700 汉字) —— 超过要告警不能静默截断(见 upsert_children)。
_ID_MAX = 64  # chunk_id / parent_id: "doc_id(16 位) + :pNNN[:cNNN]" 最长约 30
_DOC_ID_MAX = 64
_SOURCE_MAX = 512
_CHUNK_TYPE_MAX = 16
_CHILD_TEXT_MAX = 8192
_PARENT_TEXT_MAX = 65535  # 父块 1200~1800 字, 顶格留量给超长表格
UPSERT_BATCH = 500  # 单次 upsert 行数上限(经验值, 04 篇坑位 10)

# HNSW 定稿参数(04 篇 §4.4): M 每节点最大连接数, efConstruction 建图候选池
_HNSW_M = 16
_HNSW_EF_CONSTRUCTION = 200
_BM25_FUNCTION = "text_bm25"  # Function 名(会出现在 describe_collection 的 functions 里)

# jieba 会把空白与标点也切成 token: 实测样例语料 20 个子块 2540 个 token 里, 空格占 1109(44%)、
# 表格竖线 331、换行 62 —— 它们几乎出现在每一块里, 于是任何带空格/标点的 query 都会在 sparse 路
# 命中一大批无关子块, 而 RRF 只吃名次 → 噪声票与真信号票等值, 融合直接失真(04 篇坑位 1)。
#
# 为什么只能这样列: 这个 tokenizer 实测只支持 stop filter(removepunct / length / alphanumonly /
# lowercase 都报 "unsupport filter type"), 没有"按长度丢 token"或"丢标点"这类通用规则可用。
_ANALYZER_STOP_WORDS = (
    " ", "\n", "\r", "\t",                                # 空白: 最大宗的噪声源
    *string.punctuation,                                  # ASCII 标点(表格 Markdown 的 | 等)
    *"。，、；：！？…—～“”‘’（）《》【】「」",          # 全角/中文标点(同样要展开成单个字符)
    *string.ascii_letters,                                # 单字母 token(jieba 会切出 'a' 't' 'i')
    "的", "了", "是", "在", "和", "与", "就", "都", "也", "这", "那", "个", "上", "下",
    "里", "中", "为", "对", "从", "把", "被", "让", "给", "到", "着", "过", "而", "但",
)  # 末尾两行是中文单字虚词: BM25 里与"空格"同类(几乎每块都有), 不删一样是噪声项

# 建表自检只抽验这几个代表(空白 + 中文虚词), 不做全量比对: 服务端可能对词表做归一化, 全量比会误报
_ANALYZER_SENTINELS = (" ", "\n", "的")

# parents 的占位向量: 只为满足"collection 必须有向量字段且必须有索引"(见文件头事实 1/3),
# 内容恒为零向量、检索永不使用; dim=2 是服务端允许的最小维度, 所以只花 8 字节/行。
PARENT_DUMMY_DIM = 2
PARENT_DUMMY_VECTOR = [0.0] * PARENT_DUMMY_DIM


@lru_cache(maxsize=1)
def _cfg() -> Config:
    """配置懒加载(与 embed.py 同款): 单测注假配置、入口先载 .env 都不受 import 顺序影响。"""
    return load_config()


@lru_cache(maxsize=1)
def get_client():
    """Milvus 客户端单例(懒加载)。

    pymilvus 是可选的 rag2 依赖 → 懒 import(只做 embed 的环境不必装它); 客户端持有到 19530
    的连接, 每次新建会重复握手。单测 monkeypatch 这个函数注入假 client, 所以下面的函数只
    依赖 client 的**接口**(upsert / query / search ...), 不依赖它的实现。
    """
    from pymilvus import MilvusClient  # 懒 import: 见上

    return MilvusClient(uri=_cfg().milvus_uri)


def _analyzer_params() -> dict:
    """`text` 字段的分词配置: jieba + 停用词。

    入库与检索**两侧共用这一份**配置(schema 级), 所以不存在"两边词表不一致"的问题 —— 这正是
    04 篇 §2.5 选服务端内置 BM25 的收益; 代价是改词表必须重建 collection。
    """
    stop = {"type": "stop", "stop_words": list(_ANALYZER_STOP_WORDS)}
    return {"tokenizer": "jieba", "filter": [stop]}


def _child_schema(dim: int):
    """children schema(04 篇 §4.2): text 挂 BM25 Function 生成 sparse, dense 走 HNSW。

    `enable_analyzer` + jieba 必须写在 `text` 字段上: analyzer 是 **schema 级**配置, 入库与
    检索两侧都由服务端用它分词 —— 这也正是内置 BM25 天然没有"两侧分词漂移"的原因(坑位 1);
    代价是建表后想换分词只能重建 collection。
    """
    from pymilvus import DataType, Function, FunctionType, MilvusClient

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunk_id", DataType.VARCHAR, max_length=_ID_MAX, is_primary=True)
    schema.add_field("parent_id", DataType.VARCHAR, max_length=_ID_MAX)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=_DOC_ID_MAX)
    schema.add_field("source", DataType.VARCHAR, max_length=_SOURCE_MAX)
    schema.add_field("chunk_type", DataType.VARCHAR, max_length=_CHUNK_TYPE_MAX)
    schema.add_field("page_no", DataType.INT64)  # 无页码记 -1(哨兵, 04 篇坑位 7c)
    schema.add_field(
        "text",
        DataType.VARCHAR,
        max_length=_CHILD_TEXT_MAX,
        enable_analyzer=True,
        analyzer_params=_analyzer_params(),
    )
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)  # Function 的输出字段
    schema.add_field("metadata", DataType.JSON)
    schema.add_function(
        Function(
            name=_BM25_FUNCTION,
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse"],
        )
    )
    return schema


def _child_index():
    """children 索引: dense 用 HNSW(COSINE), sparse 用 SPARSE_INVERTED_INDEX(BM25)。

    sparse 的 metric 只能是 BM25、索引类型只能是倒排 —— 官方口径, 与 dense 那套连想都不用想
    (04 篇 §2.4); `ef` 是**查询期**参数, 不在索引里, 05 篇检索时按 RAG2_HNSW_EF 传入。
    """
    from pymilvus import MilvusClient

    idx = MilvusClient.prepare_index_params()
    idx.add_index(
        field_name="dense",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": _HNSW_M, "efConstruction": _HNSW_EF_CONSTRUCTION},
    )
    idx.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
    return idx


def _parent_schema():
    """parents schema(04 篇 §4.2): 只做点查, 所以刻意最简 —— 只多一个占位向量字段。"""
    from pymilvus import DataType, MilvusClient

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("parent_id", DataType.VARCHAR, max_length=_ID_MAX, is_primary=True)
    schema.add_field("text", DataType.VARCHAR, max_length=_PARENT_TEXT_MAX)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=_DOC_ID_MAX)
    schema.add_field("metadata", DataType.JSON)
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=PARENT_DUMMY_DIM)
    return schema


def _parent_index():
    """parents 索引: dense 用 FLAT(从不检索, 只为满足"向量字段必须有索引") + doc_id 倒排。

    `FLAT` 是暴力检索、不建额外图结构, 所以"从不检索"的代价只是它自己占的那点存储;
    `doc_id` 上的 INVERTED 是标量索引, 供按文档整删与按文档过滤用(04 篇坑位 9)。
    """
    from pymilvus import MilvusClient

    idx = MilvusClient.prepare_index_params()
    idx.add_index(field_name="dense", index_type="FLAT", metric_type="COSINE")
    idx.add_index(field_name="doc_id", index_type="INVERTED")
    return idx


def ensure_collections(dim: int | None = None) -> None:
    """幂等建表: 不存在则建(含索引), 已存在则自检; 最后统一 load。可在启动路径无脑调。

    `dim` 默认取 `RAG2_EMBED_DIM`; 显式传参是给单测与运维脚本用的(不依赖环境)。
    """
    client = get_client()
    want = dim if dim is not None else _cfg().embed_dim
    if client.has_collection(COLL_CHILDREN):
        _check_children(client, want)  # 已存在: 维度与 Function 都要对得上
    else:
        client.create_collection(
            COLL_CHILDREN, schema=_child_schema(want), index_params=_child_index()
        )
    if not client.has_collection(COLL_PARENTS):
        client.create_collection(
            COLL_PARENTS, schema=_parent_schema(), index_params=_parent_index()
        )
    load()


def _check_children(client, want_dim: int) -> None:
    """已存在的 children 自检: dense 维度 + BM25 Function + 分词停用词(04 篇坑位 5 / 3 / 1)。

    三条都必须查, 因为错了都不会当场报错: 维度不对要拖到插入/建索引才炸, 且报错不指向配置项;
    Function 不在(比如表是更早的 schema 建的)则 sparse 路永远查不到东西; 停用词不在则 sparse 路
    被空格/标点噪声淹没 —— 静默变差比报错难查。
    """
    desc = client.describe_collection(COLL_CHILDREN)
    got = next(
        (f["params"].get("dim") for f in desc.get("fields", []) if f.get("name") == "dense"),
        None,
    )
    if got is not None and int(got) != int(want_dim):
        raise ValueError(
            f"{COLL_CHILDREN}.dense dim={got}, 与 RAG2_EMBED_DIM={want_dim} 不一致; "
            "改维度只能重建 collection(先 drop, 再全量重灌 —— 04 篇坑位 6)"
        )
    names = {fn.get("name") for fn in desc.get("functions", [])}
    if _BM25_FUNCTION not in names:
        raise ValueError(
            f"{COLL_CHILDREN} 上找不到 BM25 Function {_BM25_FUNCTION!r}(实际: {sorted(names)}); "
            "sparse 路会静默查不到东西, 请重建 collection"
        )
    _check_analyzer(desc)


def _check_analyzer(desc: dict) -> None:
    """已存在的表是否带上了我们要求的停用词 —— 少了它 sparse 路会被空格/标点噪声淹没。

    为什么要查: analyzer 是 schema 级配置, **建表后改不了**; 加停用词之前建的旧表会静默保持
    "空格也当词"的行为 —— 带空格的 query 命中一大批无关子块, 而 RRF 只吃名次, 噪声票和真信号票
    等值, 融合直接失真(04 篇坑位 1)。这种表只靠人眼看不出来, 必须在建表自检里拦住。

    抽验 `_ANALYZER_SENTINELS` 几条而不是全量比对: 服务端可能对词表做归一化(去重/排序), 全量比对
    会误报; 抽到"空白 + 中文虚词"这两类代表就足以判定词表是加过滤之后的新版。
    """
    field = next((f for f in desc.get("fields", []) if f.get("name") == "text"), None)
    raw = (field or {}).get("params", {}).get("analyzer_params")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = None
    # 读不出来(缺失 / 不是 JSON / 是 null)一律当成"没有停用词": 宁可让人重建, 不赌那张表是好的
    filters = parsed.get("filter", []) if isinstance(parsed, dict) else []
    got = {
        word
        for flt in filters
        if isinstance(flt, dict) and flt.get("type") == "stop"
        for word in flt.get("stop_words", [])
    }
    missing = [word for word in _ANALYZER_SENTINELS if word not in got]
    if missing:
        raise ValueError(
            f"{COLL_CHILDREN}.text 的 analyzer 缺少停用词 {missing} —— 大概率是加停用词之前建的表; "
            "analyzer 建表后改不了, 必须 drop 后按当前 schema 重建并重新 ingest"
        )


def load() -> None:
    """把两个 collection 载入内存: 检索前必须 load, 而 Milvus 重启后 load 状态会丢。

    `load_collection` 幂等且开销小, 所以放在启动路径/`ensure_collections` 里无脑调(04 篇 §4.5)。
    """
    client = get_client()
    client.load_collection(COLL_CHILDREN)
    client.load_collection(COLL_PARENTS)


def flush() -> None:
    """让刚写入的数据落成可见: 一次 ingest 收尾调**一次**。

    为什么不每条 upsert 后调: flush 会封 segment 并触发索引构建, 是重操作(04 篇 §4.5);
    检索侧由 `consistency_level="Strong"` 兜底(05 篇)。
    """
    client = get_client()
    client.flush(COLL_CHILDREN)
    client.flush(COLL_PARENTS)

@dataclass(frozen=True,slots=True)
class Hit:
    """一条检索命中(04 篇 §3.2): 05 篇只按**名次**用它, 不依赖 `score` 的量纲。

    `score` 在 dense 路是 COSINE 相似度(越大越好), 在 sparse 路是 BM25 分(量纲完全不同);
    两路要合并时必须走 RRF 名次融合, 直接比分数是错的(05 篇 §2)。
    """

    chunk_id:str
    parent_id:str
    text:str
    chunk_type:str
    score:float
    metadata:dict=field(default_factory=dict)

@dataclass(frozen=True,slots=True)
class ParentRow:
    """父块点查结果: `text` 是命中子块后要给用户看/给模型读的完整上下文。"""

    parent_id: str
    text: str
    doc_id: str
    metadata: dict = field(default_factory=dict)

_HIT_FIELDS = ["chunk_id", "parent_id", "text", "chunk_type", "metadata"]
_PARENT_FIELDS = ["parent_id", "text", "doc_id", "metadata"]


def _metadata(row: Chunk) -> dict:
    """块的元信息 → Milvus 的 JSON 字段。

    进 metadata 的是"没有独立标量列"或"读的时候希望一并拿到"的项: source / page_no /
    heading_path / char_len / created_at, 图片块再加 image_path。page_no 与 source 在 children
    里本来就有列, 这里再放一份是**故意的**: `Hit.metadata` 要自足, 否则 05 / 07 篇展示"依据
    来自哪个文件第几页"还得回表查一次(04 篇 §3.2 的 Hit 只有 metadata 一个透传口)。
    """
    meta = {
        "source": row.source,
        "page_no": row.page_no if row.page_no is not None else -1,
        "heading_path": row.heading_path,
        "char_len": row.char_len,
        "created_at": row.created_at,
    }
    if row.image_path:
        meta["image_path"] = row.image_path
    return meta


def _quote(value: str) -> str:
    """把字符串安全地塞进 filter 表达式(04 篇坑位 11)。

    Milvus 的 filter 是**字符串表达式**, 拼错了就是注入面。doc_id / parent_id 都是 03 篇按
    规则生成的 hex + 固定后缀, 本来没有危险; 但今后总会有人拿别的字段来拼, 所以统一在这里
    卡一道: 出现引号、反斜杠、换行这类会改变表达式结构的字符就直接拒绝, 不做"尽力转义"。
    """
    if any(ch in value for ch in ('"', "\\", "\n", "\r")):
        raise ValueError(f"filter 值含非法字符, 拒绝拼接: {value!r}")
    return f'"{value}"'


def _too_long(value: str, max_bytes: int) -> bool:
    """VARCHAR 的 max_length 按**字节**算(04 篇坑位 7a): 中文 UTF-8 一个汉字 3 字节。

    所以不能拿 `len(text)` 去比 —— 8192 字节的字段其实只装得下约 2700 个汉字。
    """
    return len(value.encode("utf-8")) > max_bytes


def _upsert_batched(collection: str, data: list[dict]) -> int:
    """分批 upsert: 单次行数有上限(UPSERT_BATCH), 超了按批切开。"""
    client = get_client()
    for start in range(0, len(data), UPSERT_BATCH):
        client.upsert(collection, data=data[start : start + UPSERT_BATCH])
    return len(data)


def upsert_parents(rows: list[ParentChunk]) -> int:
    """父块入库(只写文本与元信息): 返回写入行数。

    `dense` 是占位向量(见文件头事实 1): schema 要求每个向量字段都得有值, 所以每行都写零向量;
    parents 从不做向量检索, 它只按 parent_id 点查。
    """
    data = [
        {
            "parent_id": row.chunk_id,
            "text": row.text,
            "doc_id": row.doc_id,
            "metadata": _metadata(row),
            "dense": list(PARENT_DUMMY_VECTOR),
        }
        for row in rows
    ]
    return _upsert_batched(COLL_PARENTS, data)


def upsert_children(
    rows: list[ChildChunk], vectors: list[list[float]], *, warnings: list[str] | None = None
) -> int:
    """子块入库(带向量): 返回写入行数。payload **不写 sparse** —— 它由 Function 生成(坑位 2)。

    三个必须在这里做的检查:
    1. `len(rows) != len(vectors)` 直接抛 —— 错位写库是最难查的故障(坑位 10);
    2. `text` 超 8192 字节的条目**跳过并记 warning**: 截断会让 BM25 与向量都基于残缺文本,
       属于"静默变差"; 跳过至少能被报告看见, 而且父块里还留着完整文本;
    3. `page_no` 为 None 时写 -1 哨兵(坑位 7c): Milvus 的 INT64 列不接受 None。
    """
    if len(rows) != len(vectors):
        raise ValueError(f"子块数 {len(rows)} 与向量数 {len(vectors)} 不一致, 拒绝写入")

    data: list[dict] = []
    for row, vec in zip(rows, vectors, strict=True):
        if _too_long(row.text, _CHILD_TEXT_MAX):
            if warnings is not None:
                warnings.append(f"{row.chunk_id}: text {len(row.text)} 字超过子块上限, 已跳过")
            continue
        data.append(
            {
                "chunk_id": row.chunk_id,
                "parent_id": row.parent_id,
                "doc_id": row.doc_id,
                "source": row.source,
                "chunk_type": row.chunk_type,
                "page_no": row.page_no if row.page_no is not None else -1,
                "text": row.text,
                "dense": vec,
                "metadata": _metadata(row),
            }
        )
    return _upsert_batched(COLL_CHILDREN, data)


def delete_doc(doc_id: str) -> None:
    """按 doc_id 整删两个 collection(全量重建的入口, 04 篇 §4.5)。

    删除是逻辑删除 + 时间戳过滤: 删完立刻查就不该再命中, 物理空间回收等 Milvus 的 compaction。
    """
    client = get_client()
    flt = f"doc_id == {_quote(doc_id)}"
    client.delete(COLL_CHILDREN, filter=flt)
    client.delete(COLL_PARENTS, filter=flt)
    flush()


def dense_search(vec: list[float], limit: int, *, ef: int | None = None) -> list[Hit]:
    """dense 路: HNSW ANN 检索(`ef` 默认取 RAG2_HNSW_EF, 区间 64~128)。

    `ef` 必须 ≥ limit, 否则候选池比要取的条数还小(05 篇坑位 2);
    `consistency_level="Strong"` 是为了"刚 ingest 完就查也能看见"(坑位 8) —— 单机本地这点
    开销无感, 换来的确定性很值。
    """
    params = {"metric_type": "COSINE", "params": {"ef": ef if ef is not None else _cfg().hnsw_ef}}
    res = get_client().search(
        COLL_CHILDREN,
        data=[vec],
        anns_field="dense",
        limit=limit,
        output_fields=_HIT_FIELDS,
        search_params=params,
        consistency_level="Strong",
    )
    return [_hit(entry) for entry in res[0]]


def sparse_search(query: str, limit: int) -> list[Hit]:
    """sparse 路: 直传**查询原文**, 服务端按 text 字段的 jieba analyzer 分词后算 BM25。

    不要自己做中文分词再拼串传入: 两侧分词口径必须一致, 而 schema 级 analyzer 是唯一权威
    口径(坑位 1)。`metric_type="BM25"` 与建表时保持一致, 显式写明便于读代码。
    """
    res = get_client().search(
        COLL_CHILDREN,
        data=[query],
        anns_field="sparse",
        limit=limit,
        output_fields=_HIT_FIELDS,
        search_params={"metric_type": "BM25"},
        consistency_level="Strong",
    )
    return [_hit(entry) for entry in res[0]]


def get_parents(parent_ids: list[str]) -> dict[str, ParentRow]:
    """父块批量点查(04 篇 §3.2): 一次 `parent_id in [...]` 取回, 按 parent_id 建索引返回。

    返回 dict 而不是 list: 调用方(05 篇)拿到的是一批子块命中, 需要按 parent_id 去重后回查,
    按主键取用比线性查找自然; 查不到的 id 不占键, 调用方用 `get` 拿到 None 即可感知。
    """
    if not parent_ids:
        return {}
    rows = get_client().query(
        COLL_PARENTS,
        filter=f"parent_id in [{', '.join(_quote(i) for i in parent_ids)}]",
        output_fields=_PARENT_FIELDS,
        consistency_level="Strong",
    )
    return {
        row["parent_id"]: ParentRow(
            parent_id=row["parent_id"],
            text=row["text"],
            doc_id=row["doc_id"],
            metadata=row.get("metadata") or {},
        )
        for row in rows
    }


def _hit(entry: dict) -> Hit:
    """把 Milvus 的一条命中摊平成 `Hit`。

    search 的返回形如 `{"id": ..., "distance": ..., "entity": {...}}`: 分数在 `distance`
    (COSINE 与 BM25 都是"越大越好"), 字段值在 `entity` 里, 所以这里按 entity 取并留默认值,
    避免某个 output_field 没回时整批崩掉。
    """
    ent = entry.get("entity") or {}
    return Hit(
        chunk_id=ent.get("chunk_id") or entry.get("id") or "",
        parent_id=ent.get("parent_id", ""),
        text=ent.get("text", ""),
        chunk_type=ent.get("chunk_type", ""),
        score=float(entry.get("distance", 0.0)),
        metadata=ent.get("metadata") or {},
    )
def list_docs()->list[dict]:
    """列出库里的文档: `[{"doc_id", "source", "children", "created_at"}]`, 按 source 排序。

    实现是"把 children 的 doc_id/source/metadata 全查回来在客户端聚合" —— Milvus 没有
    GROUP BY/DISTINCT, 而这是**运维动作**(CLI 的 `list` 子命令), 不是检索热点, 全量拉一次
    可以接受; 真涨到几十万子块再改成维护一张 docs 汇总表(本期不做)。
    `created_at` 取该 doc 所有子块里最新的切块时间(重灌后显示最新入库时间)。
    """
    rows=get_client().query(
        COLL_CHILDREN,
        filter='doc_id != ""',
        output_fields=["doc_id","source","metadata"],
        consistency_level="Strong",
    )
    agg:dict[str,dict]={}
    for row in rows:
        item = agg.setdefault(
            row["doc_id"],
            {
                "doc_id": row["doc_id"],
                "source": row.get("source", ""),
                "children": 0,
                "created_at": None,
            },
        )
        item["children"] += 1
        stamp = (row.get("metadata") or {}).get("created_at")
        if stamp and (item["created_at"] is None or stamp > item["created_at"]):
            item["created_at"] = stamp
    return sorted(agg.values(), key=lambda d: (d["source"], d["doc_id"]))

def purge_stale(source:str,keep_doc_id:str)->list[str]:
    """删掉同一 `source` 下的**旧版本**, 返回被清掉的 doc_id 列表。

    为什么需要: doc_id 是文件内容的 hash, 文件改了 doc_id 就变 —— 于是"重新 ingest 一个改过的
    文件"会在库里留下同一份文件的**新旧两份**(检索会同时命中), 而删除只能按 doc_id 做, 没人记得住
    旧 id。这里按 `source` 找出同源的其他版本一并清掉, 让重灌变成真正的替换。

    为什么不用一条带 JSON 的条件: parents 表里没有 `source` 列(只有 doc_id), 所以先在 children 上
    按 source 查出旧 doc_id, 再用 `doc_id in [...]` 两表各删一次 —— 只用已验证可用的字段。
    注意 children 的 `source` 没有标量索引, 这一步是过滤扫描; 单机规模无感, 涨大后加 INVERTED。
    """
    client = get_client()
    rows = client.query(
        COLL_CHILDREN,
        filter=f"source == {_quote(source)}",
        output_fields=["doc_id"],
        consistency_level="Strong",
    )
    stale = sorted({row["doc_id"] for row in rows} - {keep_doc_id})
    if not stale:
        return []
    ids = ", ".join(_quote(doc_id) for doc_id in stale)
    for name in (COLL_CHILDREN, COLL_PARENTS):
        client.delete(name, filter=f"doc_id in [{ids}]")
    return stale
