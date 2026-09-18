"""RAG 知识库持久层:documents/chunks 双表 + pgvector 向量检索(04 模块)。

本文件作用:
    RAGStore 封装知识库全生命周期——幂等建表(含维度一致性校验与内容级防重
    唯一索引)、上传(解析->切块->判重->向量化->入库)、向量检索(余弦距离
    top_k)、文档列表与删除;SQL 全部手写 psycopg,不走 ORM。

使用位置:
    - tools/rag/kb_search.py:_default_store() 惰性单例,检索工具的数据源;
    - tools/rag/cli.py:命令行 upload/list/delete/search;
    - cli/repl.py:cmd_kb(/kb 命令)。
"""
import hashlib
import uuid
from datetime import UTC, datetime

import psycopg

from settings.config import get_settings
from settings.db.base import ensure_vector_ext, get_conn
from tools.rag.bm25 import Bm25Index, rrf_fuse
from tools.rag.embed import embed_texts, embedding_dim
from tools.rag.parse import parse_document
from tools.rag.split import split_text

CANDIDATE_M = 5  # 双路候选池宽度(检索候选 = top_k * CANDIDATE_M,RRF 融合用)


def _to_pg_vector(vec: list[float]) -> str:
    """向量 -> pgvector 字符串字面量 '[0.1,0.2,...]'(SQL 中显式 ::vector cast)。"""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _content_hash(text: str) -> str:
    """解析后文本的规范化 SHA-256:统一换行 + 去首尾空白(内容级防重的判定依据)。

    不做空白压缩/模糊去重:同一份文件重复上传必得同哈希;改动几个字即视为新文档。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

class RAGStore:
    """知识库存取门面:构造即 ensure_vector_ext + 幂等建表,后续操作按需连库。"""

    def __init__(self,database_url:str|None=None):
        """database_url 缺省取 get_settings();建表与 embedding 维度断言在这里完成。"""
        self.database_url = database_url or get_settings().database_url
        ensure_vector_ext(self.database_url)
        self.bm25 = Bm25Index(loader=self._load_bm25_corpus)
        self._ensure_table()

    #----------建表----------#
    def _ensure_table(self)->None:
        """幂等建表，已存在的chunks表维度与实测embedding维度一致时抛错。

        documents 含 content_hash(解析后规范化文本的 SHA-256),配
        (user_id, content_hash) 唯一索引做内容级防重;存量旧数据不回填,
        旧文档(content_hash 为 NULL)不参与判重,仅对新上传生效。
        """
        dim=embedding_dim()
        with get_conn(self.database_url) as conn:
            exists=conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name='chunks'"
            ).fetchone()
            if exists:
                row=conn.execute(
                    "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a"
                    " WHERE a.attrelid = 'chunks'::regclass AND a.attname = 'embedding'"
                ).fetchone()
                # row[0] 形如 'vector(1024)',解析括号内维度
                existing = int(row[0][row[0].find("(") + 1: -1])
                if existing != dim:
                    raise RuntimeError(
                        f"向量维度不一致:chunks 表为 vector({existing}),"
                        f"当前 embedding 实测 {dim} 维。请删除 chunks/documents表后重建。"
                    )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS documents ("
                " id TEXT PRIMARY KEY,"
                " user_id TEXT NOT NULL DEFAULT 'local',"
                " filename TEXT NOT NULL,"
                " created_at TIMESTAMPTZ NOT NULL,"
                " content_hash TEXT)"
            )
            # 旧表补列(幂等);存量行不回填(用户决议 2026-09-04)
            conn.execute(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS chunks ("
                " id BIGSERIAL PRIMARY KEY,"
                " doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,"
                " seq INT NOT NULL,"
                " content TEXT NOT NULL,"
                f" embedding vector({dim}))"
            )
            # 唯一索引做竞态兜底:应用层查重后并发插入仍不会产生重复内容;
            # 旧行 content_hash 为 NULL,PG 唯一索引允许多个 NULL,不冲突
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_documents_user_hash"
                " ON documents (user_id, content_hash)"
            )
            conn.commit()

    # ---------- BM25 关键词路 ----------
    def _load_bm25_corpus(self) -> list[tuple[int, str]]:
        """BM25 懒重建数据源:chunks 全量 (id, content)。"""
        with get_conn(self.database_url) as conn:
            rows = conn.execute("SELECT id, content FROM chunks").fetchall()
        return [(r[0], r[1]) for r in rows]

    # ---------- 写入 ----------
    def upload(self, source, filename: str) -> tuple[str, bool]:
        """解析 -> 切块 -> 内容判重 -> 向量化 -> 入库;返回 (doc_id, created)。

        内容判重:解析后规范化文本的 SHA-256(_content_hash),命中则复用已有文档,
        不重复切块/向量化;created=False 表示内容重复(详见 docs/troubleshooting/04-rag.md)。
        """
        text = parse_document(source)
        chunks = split_text(text)
        if not chunks:
            raise ValueError(f"切块后无内容:{filename}")
        content_hash = _content_hash(text)
        with get_conn(self.database_url) as conn:
            row = conn.execute(
                "SELECT id FROM documents WHERE user_id = 'local' AND content_hash = %s",
                (content_hash,),
            ).fetchone()
            if row:
                return row[0], False
            vectors = embed_texts(chunks)
            doc_id = uuid.uuid4().hex
            try:
                conn.execute(
                    "INSERT INTO documents (id, user_id, filename, created_at, content_hash)"
                    " VALUES (%s, 'local', %s, %s, %s)",
                    (doc_id, filename, datetime.now(UTC), content_hash),
                )
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO chunks (doc_id, seq, content, embedding)"
                        " VALUES (%s, %s, %s, %s::vector)",
                        [
                            (doc_id, i, c, _to_pg_vector(v))
                            for i, (c, v) in enumerate(
                                zip(chunks, vectors, strict=True)
                            )
                        ],
                    )
                conn.commit()
            except psycopg.errors.UniqueViolation:
                # 极端竞态:查重与插入之间另一请求已写入同哈希 → 复用已有文档
                conn.rollback()
                row = conn.execute(
                    "SELECT id FROM documents WHERE user_id = 'local' AND content_hash = %s",
                    (content_hash,),
                ).fetchone()
                if row:
                    return row[0], False
                raise
        self.bm25.mark_dirty()
        return doc_id, True

    # ---------- 检索 / 管理 ----------
    def _search_vector(self, query: str, top_k: int) -> list[dict]:
        """向量路:embedding 查询词 -> 余弦距离升序取 top_k;返回含 chunk_id。

        抽取自原 search(score 仍为 cosine 距离,越小越近;融合时不使用原始分数)。
        """
        qvec = embed_texts([query])[0]
        qstr = _to_pg_vector(qvec)
        with get_conn(self.database_url) as conn:
            rows = conn.execute(
                "SELECT c.id, c.doc_id, d.filename, c.seq, c.content,"
                " (c.embedding <=> %s::vector) AS score"
                " FROM chunks c JOIN documents d ON d.id = c.doc_id"
                " ORDER BY c.embedding <=> %s::vector LIMIT %s",
                (qstr, qstr, top_k),
            ).fetchall()
        return [
            {
                "chunk_id": r[0],
                "doc_id": r[1],
                "filename": r[2],
                "seq": r[3],
                "content": r[4],
                "score": float(r[5]),
            }
            for r in rows
        ]

    def _fetch_chunks(self, chunk_ids: list[int]) -> dict[int, dict]:
        """按 chunk_id 回填完整字段(关键词路独占命中补齐;score 由调用方覆盖)。"""
        with get_conn(self.database_url) as conn:
            rows = conn.execute(
                "SELECT c.id, c.doc_id, d.filename, c.seq, c.content"
                " FROM chunks c JOIN documents d ON d.id = c.doc_id"
                " WHERE c.id = ANY(%s)",
                (chunk_ids,),
            ).fetchall()
        return {
            r[0]: {
                "chunk_id": r[0],
                "doc_id": r[1],
                "filename": r[2],
                "seq": r[3],
                "content": r[4],
            }
            for r in rows
        }

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """双路召回 + RRF 融合;score 为融合分,越大越相关(语义翻转,ROADMAP §7 登记)。

        向量路与关键词路各取 top_k*CANDIDATE_M 候选,rrf_fuse 按排名并集取 top_k;
        关键词路独占命中的字段经 _fetch_chunks 回填。
        """
        m = top_k * CANDIDATE_M
        vector_hits = self._search_vector(query, m)
        keyword_hits = self.bm25.search(query, m)
        fused = rrf_fuse(vector_hits, keyword_hits, top_k=top_k)
        by_id = {h["chunk_id"]: h for h in vector_hits}
        missing = [cid for cid, _score in fused if cid not in by_id]
        if missing:
            by_id.update(self._fetch_chunks(missing))
        return [{**by_id[cid], "score": score} for cid, score in fused]
    def delete(self, doc_id: str)->None:
        """删除文档(chunks 经 FK CASCADE 一并删除);不存在时报错。"""
        with get_conn(self.database_url) as conn:
            cur = conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            if cur.rowcount == 0:
                raise ValueError(f"文档不存在:{doc_id}")
            conn.commit()
        self.bm25.mark_dirty()

    def list_docs(self) -> list[dict]:
        """文档列表(含 chunk 数)。"""
        with get_conn(self.database_url) as conn:
            rows = conn.execute(
                "SELECT d.id, d.filename, d.created_at,"
                " (SELECT count(*) FROM chunks c WHERE c.doc_id = d.id)"
                " FROM documents d ORDER BY d.created_at"
            ).fetchall()
        return [
            {"doc_id": r[0], "filename": r[1], "created_at": r[2], "chunks": r[3]}
            for r in rows
        ]

