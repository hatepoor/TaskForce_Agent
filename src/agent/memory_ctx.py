"""主智能体共享上下文:agents.md 权威背景(固定 system)+ 长期记忆工具(memory-as-tool, ADR-0011)。

架构评审(ARCH-REVIEW / ADR-0011)落地:
- agents.md:构建期读入并 lru_cache 缓存(字节级稳定,进固定 system),不再每轮读盘;
- 长期记忆:封装为 memory_search / store_memory 两个 @tool(同 tools/rag/kb_search 模式),
  由主智能体(answer 侧)判断需要时按需调用,结果以 ToolMessage 进消息流;
  废除"每轮无条件向量检索 top-5 注入 system"的旧机制(缓存破坏 + 上下文漂移 + 无法按需检索)。

使用位置:
    - agent/supervisor.py:route_node 装配固定 system(仅 agents_md);
    - agent/answer.py:answer_node 装配固定 system + bind_tools 记忆工具循环;
    - tests/test_memory_inject.py:工具行为与 answer 循环测试(monkeypatch _default_store)。
"""
import json
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

from settings.config import get_settings
from settings.db.store import get_store

USER_ID = "default"  # 单用户工作台:记忆 namespace ("memory", USER_ID)


@lru_cache(maxsize=1)
def load_agents_md(path: str = "agents.md") -> str:
    """读 agents.md 全文(会话级权威背景,进固定 system);缺失给占位。构建期读入并缓存。"""
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return "(未提供 agents.md,按默认行为运行)"


@lru_cache(maxsize=1)
def _default_store():
    """惰性单例:首次调用才连库;测试用 monkeypatch 替换注入 FakeStore(同 kb_search)。"""
    return get_store(get_settings().database_url)


@tool
def memory_search(query: str, top_k: int = 5) -> str:
    """在长期记忆中检索用户本人信息(身份/偏好/习惯/过往决定),返回最相关条目列表。

    回答"关于用户自己"的问题前应调用;结果为空说明尚无记录。
    Args:
        query: 检索查询。用名词短语描述想找的用户信息,一次一条。
        top_k: 返回命中条数上限。
    """
    top_k = min(max(int(top_k or 5), 1), 10)
    try:
        hits = _default_store().search(("memory", USER_ID), query=query, limit=top_k)
    except Exception as e:
        return f"记忆检索不可用:{e}"
    if not hits:
        return "[]"
    return json.dumps(
        [
            {
                "content": h.value["content"],
                "source": h.value.get("source", "explicit"),
                "created_at": h.value.get("created_at", ""),
            }
            for h in hits
        ],
        ensure_ascii=False,
    )


@tool
def store_memory(content: str, source: str = "explicit") -> str:
    """把用户明确告知的一条事实/偏好写入长期记忆。

    仅当用户显式要求记住(如"记住我偏好X")时调用;content 必须压缩为一句话原子事实。
    Args:
        content: 一句话原子事实(如"用户偏好中文回复")。
        source: 来源标记,explicit(用户显式告知)或 confirmed(用户确认)。
    """
    try:
        _default_store().put(
            ("memory", USER_ID),
            f"m_{uuid.uuid4().hex[:8]}",
            {
                "content": content,
                "source": source,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
    except Exception as e:
        return f"记忆写入失败:{e}"
    return f"已记住:{content}"


MEMORY_TOOLS = [memory_search, store_memory]
