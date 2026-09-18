"""RAG 混合检索:中文分词与 BM25 关键词路(01/02 模块)。

本文件作用:
    tokenize 是入库与查询双端共用的唯一分词函数(词表不一致会崩命中率);
    Bm25Index 是内存 BM25 索引(懒加载 + 脏标记 + 双检锁,loader 注入零 DB 可测);
    rrf_fuse 是 RRF 融合排序(只依赖排名,返回 top_k 的 chunk_id,由 store 层回填字段)。
"""

import math
import threading
from collections.abc import Callable

import jieba
from rank_bm25 import BM25Okapi


class SafeBM25Okapi(BM25Okapi):
    """rank_bm25 0.2.2 的 epsilon 下限在小语料下会变成负值:

    高频词占多数时 average_idf<0,eps=epsilon*average_idf 为负,负 idf 词仍得负分,
    破坏 "score>0 即有命中词" 的过滤语义。覆写为带 +1 平滑的标准 BM25 idf
    (log(1 + (N-df+0.5)/(df+0.5)),恒非负),打分逻辑与 k1/b 参数保持库默认。
    """

    def _calc_idf(self, nd):
        for word, freq in nd.items():
            self.idf[word] = math.log(
                1 + (self.corpus_size - freq + 0.5) / (freq + 0.5)
            )


def tokenize(text: str) -> list[str]:
    """jieba 检索分词:cut_for_search + 过滤空白/单字/纯标点。

    入库构建 BM25 索引与查询必须共用本函数,双端输出天然一致。
    """
    tokens = []
    for tok in jieba.cut_for_search(text):
        tok = tok.strip()
        if len(tok) >= 2 and any(ch.isalnum() for ch in tok):
            tokens.append(tok)
    return tokens


class Bm25Index:
    """
    内存 bm25 索引，懒加载 + 脏标记 + 双检锁。
    loader 注入返回 [(chunk_id, content), ...];缺省空语料(读库 loader 由 03 模块注入)。
    """

    def __init__(self, loader: Callable[[], list[tuple[int, str]]] | None = None) -> None:
        self._loader = loader
        self._bm25: BM25Okapi | None = None
        self._ids: list[int] = []
        self._dirty = True
        self._lock = threading.Lock()

    def mark_dirty(self) -> None:
        """upload/delete 后置脏，下次 search 才重建（懒加载，不及时更新）"""
        self._dirty = True

    def _build(self) -> None:
        raw = self._loader() if self._loader else []
        self._ids = [chunk_id for chunk_id, _content in raw]
        self._bm25 = SafeBM25Okapi([tokenize(content) for _chunk_id, content in raw])

    def _ensure_built(self) -> None:
        with self._lock:  # 双检:并发首次 search 只构建一次
            if self._bm25 is None or self._dirty:
                self._build()
                self._dirty = False

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """BM25 打分 top_k，返回 [(chunk_id, score)];只返回有命中词的(score>0)。"""
        self._ensure_built()
        assert self._bm25 is not None
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [
            (self._ids[i], float(scores[i]))
            for i in ranked[:top_k]
            if scores[i] > 0
        ]


def rrf_fuse(
    vector_hits: list[dict],
    keyword_hits: list[tuple[int, float]],
    k: int = 10,
    top_k: int = 10,
) -> list[tuple[int, float]]:
    """RRF 融合：双路候选按各自排名并集打分(Σ 1/(k+rank))，返回 top_k 的 chunk_id。

    只依赖排名不依赖原始分数(免归一化);vector_hits 需含 chunk_id 键。
    返回 top_k 的 (chunk_id, 融合分) 列表(完整字段由 store 层按 chunk_id 回填)
    """
    fused: dict[int, float] = {}
    for rank, hit in enumerate(vector_hits, start=1):
        fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 1.0 / (k + rank)
    for rank, (chunk_id, _score) in enumerate(keyword_hits, start=1):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)
    return ordered[:top_k]
