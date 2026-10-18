"""ingest.py —— 入库流水线编排: parse → clean → chunk → embed → store(02/03/04 篇的合流点)。

**逐文件处理是硬约束**(07 篇 §3.1): `ParsedDoc` 不留磁盘痕迹, 只在内存里传递, 所以必须
`for 文件: parse → clean → chunk → embed → upsert → 丢弃` —— 峰值内存 = 最大**单个**文件的解析
产物 + 它的子块向量, 与语料总量无关。禁止"先把所有文件 parse 完再统一入库"。

本文件只 import 同级模块, 不 import 项目其它包, 整目录可搬走。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from . import embed, store
from .chunk import split
from .clean import clean_document
from .config import Config, load_config
from .contracts import ChildChunk, IngestReport, ParentChunk
from .parsers import parse_document


def run_ingest(paths: list[str | Path], cfg: Config | None = None) -> IngestReport:
    """把一批文件/目录灌进库里, 返回汇总报告。

    单文件的失败(损坏文件、不支持的格式、入库报错)记进 `failed` 并继续处理下一个 —— 一批里有一个
    坏文件不该让整批失败(02 篇把 ParseError 统一成人话异常, 就是为了这里能原样记进报告)。
    """
    cfg = cfg or load_config()
    store.ensure_collections()  # 幂等: 表不在则建; 维度 / Function / analyzer 不对则在此时报错
    ok: list[str] = []
    failed: dict[str, str] = {}
    warnings: dict[str, list[str]] = {}
    total_parents = total_children = 0

    for path, source in expand_paths(paths):
        try:
            parents, children, notes = _ingest_one(path, source, cfg)
        except Exception as exc:  # 单文件隔离: 报告里只留可读原因, 不让堆栈打断整批
            failed[source] = f"{type(exc).__name__}: {exc}"
            continue
        total_parents += len(parents)
        total_children += len(children)
        ok.append(source)
        if notes:
            warnings[source] = notes

    flushStarted = time.perf_counter()
    store.flush()  # 一整批写完才 flush 一次(04 篇 §4.5: 每条一调会反复封 segment)
    print(f"[ingest] flush={time.perf_counter() - flushStarted:.2f}s", file=sys.stderr)
    return IngestReport(
        ok_sources=ok,
        failed=failed,
        total_parents=total_parents,
        total_children=total_children,
        warnings=warnings,
    )


def expand_paths(paths: list[str | Path]) -> list[tuple[Path, str]]:
    """展开输入 → `[(文件, source)]`, 排序去重。

    - 目录**递归**展开, 跳过隐藏文件与隐藏目录(`.git` / `.DS_Store` / 编辑器临时文件);
    - `source` = 相对"语料根"的 POSIX 路径: 传目录时根是该目录, 传单文件时根是父目录(于是单文件
        入库的 source 就是文件名, 与 `parse_document` 的默认口径一致);
    - 按 resolved 路径去重 + 排序: 同一批输入跑两次, 入库顺序与报告顺序完全一致(可复现)。
    """
    jobs: dict[Path, tuple[Path, str]] = {}
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                rel = f.relative_to(p)
                if f.is_file() and not _is_hidden(rel):
                    jobs.setdefault(f.resolve(), (f, rel.as_posix()))
        else:
            # 文件不存在也照收: 交给 parse_document 报"文件不存在或不是文件", 错误文案只此一处
            jobs.setdefault(p.resolve(), (p, p.name))
    return [jobs[key] for key in sorted(jobs)]


def _is_hidden(rel: Path) -> bool:
    """任一层目录/文件名以点开头就算隐藏。"""
    return any(part.startswith(".") for part in rel.parts)


def _ingest_one(
    path: Path, source: str, cfg: Config
) -> tuple[list[ParentChunk], list[ChildChunk], list[str]]:
    """单文件全流程: 返回 (父块, 子块, 该文件的警告)。"""
    started = time.perf_counter()
    doc = parse_document(path, cfg, source=source)
    parsedAt = time.perf_counter()
    doc, stats = clean_document(doc, cfg)
    cleanedAt = time.perf_counter()
    parents, children = split(doc, cfg)
    chunkedAt = time.perf_counter()

    notes = list(doc.meta.get("warnings", []))  # 解析 + 清洗阶段的警告(clean 已并进 meta)
    notes.append(f"清洗统计: {stats}")  # 统计也进报告, 这是 02 篇定的口径
    vectors = embed.embed_chunks(children, warnings=notes)  # 超长跳过等继续往同一个口里记
    embeddedAt = time.perf_counter()
    stale = store.purge_stale(source, keep_doc_id=doc.doc_id)  # 文件改过 → 清掉同源旧版本
    if stale:
        notes.append(f"清掉同源旧版本 {stale}")
    store.upsert_parents(parents)
    store.upsert_children(children, vectors, warnings=notes)
    storedAt = time.perf_counter()
    print(
        f"[ingest] {source} "
        f"parse={parsedAt - started:.2f}s "
        f"clean={cleanedAt - parsedAt:.2f}s "
        f"chunk={chunkedAt - cleanedAt:.2f}s "
        f"embed={embeddedAt - chunkedAt:.2f}s "
        f"store={storedAt - embeddedAt:.2f}s "
        f"docling={doc.meta.get('elapsed_s')}s "
        f"parents={len(parents)} children={len(children)}",
        file=sys.stderr,
    )
    return parents, children, notes
