"""知识库路由(模块 11 T3):GET /knowledge / POST /knowledge/upload / DELETE /knowledge/{doc_id}。

**2026-09-22 起换内核**(里程碑 B 步骤 6):走 `rag_v01`(Milvus + 双路 RRF)—— 与 REPL `/kb`、
检索子智能体读的是**同一份**数据,不会再出现"路由列出 A 库、检索答 B 库"。
**2026-09-23 架构整理 c4**(ROADMAP §7):判重 / 20MB 上限 / 带原名临时落盘等管理语义收编
`rag_v01.upload/list_docs/delete_doc` facade,本路由只做 HTTP 状态码与响应形状的纯渲染;
CLI `/kb` 调同一 facade(CLI 上传从此同受 20MB 上限)。

**与旧契约的两处差异**(docs/60-前端文档/API-CONTRACT/02-端点-知识库.md §2.3):
1. `doc_id` 是**内容寻址**的(文件字节的 sha256 前 16 位),重复上传必然同 id →
   `created: false` 据此判定。
2. 新内核没有"上传时间"概念, `created_at` 恒为 `null`;前端 `fmtDateTime` 对 null 返回空串。
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

import rag_v01

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
def list_knowledge():
    return {"docs": rag_v01.list_docs()}


@router.post("/upload")
def upload_knowledge(file: UploadFile = File(...)):
    result = rag_v01.upload(file.file.read(), file.filename or "upload")
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"doc_id": result["doc_id"], "created": result["created"], "name": result["name"]}


@router.delete("/{doc_id}")
def delete_knowledge(doc_id: str):
    if not rag_v01.delete_doc(doc_id):
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    return {"ok": True, "doc_id": doc_id}
