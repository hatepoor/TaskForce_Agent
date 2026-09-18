/**
 * Memory 资源类型镜像(唯一事实源:API-CONTRACT.md §2.4)。
 */

/** GET /memory 单条长期记忆。 */
export interface MemoryItem {
  /** Store 主键。 */
  key: string
  /** 一句话原子事实;缺失时为 ""。 */
  content: string
  /** "explicit"(用户明示)| "confirmed"(自动确认);缺失时为 ""。 */
  source: 'explicit' | 'confirmed' | ''
  /** ISO 8601;缺失时为 ""。 */
  created_at: string
}

/** GET /memory 响应(按 created_at 降序,固定 limit=100)。 */
export interface MemoryListResponse {
  items: MemoryItem[]
}

/** DELETE /memory/{key} 响应;store.delete() 对不存在的 key 幂等,也返回 200。 */
export interface MemoryDeleteResult {
  ok: boolean
  key: string
}