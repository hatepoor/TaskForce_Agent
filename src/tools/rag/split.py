"""切块:RecursiveCharacterTextSplitter(500/100)封装。

使用位置:
    - tools/rag/store.py:RAGStore.upload 第二步(解析后切块再向量化入库)。
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(text: str) -> list[str]:
    """按 chunk_size=500 / overlap=100 切块,返回非空块列表。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )
    return [
        c
        for c in splitter.split_text(text) if c.strip()
    ]
