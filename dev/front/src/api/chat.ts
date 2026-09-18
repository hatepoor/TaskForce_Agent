/**
 * Chat 资源封装(契约 §2.1)。
 * - listThreads / listThreadsMeta / listThreadMessages / fetchTaskStatus:普通 JSON 端点;
 * - send / submitAnswer / submitConfirm / summarize:SSE 四入口,转发 api/sse.ts 的 sseFetch
 *   (模块 05 已接通;仅 useChatStream(模块 07)允许调用)。
 */
import type {
  AnswerRequest,
  ChatRequest,
  ConfirmRequest,
  SummaryRequest,
  TaskStatusResponse,
  ThreadListResponse,
  ThreadMessagesResponse,
  ThreadMetaResponse,
} from '@/types/chat'

import { request } from './http'
import { sseFetch, type SseHandlers } from './sse'

/** GET /chat/threads — 会话线程 id 列表(§2.1.4)。 */
export function listThreads(): Promise<ThreadListResponse> {
  return request<ThreadListResponse>('/chat/threads')
}

/** GET /chat/threads/meta — 会话元数据(§2.1.5)。 */
export function listThreadsMeta(): Promise<ThreadMetaResponse> {
  return request<ThreadMetaResponse>('/chat/threads/meta')
}

/** GET /chat/threads/{thread_id}/messages — 历史消息回填(§2.1.6)。 */
export function listThreadMessages(threadId: string): Promise<ThreadMessagesResponse> {
  return request<ThreadMessagesResponse>(`/chat/threads/${encodeURIComponent(threadId)}/messages`)
}

/** GET /chat/tasks — 后台任务 peek(非消费,§2.1.7;useTaskWatch 轮询用)。 */
export function fetchTaskStatus(threadId: string): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(`/chat/tasks?thread_id=${encodeURIComponent(threadId)}`)
}

/* ---------- SSE 四入口:转发 sseFetch(模块 05 接通) ---------- */

/** POST /chat — 发起一轮对话(SSE,§2.1.1)。 */
export function send(
  body: ChatRequest,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return sseFetch('/chat', body, handlers, signal)
}

/** POST /chat/answer — ask 挂起恢复(SSE,§2.1.3)。 */
export function submitAnswer(
  body: AnswerRequest,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return sseFetch('/chat/answer', body, handlers, signal)
}

/** POST /chat/confirm — memory 挂起恢复(SSE,§2.1.2)。 */
export function submitConfirm(
  body: ConfirmRequest,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return sseFetch('/chat/confirm', body, handlers, signal)
}

/** POST /chat/summary — 后台任务全批完成后的自动汇总轮(SSE,§2.1.8)。 */
export function summarize(
  body: SummaryRequest,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return sseFetch('/chat/summary', body, handlers, signal)
}