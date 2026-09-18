"""记忆路由(模块 11 T3):GET /memory / DELETE /memory/{key}。

复用 06 的 PostgresStore(namespace ("memory", "default"),与 REPL /memory 同语义)。
"""
from fastapi import APIRouter

from settings.config import get_settings
from settings.db.store import get_store

router = APIRouter(prefix="/memory", tags=["memory"])


def _store():
    return get_store(get_settings().database_url)


@router.get("")
def list_memory():
    items = _store().search(("memory", "default"), query=None, limit=100)
    items = sorted(items, key=lambda it: it.value.get("created_at", ""), reverse=True)
    return {
        "items": [
            {
                "key": it.key,
                "content": it.value.get("content", ""),
                "source": it.value.get("source", ""),
                "created_at": it.value.get("created_at", ""),
            }
            for it in items
        ]
    }


@router.delete("/{key}")
def delete_memory(key: str):
    _store().delete(("memory", "default"), key)
    return {"ok": True, "key": key}
