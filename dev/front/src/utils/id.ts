/**
 * 本地 id 生成。
 *
 * thread_id 必须带 `sess-` 前缀且由前端生成:后端会话列表按 LIKE 'sess-%' 过滤
 * (裸 UUID 永远不进列表),而全流唯一带 thread_id 的 usage 帧在轮末才发,
 * 不能等它确认身份(ARCHITECTURE 坑 3)。
 */

/** 后端会话列表的硬过滤前缀;漂移由 isThreadId 在开发期暴露。 */
export const THREAD_ID_PREFIX = 'sess-'

/** crypto.randomUUID 仅安全上下文(localhost / https)可用,局域网 IP 访问时走降级分支。 */
function randomUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const rand = (): string => Math.random().toString(16).slice(2, 10)
  return `${Date.now().toString(16)}-${rand()}-${rand()}`
}

/** 唯一 thread_id 生成入口:新建会话、首次载入都经它。 */
export function newThreadId(): string {
  return `${THREAD_ID_PREFIX}${randomUuid()}`
}

/** 前缀断言:不合规的 id 说明后端契约漂移(见 chat store 的 loadThreads)。 */
export function isThreadId(id: string): boolean {
  return id.startsWith(THREAD_ID_PREFIX)
}

/** UI 侧项 id(消息项 / 轮次 id),与 thread_id 无关。 */
export function newItemId(): string {
  return randomUuid()
}