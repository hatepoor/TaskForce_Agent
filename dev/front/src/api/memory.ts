/**
 * Memory 资源封装(契约 §2.4)。
 */
import type { MemoryDeleteResult, MemoryListResponse } from '@/types/memory'

import { request } from './http'

/** GET /memory — 长期记忆列表(按 created_at 降序,固定 limit=100)。 */
export function listMemories(): Promise<MemoryListResponse> {
  return request<MemoryListResponse>('/memory')
}

/**
 * DELETE /memory/{key} — 删除单条记忆。
 * key 可能含中文/斜杠,必须 encodeURIComponent;store.delete() 幂等,删不存在的 key 也 200。
 */
export function removeMemory(key: string): Promise<MemoryDeleteResult> {
  return request<MemoryDeleteResult>(`/memory/${encodeURIComponent(key)}`, { method: 'DELETE' })
}