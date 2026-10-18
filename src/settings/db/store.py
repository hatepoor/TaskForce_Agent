"""
长期记忆 Postgres Store 工厂(06 模块):跨线程持久,与 checkpointer 并列挂compile。

使用位置:
    - agent/build.py(06 T2 注入 / T3/T5 写入):get_store;
    - cli/repl.py(06 T6):/memory list|delete;
    - tests/test_memory.py:插查删 roundtrip。

embed 可选注入(2026-09-23 架构整理 c2,见 ROADMAP §7):缺省用 settings.embeddings
的真实客户端;测试传入假向量化函数即可免真实 key,向量维度随注入函数实测。
"""
from collections.abc import Callable
from functools import lru_cache

from langgraph.store.postgres import PostgresStore
from psycopg_pool import ConnectionPool

from settings.embeddings import embed_texts, embedding_dim

EmbedFn = Callable[[list[str]], list[list[float]]]


@lru_cache
def get_store(database_url: str, embed: EmbedFn | None = None) -> PostgresStore:
    """
    装配 PostgresStore:
        -连接池 + pgvector 索引配置(content 字段嵌入,cosine);
        setup() 幂等建表。
        namespace 约定 ("memory", user_id),条目 value 固定{"content", "source", "created_at"}
        -embed:可选向量化函数(测试假件注入),缺省 settings 版真实客户端。
    """
    pool=ConnectionPool(
        database_url,
        kwargs={
            "autocommit":True,
        },
        min_size=2,
        max_size=8,
        timeout=10,
        max_idle=300,
        max_lifetime=3600,
        open=True,
    )
    if embed is None:
        embed_fn, dims = embed_texts, embedding_dim()
    else:
        embed_fn = embed
        dims = len(embed_fn(["维度探测"])[0])
    store=PostgresStore(
        pool,
        index={
            "dims": dims,
            "embed": embed_fn,
            "fields": ["content"],
            "distance_type": "cosine",
            "ann_index_config": {"kind": "flat"},
        },
    )
    store.setup()
    return store
