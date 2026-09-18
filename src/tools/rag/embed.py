"""智谱 embedding 客户端(OpenAI 兼容):配置校验 + 实测维度(供建表 vector(N))。

使用位置:
    - tools/rag/store.py:upload 向量化 / search 查询向量化 / 建表取 embedding_dim;
    - tests/test_rag.py:维度与配置缺失报错测试。
"""

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from settings.config import get_settings

EMBEDDING_ERROR = (
    "Embedding 未配置:请在 .env 填写 "
    "EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL(智谱)"
)


def make_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    if not s.embedding_api_key:
        raise RuntimeError(EMBEDDING_ERROR)
    return OpenAIEmbeddings(
        base_url=s.embedding_base_url,
        api_key=s.embedding_api_key,
        model=s.embedding_model,
    )


@lru_cache(maxsize=1)
def embedding_dim() -> int:
    """实测 embedding 维度(进程内只探测一次),供建表 vector(N) 与一致性断言。"""
    vec = make_embeddings().embed_query("维度探测")
    return len(vec)


ZHIPU_BATCH_LIMIT = 64  # 智谱 embedding 单请求 input 数组上限(超限报错误码 1214)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化;超过智谱 64 条/请求上限时自动分批,结果按原顺序拼接。"""
    if not texts:
        return []
    client = make_embeddings()
    return [
        vec
        for i in range(0, len(texts), ZHIPU_BATCH_LIMIT)
        for vec in client.embed_documents(texts[i:i + ZHIPU_BATCH_LIMIT])
    ]
