"""psycopg 连接辅助 + pgvector 扩展幂等创建(00 模块契约,其他模块禁止复制定义)。

使用位置:
    - settings/db/checkpointer.py:经 ConnectionPool 自行建池,不直接用本文件;
    - tools/rag/store.py:RAGStore 建表/上传/检索全走 get_conn。
"""

import psycopg


def get_conn(database_url: str):
    """返回 psycopg 连接上下文管理器(退出自动提交/回滚并关闭)。"""
    return psycopg.connect(database_url)


def ensure_vector_ext(database_url: str) -> None:
    """幂等创建 pgvector 扩展(重复执行不报错)。"""
    with get_conn(database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
