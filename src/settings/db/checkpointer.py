"""Postgres 持久化 checkpointer:短期记忆(按 thread_id)+ 会话列表查询。

本文件作用:
    get_checkpointer() 建连接池并装配 PostgresSaver(checkpoint 落库、幂等建表、
    放行三个契约类型的 msgpack 反序列化);list_session_ids() 直查裸 SQL 列出全部
    会话线程,供 REPL /list_session 使用。

使用位置:
    - cli/repl.py:main() 中 get_checkpointer 挂给 build_graph,/list_session 用 list_session_ids;
    - tests/test_session.py:checkpointer 行为测试。
"""
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg_pool import ConnectionPool

# checkpoint 允许反序列化的项目契约类型(不配则每轮告警;strict 模式下直接拒绝)
_ALLOWED_CONTRACTS = [
    ("agent.contracts.route", "Route"),
    ("agent.contracts.task_contract", "TaskContract"),
    ("agent.contracts.summary", "ResultSummary"),
]


@lru_cache
def get_checkpointer(database_url:str)->PostgresSaver:
    """连接池线程安全;autocommit 必须开(checkpoint 迁移含 CREATE INDEXCONCURRENTLY)。"""
    pool = ConnectionPool(
        database_url,
        kwargs={
            "autocommit": True
        },
        max_size=10,
    open=True)
    saver = PostgresSaver(pool)
    saver.setup()          # CREATE TABLE IF NOT EXISTS 语义,幂等,进程内只跑一次
    saver.serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_CONTRACTS)
    return saver


def list_session_ids(saver: PostgresSaver) -> list[str]:
    """列出所有会话线程 id(REPL /list_session 的数据源)。

    直查裸 SQL 而非 saver.list():后者要逐条反序列化 checkpoint,列表场景太重;
    sess- 前缀过滤掉非会话数据,按 id 字母序返回。
    """
    with saver.conn.connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints"
            " WHERE thread_id LIKE 'sess-%' ORDER BY thread_id"
        ).fetchall()
    return [r[0] for r in rows]


def list_session_meta(saver: PostgresSaver, limit: int = 50) -> list[dict]:
    """会话元数据:最近 checkpoint + checkpoint 数(前端会话列表排序用)。

    直查裸 SQL 聚合,不反序列化 checkpoint(同 list_session_ids 的理由);
    checkpoint_id 是 UUIDv6 风格单调递增字符串,max() 即最近一次写入,
    以它做"最近活跃"排序键。

    注意:本查询带参数(LIMIT %s),psycopg 会做占位符解析——SQL 里的字面
    百分号必须写成 '%%'(即 LIKE 'sess-%%'),裸写 'sess-%' 会抛
    ProgrammingError(端点 500;无参查询不走解析,故 list_session_ids 不受影响)。
    """
    with saver.conn.connection() as conn:
        rows = conn.execute(
            "SELECT thread_id, max(checkpoint_id) AS last_cp, count(*) AS n"
            " FROM checkpoints WHERE thread_id LIKE 'sess-%%'"
            " GROUP BY thread_id ORDER BY last_cp DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [
        {"thread_id": r[0], "last_checkpoint": r[1], "checkpoints": r[2]}
        for r in rows
    ]


