"""rag_v01 —— 知识库 RAG 的包级 facade: 检索面 ingest / search / evaluate + 管理面
list_docs / upload / delete_doc(07 篇 §4.1; 管理面 2026-09-23 架构整理 c4 收编, 见 ROADMAP §7)。

调用方(agent 侧、API 路由、CLI)只依赖这几个函数签名与 `contracts.py` 里的类型; 内部模块
(parsers / clean / chunk / embed / store / retrieve)随各分篇自由重构, 不构成对外承诺。
管理面是**唯一实现**:20MB 上限、判重快照、带原名临时落盘、404 判定都在这里,
api/cli 双入口只做状态码与渲染, 不再各写一套。

**无 import 副作用**: 全部子模块在函数体内按需 import, 于是 `import rag_v01` 不会加载
docling / pymilvus / sentence-transformers, 不连 Milvus, 也不建目录(07 篇 §2.3 第三条硬保证)。
`evaluate` 入口随模块 06(ragas)一起加, 此处不留占位。
"""
from __future__ import annotations

from pathlib import Path

from .contracts import ChildHit, EvalReport, IngestReport, RetrievedChunk

__all__ = [
    "ingest",
    "search",
    "evaluate",
    "list_docs",
    "upload",
    "delete_doc",
    "MAX_UPLOAD_BYTES",
    "ChildHit",
    "EvalReport",
    "IngestReport",
    "RetrievedChunk",
]

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 上传上限(管理面唯一出处, api/cli 共用; 原 api 常量下沉于此)


def ingest(paths: list[str | Path]) -> IngestReport:
    """parse → clean → chunk → embed → store 的流水线编排(02/03/04 篇)。"""
    from .pipeline import run_ingest

    return run_ingest(paths)


def search(query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """双路 top-20 召回 + 手写 RRF(k=60)融合取 top_k, 再按 parent_id 回溯父块去重(05 篇)。

    `top_k=None` 走 `RAG2_RETRIEVE_TOP_K`(默认值只存在于 config.py 一处, 与 05 篇落地口径一致)。
    """
    from .retrieve import search as run_search

    return run_search(query, top_k)


def list_docs() -> list[dict]:
    """管理面文档列表: `[{doc_id, filename, chunks, created_at}]`, 按文件名排序。

    新内核没有文档表, 列表由 store 聚合子块现算; `created_at` 来自子块 metadata
    (切块时刻, 重灌后取最新值), 旧数据没有该字段时为 None。
    """
    from .store import list_docs as _store_list

    return [
        {
            "doc_id": row["doc_id"],
            "filename": row["source"],
            "chunks": row["children"],
            "created_at": row.get("created_at") or None,
        }
        for row in sorted(_store_list(), key=lambda r: r["source"])
    ]


def delete_doc(doc_id: str) -> bool:
    """删除文档(按 doc_id 清两个 collection)。不存在返回 False —— 404/文案由双入口自理。"""
    from .store import delete_doc as _store_delete
    from .store import list_docs as _store_list

    if doc_id not in {row["doc_id"] for row in _store_list()}:
        return False
    _store_delete(doc_id)
    return True


def upload(content: bytes, filename: str) -> dict:
    """管理面上传唯一实现:20MB 上限 → 判重快照 → 带原名临时落盘 → ingest。

    返回 `{"ok", "error", "doc_id", "created", "name"}`:
    - ok=False 时 error 是面向用户的失败原因(上限/解析入库失败), 入口直接映射 400/红字;
    - created=False 表示内容寻址(文件字节 sha256 前 16 位)复用了已有文档。
    上限检查最先做 —— 超限早返回, 不落临时文件也不碰内核。
    """
    import hashlib
    import shutil
    import tempfile

    if len(content) > MAX_UPLOAD_BYTES:
        return {
            "ok": False,
            "error": f"文件超过 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 上限",
            "doc_id": "",
            "created": False,
            "name": filename,
        }
    name = filename or "upload"
    docs = list_docs()
    before = {d["doc_id"] for d in docs}
    # 内容寻址早返回:同一份文件重复上传不再 parse/embed/写库(之前只判 created,
    # 仍然会完整重跑 docling, 12 页 PDF 要几十秒)。
    docId = hashlib.sha256(content).hexdigest()[:16]
    existing = next((d for d in docs if d["doc_id"] == docId), None)
    if existing is not None:
        return {
            "ok": True,
            "error": "",
            "doc_id": existing["doc_id"],
            "created": False,
            "name": existing["filename"],
        }

    # 必须**带着原名**落临时文件: source 取的是文件名(pipeline.expand_paths 的口径),
    # 随机临时名会让入库后的文档在列表里变成一串乱码名。
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / name
    try:
        tmp_path.write_bytes(content)
        report = ingest([tmp_path])
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if report.failed:
        return {
            "ok": False,
            "error": next(iter(report.failed.values())),
            "doc_id": "",
            "created": False,
            "name": name,
        }
    doc_id = {d["filename"]: d for d in list_docs()}.get(name, {}).get("doc_id", "")
    created = doc_id not in before
    return {"ok": True, "error": "", "doc_id": doc_id, "created": created, "name": name}


def evaluate(
    testset_path: str | Path | None = None,
    report_dir: str | Path = "eval_reports",
    *,
    samples_path: str | Path | None = None,
    system_label: str = "rag_v01",
    limit: int | None = None,
) -> EvalReport:
    """ragas 四指标评估(06 篇): 逐题检索 + 最简生成 → 打分 → 落盘 json/markdown 报告。

    需要 ragas —— 它装在**独立的评估环境** `eval/` 里(与主项目依赖互斥, 见 06 篇 §2.7), 所以在
    主环境调用会抛一条带跑法指引的 `ImportError`; 导入本包不受影响(子模块按需 import)。
    """
    from .evaluation import run_eval

    return run_eval(
        testset_path,
        report_dir,
        samples_path=samples_path,
        system_label=system_label,
        limit=limit,
    )
