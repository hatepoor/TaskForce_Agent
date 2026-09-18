/**
 * Chat 资源类型镜像(唯一事实源:API-CONTRACT.md §2.1 / §3)。
 * 分两段:SSE 与端点契约镜像(后端形状) + UI 侧模型(前端内部使用)。
 */

/* ---------- 契约镜像:SSE 事件载荷(§三) ---------- */

export type RouteNext = 'answer' | 'ask' | 'memory' | 'dispatch'

/** route 事件里的单个子任务(§3.3)。 */
export interface TaskPayload {
  agent: 'retriever' | 'research' | 'executor'
  task: string
  reason: string
}

/** route 事件载荷(§3.3):next=ask 时 question 有值,next=dispatch 时 tasks 有值。 */
export interface RoutePayload {
  next: RouteNext
  question: string | null
  tasks: TaskPayload[] | null
}

/** interrupt 事件载荷(B3 信封,§3.3):kind 自描述,恢复端点按 kind 选,不靠猜。 */
export interface InterruptEnvelope {
  kind: 'ask' | 'memory' | 'unknown'
  text: string
}

/** usage 事件载荷(§3.3):进程级累计值,非本轮消耗,前端做差分。 */
export interface UsageEvent {
  thread_id: string
  calls: number
  input_tokens: number
  output_tokens: number
}

/** error 事件载荷(B4,§3.3):code 如 'recursion_limit'。 */
export interface ErrorEvent {
  message: string
  code?: string
}

/* ---------- 契约镜像:端点请求/响应(§2.1) ---------- */

/** POST /chat 请求体(§2.1.1):thread_id 由前端生成(sess- 前缀;可省略)。 */
export interface ChatRequest {
  thread_id?: string
  text: string
}

/** POST /chat/confirm 请求体(§2.1.2)。 */
export interface ConfirmRequest {
  thread_id: string
  approved: boolean
}

/** POST /chat/answer 请求体(§2.1.3)。 */
export interface AnswerRequest {
  thread_id: string
  text: string
}

/** POST /chat/summary 请求体(§2.1.8):后台任务全批完成后的自动汇总轮。 */
export interface SummaryRequest {
  thread_id: string
}

/** GET /chat/tasks 响应(§2.1.7):后台任务 peek(非消费),前端轮询用。 */
export interface TaskStatusResponse {
  /** 未完成数;全批完成的判据是 pending === 0 */
  pending: number
  /** 已完成未消费数;> 0 才值得发起汇总(轮询不消费,结果留给汇总轮 drain) */
  done: number
}

/** GET /chat/threads 响应(§2.1.4):纯 id 列表,无标题/时间。 */
export interface ThreadListResponse {
  threads: string[]
}

/** GET /chat/threads/meta 响应(§2.1.5,B2 已落地)。 */
export interface ThreadMetaResponse {
  threads: ThreadMetaRow[]
}

/** 历史回填的单条消息(§2.1.6):后端已过滤内部合成消息。 */
export interface ThreadMessage {
  role: 'user' | 'assistant'
  content: string
}

/** GET /chat/threads/{thread_id}/messages 响应(§2.1.6,B1 已落地)。 */
export interface ThreadMessagesResponse {
  thread_id: string
  messages: ThreadMessage[]
  /** 无挂起时为 null;有挂起时与 SSE interrupt 帧同信封,前端复用同一套渲染。 */
  pending_interrupt: InterruptEnvelope | null
}

/* ---------- UI 侧模型(ARCHITECTURE §5.3) ---------- */

export interface BaseItem {
  id: string
  seq: number
  at: number
}

export interface UserItem extends BaseItem {
  kind: 'user'
  text: string
}

export interface AssistantItem extends BaseItem {
  kind: 'assistant'
  text: string
  /** true:纯文本 pre-wrap + 光标;false:Markdown 渲染。 */
  streaming: boolean
  usage?: TurnUsage
  /** 兜底文案:递归过深 / 无输出 / 流中断。 */
  note?: string
  error?: { message: string; status?: number }
}

export interface RouteItem extends BaseItem {
  kind: 'route'
  route: RoutePayload
}

export interface InterruptItem extends BaseItem {
  kind: 'interrupt'
  sub: 'ask' | 'memory' | 'unknown'
  text: string
  status: 'waiting' | 'submitting' | 'resolved' | 'failed'
  /** ask 已答时的回答文本。 */
  answer?: string
  /** memory 已决时的结果。 */
  approved?: boolean
  error?: string
}

/** 时间序平铺联合数组(不是 user/assistant 双数组,天然保序)。 */
export type ChatItem = UserItem | AssistantItem | RouteItem | InterruptItem

export interface TurnUsage {
  calls: number
  inputTokens: number
  outputTokens: number
}

export interface TurnState {
  turnId: string
  status: 'streaming' | 'done' | 'aborted' | 'error'
  startedAt: number
  finishedAt?: number
  usageBefore?: { calls: number; input_tokens: number; output_tokens: number }
  usageAfter?: UsageEvent
  error?: { message: string; status?: number }
}

export interface PendingInterrupt {
  sub: 'ask' | 'memory' | 'unknown'
  text: string
  status: InterruptItem['status']
  /** 关联消息数组里的 InterruptItem。 */
  itemId: string
}

/** 本地会话标题/时间(localStorage,§5.2)。 */
export interface ThreadMeta {
  title: string
  createdAt: number
  lastActiveAt: number
  /**
   * 该会话已派发后台任务、等全批完成自动汇总(派发时置位;轮询确认无待汇总项后清位)。
   * 随本地元数据持久化:刷新页面后继续等,不必重新提问。
   */
  awaitingTasks?: boolean
}

/** GET /chat/threads/meta 的单行(§2.1.5)。 */
export interface ThreadMetaRow {
  thread_id: string
  last_checkpoint: string
  checkpoints: number
}