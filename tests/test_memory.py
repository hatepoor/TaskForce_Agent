"""模块 06 T1 单测:get_store 长期记忆工厂的插查删 roundtrip + namespace 隔离。

需 DB + 智谱 embedding 配置;依赖不可用时自动 skip(同 test_rag 模式)。
隔离 schema 方案同 test_rag(2026-09-04 R 模块 #4 踩坑后确立):测试建表/写入
不污染 public 下的真实长期记忆。

注意:PostgresStore 向量检索无相似度阈值(返回 top-k 即使低相关),"无命中"判定
交给调用方,故本文件不设"无关 query 返回空"这类脆弱断言。
"""

import uuid as _uuid

import pytest

from settings.config import get_settings
from settings.db.base import get_conn

_USER = "pytest_user"


def _store_deps_ready() -> bool:
    s = get_settings()
    return bool(s.embedding_api_key)


@pytest.fixture(scope="module")
def store():
    """隔离 schema 中的 get_store:测试建表/写入不污染 public 下的真实长期记忆。"""
    if not _store_deps_ready():
        pytest.skip("长期记忆依赖不可用(DB/EMBEDDING 未配置)")
    from settings.db.store import get_store

    url = get_settings().database_url
    schema = f"test_mem_{_uuid.uuid4().hex[:8]}"
    sep = "&" if "?" in url else "?"
    scoped = f"{url}{sep}options=-csearch_path%3D{schema}%2Cpublic"
    try:
        with get_conn(url) as conn:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.commit()
        s = get_store(scoped)
    except Exception as e:  # DB 未起 / embedding 未配置
        pytest.skip(f"长期记忆依赖不可用:{e}")
    yield s
    with get_conn(url) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        conn.commit()


def _mem(content: str, source: str = "explicit") -> dict:
    """记忆条目 value 固定形状:content/source/created_at。"""
    return {
        "content": content,
        "source": source,
        "created_at": "2026-09-04T00:00:00+00:00",
    }


def _put(store, content: str, user: str = _USER) -> str:
    key = f"k_{_uuid.uuid4().hex[:6]}"
    store.put(("memory", user), key, _mem(content))
    return key


def _search(store, query: str, user: str = _USER, limit: int = 5):
    return store.search(("memory", user), query=query, limit=limit)


def test_put_search_roundtrip(store):
    """写入一条记忆,用相关内容 query 检索,能取回且 value 形状完整。"""
    content = "用户偏好中文回复"
    _put(store, content)
    hits = _search(store, "用户喜欢用什么语言回复")
    assert hits
    assert hits[0].value["content"] == content
    assert hits[0].value["source"] == "explicit"
    assert "created_at" in hits[0].value


def test_search_ranks_relevant_first(store):
    """两条主题不同记忆,query 主题甲应让甲条排在首位(相关性排序生效)。"""
    _put(store, "用户偏好中文回复")
    _put(store, "用户每天晨跑五公里")
    hits = _search(store, "用户平时跑步锻炼吗")
    assert hits and "晨跑" in hits[0].value["content"]


def test_delete_removes_item(store):
    """delete 后同名 key 检索不再返回该条。"""
    content = "将被删除的临时记忆"
    key = _put(store, content)
    store.delete(("memory", _USER), key)
    assert all(h.value["content"] != content for h in _search(store, content))


def test_namespace_isolation(store):
    """不同 user_id 的 namespace 互不可见:("memory", user_a) 搜不到 user_b 的条目。"""
    _put(store, "甲用户的独家记忆", user="user_a")
    assert _search(store, "甲用户的独家记忆", user="user_b") == []
    assert _search(store, "甲用户的独家记忆", user="user_a")


# ---------- T6:/memory 命令的存储语义(list 全量倒序 / delete) ----------


def test_search_query_none_lists_all(store):
    """search(query=None) 列出 namespace 全部条目(REPL /memory list 数据源)。"""
    _put(store, "第一条记忆")
    _put(store, "第二条记忆")
    items = store.search(("memory", _USER), query=None, limit=100)
    assert len(items) >= 2
    contents = {it.value["content"] for it in items}
    assert "第一条记忆" in contents and "第二条记忆" in contents


def test_delete_then_list_excludes(store):
    """delete 后 list 不再含该条(/memory delete 的存储语义)。"""
    key = _put(store, "将被删除的条目")
    store.delete(("memory", _USER), key)
    items = store.search(("memory", _USER), query=None, limit=100)
    assert all(it.key != key for it in items)
