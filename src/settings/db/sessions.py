"""会话元数据表:把会话列表查询从 checkpoints 全表聚合里拿出来。

本文件作用:
    sessions 是 checkpoints 的派生索引表(thread_id 主键 + 最近活跃时间),每轮
    对话结束由 run_turn 的 onDone 回调 upsert 一次;列表接口只查这张小表。
    保留 pruneSessions() 做整会话清理,默认 dryRun=True,不自动删数据。

使用位置:
    - settings/db/checkpointer.py:get_checkpointer() 里 ensureSessionsTable();
    - agent/service.py / cli/repl.py / api/routers/chat.py:每轮结束 touchSession;
    - api/routers/chat.py 与 cli/commands/session.py:listSessions / listThreadIds;
    - tests/test_session_meta.py:真库 roundtrip(DB 不可用时 skip)。
"""

from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.postgres import PostgresSaver

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    thread_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checkpoint_id TEXT,
    checkpoint_count   BIGINT NOT NULL DEFAULT 0
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS sessions_updated_idx
    ON sessions (updated_at DESC)
"""

# 老库升级:第一次建表时从 checkpoints 回填,保证 /threads 列表不丢历史会话。
# 无参数查询,psycopg 不解析占位符,LIKE 里的单个 % 可以直写。
_BACKFILL = """
INSERT INTO sessions (
    thread_id, created_at, updated_at,
    last_checkpoint_id, checkpoint_count
)
SELECT thread_id, now(), now(), max(checkpoint_id), count(*)
FROM checkpoints
WHERE thread_id LIKE 'sess-%'
GROUP BY thread_id
ON CONFLICT (thread_id) DO NOTHING
"""

_TOUCH = """
INSERT INTO sessions (
    thread_id, title, created_at, updated_at,
    last_checkpoint_id, checkpoint_count
)
VALUES (
    %s, %s, now(), now(),
    (SELECT max(checkpoint_id) FROM checkpoints WHERE thread_id = %s),
    (SELECT count(*) FROM checkpoints WHERE thread_id = %s)
)
ON CONFLICT (thread_id) DO UPDATE SET
    updated_at = EXCLUDED.updated_at,
    last_checkpoint_id = EXCLUDED.last_checkpoint_id,
    checkpoint_count = EXCLUDED.checkpoint_count,
    title = CASE
        WHEN sessions.title = '' THEN EXCLUDED.title
        ELSE sessions.title
    END
"""


def ensureSessionsTable(saver: PostgresSaver) -> None:
    """幂等建表 + 首次回填;进程内由 get_checkpointer 调用一次。"""
    with saver.conn.connection() as conn:
        conn.execute(_CREATE_TABLE)
        conn.execute(_CREATE_INDEX)
        empty = conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        if empty:
            conn.execute(_BACKFILL)


def touchSession(
        saver: PostgresSaver,
        threadId: str,
        title: str | None = None,
) -> None:
    """一轮结束后更新最近活跃时间与 checkpoint 计数。

    title 只在新会话第一次写入时生效(已有标题不覆盖);调用方传用户本轮
    输入的前 40 字,合成消息(系统通知/用户回答/子智能体结果)传 None。
    """
    cleanTitle = " ".join((title or "").split())[:40]
    with saver.conn.connection() as conn:
        conn.execute(
            _TOUCH,
            (threadId, cleanTitle, threadId, threadId),
        )


def listSessions(
        saver: PostgresSaver,
        limit: int = 50,
) -> list[dict]:
    """按最近活跃倒序返回会话元数据;键名保持旧 list_session_meta 的形状。"""
    with saver.conn.connection() as conn:
        rows = conn.execute(
            "SELECT thread_id, last_checkpoint_id, checkpoint_count"
            " FROM sessions ORDER BY updated_at DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [
        {
            "thread_id": row[0],
            "last_checkpoint": row[1],
            "checkpoints": row[2],
        }
        for row in rows
    ]


def listThreadIds(saver: PostgresSaver) -> list[str]:
    """全部会话 id,按最近活跃倒序(REPL /list_session 与 GET /chat/threads)。"""
    with saver.conn.connection() as conn:
        rows = conn.execute(
            "SELECT thread_id FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [row[0] for row in rows]


def deleteSession(saver: PostgresSaver, threadId: str) -> None:
    """删除会话元数据;checkpointer 三表由 PostgresSaver.delete_thread 负责。"""
    with saver.conn.connection() as conn:
        conn.execute("DELETE FROM sessions WHERE thread_id = %s", (threadId,))


def pruneSessions(
        saver: PostgresSaver,
        *,
        keepDays: int = 30,
        keepCount: int = 50,
        currentThreadId: str | None = None,
        dryRun: bool = True,
) -> list[str]:
    """整会话清理:删除 updated_at 早于 keepDays、且不在最近 keepCount 内的会话。

    只删整会话,绝不按 checkpoint/blob 版本局部裁剪(blob 版本可能被新 checkpoint
    引用,按版本号截断会删坏状态)。默认 dryRun=True,先看目标再决定是否执行。
    """
    cutoff = datetime.now(UTC) - timedelta(days=keepDays)
    with saver.conn.connection() as conn:
        oldRows = conn.execute(
            "SELECT thread_id FROM sessions"
            " WHERE updated_at < %s ORDER BY updated_at ASC",
            (cutoff,),
        ).fetchall()
        keepRows = conn.execute(
            "SELECT thread_id FROM sessions"
            " ORDER BY updated_at DESC LIMIT %s",
            (keepCount,),
        ).fetchall()

    keepIds = {row[0] for row in keepRows}
    targets = [
        row[0]
        for row in oldRows
        if row[0] not in keepIds and row[0] != currentThreadId
    ]
    if dryRun:
        return targets

    for threadId in targets:
        saver.delete_thread(threadId)
        deleteSession(saver, threadId)
    return targets
