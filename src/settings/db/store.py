"""
长期记忆 Postgres Store 工厂(06 模块):跨线程持久,与 checkpointer 并列挂compile。

使用位置:
    - agent/build.py(06 T2 注入 / T3/T5 写入):get_store;
    - cli/repl.py(06 T6):/memory list|delete;
    - tests/test_memory.py:插查删 roundtrip。
"""
from functools import lru_cache

from langgraph.store.postgres import PostgresStore
from psycopg_pool import ConnectionPool

from tools.rag.embed import embed_texts, embedding_dim


@lru_cache
def get_store(database_url:str)->PostgresStore:
    """
    装配 PostgresStore:
        -连接池 + pgvector 索引配置(content 字段嵌入,cosine);
        setup() 幂等建表。
        namespace 约定 ("memory", user_id),条目 value 固定{"content", "source", "created_at"}
    """
    pool=ConnectionPool(
        database_url,
        kwargs={
            "autocommit":True,
        },
        max_size=10,
        open=True,
    )
    store=PostgresStore(
        pool,
        index={
            "dims": embedding_dim(),
            "embed": embed_texts,
            "fields": ["content"],
            "distance_type": "cosine",
            "ann_index_config": {"kind": "flat"},
        },
    )
    store.setup()
    return store
