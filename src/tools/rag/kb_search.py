"""kb_search:知识库向量检索工具(R-T1,ADR-0010)——去重与截断的确定性保障内聚在工具内。

使用位置:
    - agent/subagents/retriever.py:装配进 ReAct 子图的工具集,是子智能体唯一的知识库入口;
    - tests/test_kb_search.py:工具行为测试(FakeStore 注入)。
"""

import json
from functools import lru_cache

from langchain_core.tools import tool

from tools.rag.store import RAGStore

SNIPPET_LIMIT = 500  # 单条命中内容上限(字符),防单次工具结果撑爆子图上下文


@lru_cache(maxsize=1)
def _default_store() -> RAGStore:
    """惰性单例:首次检索才连库;测试用 monkeypatch 替换注入 FakeStore。"""
    return RAGStore()


@tool
def kb_search(query: str, top_k: int = 5) -> str:
    """在知识库中检索用户上传的文档,返回最相关的片段列表(JSON 数组,无命中时为 [])。

    Args:
        query: 检索查询。用名词短语,一次一条;复合问题拆成多条分别检索。
        top_k: 返回命中条数上限。
    """
    top_k = min(max(int(top_k or 5), 1), 10)  # 钳制:防模型给异常值拖垮检索
    hits = _default_store().search(query, top_k=top_k)
    return json.dumps(
        [
            {
                "doc_id": h["doc_id"],
                "filename": h["filename"],
                "seq": h["seq"],
                "content": h["content"][:SNIPPET_LIMIT],
                "score": h["score"],
            }
            for h in hits
        ],
        ensure_ascii=False,
    )
