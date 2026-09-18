"""知识库路由(模块 11 T3):GET /knowledge / POST /knowledge/upload / DELETE /knowledge/{doc_id}。

复用 04 的 RAGStore(与 REPL /kb 同一套实现);上传大小上限 20MB(DEV 坑表)。
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from tools.rag.store import RAGStore

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB


@router.get("")
def list_knowledge():
    return {"docs": RAGStore().list_docs()}


@router.post("/upload")
def upload_knowledge(file: UploadFile = File(...)):
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 20MB 上限")
    name = file.filename or "upload"
    suffix = Path(name).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        doc_id, created = RAGStore().upload(Path(tmp_path), name)
    finally:
        os.unlink(tmp_path)
    return {"doc_id": doc_id, "created": created, "name": name}


@router.delete("/{doc_id}")
def delete_knowledge(doc_id: str):
    RAGStore().delete(doc_id)
    return {"ok": True, "doc_id": doc_id}
