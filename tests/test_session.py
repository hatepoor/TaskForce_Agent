"""会话列表单测:list_session_ids(依赖 PG checkpointer,不可用自动 skip)。"""

import uuid

import pytest
from langchain_core.messages import AIMessage

from agent.build import build_graph
from agent.contracts import Route
from settings.config import get_settings
from settings.db.checkpointer import get_checkpointer, list_session_ids, list_session_meta


@pytest.fixture(scope="module")
def saver():
    try:
        return get_checkpointer(get_settings().database_url)
    except Exception as e:  # DB 未起
        pytest.skip(f"checkpointer 依赖不可用:{e}")


class _FakeLLM:
    """奇数次调用返回 Route(answer),偶数次返回最终文本(answer 节点)。"""

    def __init__(self):
        self._n = 0

    def with_structured_output(self, schema, **kwargs):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self._n += 1
        if self._n % 2 == 1:
            return Route(next="answer")
        return AIMessage("ok")


def test_list_session_ids_contains_written_thread(saver):
    """真实写一轮会话后,list_session_ids 能列出该 thread;结束删除不残留。"""
    tid = f"sess-{uuid.uuid4().hex[:8]}"
    graph = build_graph(llm=_FakeLLM(), checkpointer=saver)
    config = {"recursion_limit": 25, "configurable": {"thread_id": tid}}
    try:
        list(graph.stream({"messages": [("user", "会话列表测试")]}, config,
                          stream_mode="updates"))
        ids = list_session_ids(saver)
        assert tid in ids
        # 全部是 sess- 前缀(过滤非会话数据)
        assert all(i.startswith("sess-") for i in ids)
    finally:
        saver.delete_thread(tid)  # 清理,不污染用户的 /list_session 输出


def test_list_session_ids_sorted(saver):
    """返回按 thread_id 字母序(便于 /list_session 稳定展示)。"""
    ids = list_session_ids(saver)
    assert ids == sorted(ids)


def test_list_session_meta_runs_against_real_db(saver):
    """真库回归:带参聚合 SQL 必须通过 psycopg 占位符解析。

    历史 bug:LIKE 'sess-%' 未转义为 'sess-%%',带参查询抛 ProgrammingError
    (端点 500);裸文本断言(sql 形状测试)拦不住,必须真执行一次。
    """
    rows = list_session_meta(saver, limit=5)
    assert isinstance(rows, list)
    for r in rows:
        assert set(r) == {"thread_id", "last_checkpoint", "checkpoints"}
        assert r["thread_id"].startswith("sess-")
