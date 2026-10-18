"""sessions 元数据表 roundtrip(依赖 PG,不可用自动 skip)。"""

import uuid

import pytest

from settings.config import get_settings
from settings.db.checkpointer import get_checkpointer
from settings.db.sessions import (
    deleteSession,
    ensureSessionsTable,
    listSessions,
    listThreadIds,
    pruneSessions,
    touchSession,
)


@pytest.fixture(scope="module")
def saver():
    try:
        return get_checkpointer(get_settings().database_url)
    except Exception as e:  # DB 未起
        pytest.skip(f"checkpointer 依赖不可用:{e}")


def _tid() -> str:
    return f"sess-test-{uuid.uuid4().hex[:8]}"


def test_ensure_table_idempotent(saver):
    """建表与回填必须可重复执行。"""
    ensureSessionsTable(saver)
    ensureSessionsTable(saver)


def test_touch_list_delete_roundtrip(saver):
    """touch -> list -> delete:三个入口都对同一 thread_id 生效。"""
    tid = _tid()
    try:
        touchSession(saver, tid, title="测试会话标题")

        with saver.conn.connection() as conn:
            row = conn.execute(
                "SELECT title, checkpoint_count FROM sessions WHERE thread_id = %s",
                (tid,),
            ).fetchone()
        assert row == ("测试会话标题", 0)

        sessions = listSessions(saver, limit=500)
        item = next(r for r in sessions if r["thread_id"] == tid)
        assert set(item) == {"thread_id", "last_checkpoint", "checkpoints"}
        assert item["checkpoints"] == 0
        assert tid in listThreadIds(saver)

        # 已有标题不被后续轮次覆盖
        touchSession(saver, tid, title="另一个标题")
        with saver.conn.connection() as conn:
            title = conn.execute(
                "SELECT title FROM sessions WHERE thread_id = %s",
                (tid,),
            ).fetchone()[0]
        assert title == "测试会话标题"
    finally:
        deleteSession(saver, tid)
        saver.delete_thread(tid)

    assert tid not in listThreadIds(saver)


def test_prune_sessions_dry_run_does_not_delete(saver):
    """dryRun 只返回目标,不能删任何会话。"""
    tid = _tid()
    try:
        touchSession(saver, tid)
        with saver.conn.connection() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = now() - interval '60 days'"
                " WHERE thread_id = %s",
                (tid,),
            )

        targets = pruneSessions(
            saver,
            keepDays=30,
            keepCount=0,
            dryRun=True,
        )
        assert tid in targets

        with saver.conn.connection() as conn:
            still = conn.execute(
                "SELECT count(*) FROM sessions WHERE thread_id = %s",
                (tid,),
            ).fetchone()[0]
        assert still == 1
    finally:
        deleteSession(saver, tid)
        saver.delete_thread(tid)
