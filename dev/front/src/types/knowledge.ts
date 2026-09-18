/**
 * Knowledge 资源类型镜像(唯一事实源:API-CONTRACT.md §2.3)。
 */

/** GET /knowledge 单条文档。 */
export interface KDoc {
  /** 32 位 hex(uuid4().hex)。 */
  doc_id: string
  /** 上传时的原始文件名。 */
  filename: string
  /** ISO 8601,带时区偏移。 */
  created_at: string
  /** 该文档切块数。 */
  chunks: number
}

/** GET /knowledge 响应(按 created_at 升序)。 */
export interface KDocListResponse {
  docs: KDoc[]
}

/**
 * POST /knowledge/upload 响应。
 * `created: false` 为内容判重命中(解析后文本 SHA-256 相同),复用已有 doc_id,
 * 不是错误——UI 提示"该文档已存在,已复用"。
 */
export interface KUploadResult {
  doc_id: string
  created: boolean
  name: string
}

/** DELETE /knowledge/{doc_id} 响应(B7 落地前,删除不存在的文档会 500 而非 404)。 */
export interface KDeleteResult {
  ok: boolean
  doc_id: string
}