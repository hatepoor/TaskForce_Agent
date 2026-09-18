/**
 * Knowledge 资源封装(契约 §2.3)。
 * 组件/store 只经本层访问 /knowledge(验收标准:组件层无裸 fetch)。
 */
import type { KDeleteResult, KDocListResponse, KUploadResult } from '@/types/knowledge'

import { request } from './http'

/** GET /knowledge — 文档列表(按 created_at 升序)。 */
export function listDocs(): Promise<KDocListResponse> {
  return request<KDocListResponse>('/knowledge')
}

/**
 * POST /knowledge/upload — 上传单文件(multipart/form-data)。
 * - 不手动设 Content-Type:让浏览器带 boundary(契约 §2.3);
 * - 单独给 120s 超时(20MB 文件 + embedding,契约 §3.6);
 * - 多选文件由调用方拆成串行 N 个请求。
 */
export function uploadDoc(file: File): Promise<KUploadResult> {
  const fd = new FormData()
  fd.append('file', file)
  return request<KUploadResult>('/knowledge/upload', {
    method: 'POST',
    body: fd,
    signal: AbortSignal.timeout(120_000),
  })
}

/** DELETE /knowledge/{doc_id}(B7 落地前删除不存在文档会 500,过渡处理见契约 §1.3)。 */
export function removeDoc(docId: string): Promise<KDeleteResult> {
  return request<KDeleteResult>(`/knowledge/${encodeURIComponent(docId)}`, { method: 'DELETE' })
}