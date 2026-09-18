"""文档解析:按扩展名把 txt/md/pdf/docx 统一抽成纯文本。

使用位置:
    - tools/rag/store.py:RAGStore.upload 第一步(parse_document);
    - tests/test_rag.py:解析与空文本报错测试。
"""
from pathlib import Path


def parse_document(path)->str:
    """按扩展名分发解析,返回纯文本;未知格式/空文本给可读中文错误。"""
    suffix = Path(path).suffix.lower()
    if suffix in (".txt", ".md"):
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        from pypdf import PdfReader

        pages = PdfReader(path).pages
        text = "\n".join(page.extract_text() or "" for page in pages)
    elif suffix == ".docx":
        from docx import Document

        text = "\n".join(p.text for p in Document(path).paragraphs)
    else:
        raise ValueError(f"不支持的文档格式:{suffix}(仅支持 txt/md/pdf/docx)")
    if not text.strip():
        raise ValueError(
            f"文档解析后为空:{Path(path).name}"
            "(扫描版 PDF 无文本层,不支持 OCR,请换文本版)"
        )
    return text
