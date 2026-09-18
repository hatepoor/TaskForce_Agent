/**
 * 会话身份 + 各会话的消息 / 轮次 / 挂起态(ARCHITECTURE §5.2)。
 *
 * 模块 06 已实现:会话列表、切换、历史回填、本地标题;
 * 轮次动作(beginTurn ~ resolvePending)目前是空壳(console.warn),由模块 07 的
 * useChatStream 转实现——调用它们不会有副作用,也绝不抛错。
 *
 * 三个 ByThread 映射是"切会话不丢、不串台"的关键:所有状态按 thread_id 分组,
 * currentThreadId 只决定 computed 读哪一组。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { listThreadMessages, listThreadsMeta } from '@/api/chat'
import { errText } from '@/api/http'
import {
  THREAD_META_KEY,
  readCurrentThreadId,
  useLocalStore,
  writeCurrentThreadId,
} from '@/composables/useLocalStore'
import { useUiStore } from '@/stores/ui'
import type {
  AssistantItem,
  ChatItem,
  InterruptEnvelope,
  InterruptItem,
  PendingInterrupt,
  RoutePayload,
  ThreadMessage,
  ThreadMeta,
  ThreadMetaRow,
  TurnState,
  TurnUsage,
  UsageEvent,
} from '@/types/chat'
import { isThreadId, newItemId, newThreadId } from '@/utils/id'

/** 会话列表一行(后端 meta 与本地元数据融合后的展示模型)。 */
export interface SessionRow {
  threadId: string
  /** 本地标题,空串表示还没取到首条输入 */
  title: string
  /** 本地记录的最后活跃时间;0 = 未知(后端有但本地没碰过) */
  lastActiveAt: number
  /** 后端已有 checkpoint(即发过消息);本地新建未发消息为 false */
  persisted: boolean
}

/** 标题取首条输入前 20 字:折叠空白,超长截断。 */
export function titleFromText(text: string, limit = 20): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length <= limit ? flat : `${flat.slice(0, limit)}…`
}

/** B1 响应的消息数组 → 前端消息项(纯函数,便于单测)。 */
export function buildHistoryItems(
  messages: ThreadMessage[],
  pending: InterruptEnvelope | null,
): ChatItem[] {
  const items: ChatItem[] = messages.map((m, seq) =>
    m.role === 'user'
      ? { kind: 'user', id: newItemId(), seq, at: 0, text: m.content }
      : { kind: 'assistant', id: newItemId(), seq, at: 0, text: m.content, streaming: false },
  )
  if (pending !== null) {
    items.push({
      kind: 'interrupt',
      id: newItemId(),
      seq: items.length,
      at: 0,
      sub: pending.kind,
      text: pending.text,
      status: 'waiting',
    })
  }
  return items
}

export const useChatStore = defineStore('chat', () => {
  const ui = useUiStore()
  const local = useLocalStore<Record<string, ThreadMeta>>(THREAD_META_KEY, {})

  // ---- 会话身份 ----
  const threadMeta = local.state
  const threads = ref<ThreadMetaRow[]>([])
  const currentThreadId = ref<string>(readCurrentThreadId() ?? newThreadId())
  const loadingThreads = ref(false)
  const threadsError = ref('')

  // ---- 消息与轮次(按会话分组,切会话不丢) ----
  const itemsByThread = ref<Record<string, ChatItem[]>>({})
  const turnByThread = ref<Record<string, TurnState | null>>({})
  const pendingByThread = ref<Record<string, PendingInterrupt | null>>({})
  const hydratingByThread = ref<Record<string, boolean>>({})

  // 回填竞态令牌(非响应式):同一会话并发回填时只有最后一次的结果作数
  const hydrateToken: Record<string, number> = {}

  // 轮次簿记(非响应式):流一旦开始就锁定到发起它的会话,用户切走也不串台
  let activeTurnThread: string | null = null
  let tokenBuf = ''
  let rafId: number | null = null
  /** 本轮是否已有任何事件到达(token/route/interrupt/usage):Composer 据此决定何时清空草稿 */
  const turnHasOutput = ref(false)

  const items = computed<ChatItem[]>(() => itemsByThread.value[currentThreadId.value] ?? [])
  const turn = computed<TurnState | null>(() => turnByThread.value[currentThreadId.value] ?? null)
  const pending = computed<PendingInterrupt | null>(
    () => pendingByThread.value[currentThreadId.value] ?? null,
  )
  const isStreaming = computed(() => turn.value?.status === 'streaming')
  const loadingHistory = computed(() => hydratingByThread.value[currentThreadId.value] === true)
  const currentTitle = computed(() => threadMeta.value[currentThreadId.value]?.title ?? '')

  /** 会话列表:本地新建(后端还没有 checkpoint)的排最前,其余按后端最近活跃。 */
  const sessionList = computed<SessionRow[]>(() => {
    const fromServer: SessionRow[] = threads.value.map((row) => ({
      threadId: row.thread_id,
      title: threadMeta.value[row.thread_id]?.title ?? '',
      lastActiveAt: threadMeta.value[row.thread_id]?.lastActiveAt ?? 0,
      persisted: true,
    }))
    const known = new Set(threads.value.map((row) => row.thread_id))
    const localOnly: SessionRow[] = Object.entries(threadMeta.value)
      .filter(([id]) => !known.has(id))
      .map(([id, meta]) => ({
        threadId: id,
        title: meta.title,
        lastActiveAt: meta.lastActiveAt,
        persisted: false,
      }))
      .sort((a, b) => b.lastActiveAt - a.lastActiveAt)
    return [...localOnly, ...fromServer]
  })

  // ---- 本地元数据 ----

  /** 触碰会话:没有本地记录就补一条(空标题),有则刷新活跃时间。 */
  function touchThread(threadId: string): void {
    const now = Date.now()
    local.update((draft) => {
      const prev = draft[threadId]
      draft[threadId] =
        prev === undefined
          ? { title: '', createdAt: now, lastActiveAt: now }
          : { ...prev, lastActiveAt: now }
    })
  }

  /** 本地标题只认首条输入(已有标题不覆盖),由模块 07 首次发送时调用。 */
  function setThreadTitle(threadId: string, text: string): void {
    const title = titleFromText(text)
    if (title === '') return
    const prev = threadMeta.value[threadId]
    if (prev !== undefined && prev.title !== '') return

    const now = Date.now()
    local.update((draft) => {
      const base = draft[threadId] ?? { title: '', createdAt: now, lastActiveAt: now }
      draft[threadId] = { ...base, title }
    })
  }

  /** 该会话是否在等后台任务全批完成(useTaskWatch 的轮询开关)。 */
  function hasAwaitingTasks(threadId: string): boolean {
    return threadMeta.value[threadId]?.awaitingTasks === true
  }

  /** 置位/清位"待自动汇总";随本地元数据持久化(刷新后继续等,不必重新提问)。 */
  function setAwaitingTasks(threadId: string, awaiting: boolean): void {
    if (hasAwaitingTasks(threadId) === awaiting) return
    const now = Date.now()
    local.update((draft) => {
      const prev = draft[threadId] ?? { title: '', createdAt: now, lastActiveAt: now }
      if (awaiting) draft[threadId] = { ...prev, awaitingTasks: true }
      else {
        const { awaitingTasks: _dropped, ...rest } = prev
        draft[threadId] = rest
      }
    })
  }

  function setCurrent(threadId: string): void {
    currentThreadId.value = threadId
    writeCurrentThreadId(threadId)
  }

  // ---- 会话动作 ----

  /** 新建会话:只在前端生成 id 置为当前,不请求后端(后端首次 /chat 才惰性建 checkpoint)。 */
  function newThread(): string {
    const id = newThreadId()
    touchThread(id)
    itemsByThread.value[id] = []
    pendingByThread.value[id] = null
    setCurrent(id)
    return id
  }

  /** 切换会话:置当前 + 触碰本地元数据 + 按需回填历史。 */
  function switchThread(threadId: string, opts: { hydrate?: boolean } = {}): void {
    const id = threadId.trim()
    if (id === '') return
    touchThread(id)
    setCurrent(id)
    if (opts.hydrate !== false) ensureHydrated(id)
  }

  /** 拉取后端会话元数据(B2),后端已按最近活跃排序。 */
  async function loadThreads(): Promise<void> {
    loadingThreads.value = true
    threadsError.value = ''
    try {
      const res = await listThreadsMeta()
      threads.value = res.threads
      for (const row of res.threads) {
        if (!isThreadId(row.thread_id)) {
          console.warn(`[chat] 会话 id 缺少 sess- 前缀(后端过滤器漂移?):${row.thread_id}`)
        }
      }
      prefetchRecent()
    } catch (e) {
      threadsError.value = errText(e)
    } finally {
      loadingThreads.value = false
    }
  }

  /**
   * 预热最近 N 个会话:后台回填内容——列表标题(来自首条用户消息)一次补齐,
   * 点击切换时秒开(实测回填约 9ms,12 个并发对后端无压力;失败静默,不打扰首屏)。
   */
  function prefetchRecent(limit = 12): void {
    for (const row of sessionList.value.slice(0, limit)) ensureHydrated(row.threadId)
  }

  /** 内容按需载入:已有内容或正在载入则不重复请求。 */
  function ensureHydrated(threadId: string = currentThreadId.value): void {
    if (itemsByThread.value[threadId] !== undefined) return
    if (hydratingByThread.value[threadId] === true) return
    void hydrateFromServer(threadId)
  }

  /**
   * 历史回填(B1):messages → ChatItem[],pending_interrupt → 挂起占位。
   * 流式进行中不覆盖(模块 07 的当前轮优先);并发回填以最后一次为准。
   */
  async function hydrateFromServer(threadId: string): Promise<void> {
    // 用函数包一层读状态:await 之后要重新判断,不能被前面的窄化骗过
    const isBusy = (): boolean => turnByThread.value[threadId]?.status === 'streaming'
    if (isBusy()) return

    const token = (hydrateToken[threadId] ?? 0) + 1
    hydrateToken[threadId] = token
    hydratingByThread.value[threadId] = true
    try {
      const res = await listThreadMessages(threadId)
      if (hydrateToken[threadId] !== token) return
      if (isBusy()) return

      const list = buildHistoryItems(res.messages, res.pending_interrupt)
      itemsByThread.value[threadId] = list

      // 回填补齐标题:本地没标题的会话(CLI/API 建的、换过浏览器)用首条用户消息兜底,
      // 否则列表里全是"未命名会话 + sess-xxx",整页看着像半成品
      const firstUser = res.messages.find((m) => m.role === 'user')
      if (firstUser !== undefined) setThreadTitle(threadId, firstUser.content)

      const last = list[list.length - 1]
      pendingByThread.value[threadId] =
        last !== undefined && last.kind === 'interrupt'
          ? { sub: last.sub, text: last.text, status: 'waiting', itemId: last.id }
          : null
    } catch (e) {
      if (hydrateToken[threadId] !== token) return
      ui.toast(`加载会话历史失败:${errText(e)}`, 'error')
    } finally {
      if (hydrateToken[threadId] === token) hydratingByThread.value[threadId] = false
    }
  }

  // ---- 轮次动作(模块 07) ----

  /** 动作落在"本轮所属会话"上:流开始后用户切走,输出仍写回原会话。 */
  function turnThread(): string {
    return activeTurnThread ?? currentThreadId.value
  }

  function nextSeq(threadId: string): number {
    return itemsByThread.value[threadId]?.length ?? 0
  }

  function pushItem(threadId: string, item: ChatItem): void {
    const list = itemsByThread.value[threadId]
    if (list === undefined) itemsByThread.value[threadId] = [item]
    else list.push(item)
  }

  function lastAssistant(threadId: string): AssistantItem | undefined {
    const list = itemsByThread.value[threadId]
    if (list === undefined) return undefined
    for (let i = list.length - 1; i >= 0; i -= 1) {
      const it = list[i]
      if (it !== undefined && it.kind === 'assistant') return it
    }
    return undefined
  }

  function closeAssistantStream(threadId: string): void {
    const item = lastAssistant(threadId)
    if (item !== undefined) item.streaming = false
  }

  /**
   * 收掉当前 AI 段:空占位只是"正在生成"的加载指示,遇轨迹/挂起直接收回,
   * 不留一条空气泡;已有正文则关光标留在原位(轨迹条之后的新 token 另起一段)。
   */
  function closeOrDropPlaceholder(threadId: string): void {
    const list = itemsByThread.value[threadId]
    if (list === undefined) return
    const last = list[list.length - 1]
    if (last === undefined || last.kind !== 'assistant') return
    if (last.streaming && last.text.trim() === '') {
      list.pop()
      return
    }
    last.streaming = false
  }

  /** 用户消息落列表(气泡 + 首条输入设本地标题)。 */
  function pushUser(text: string): void {
    const threadId = currentThreadId.value
    setThreadTitle(threadId, text)
    pushItem(threadId, {
      kind: 'user',
      id: newItemId(),
      seq: nextSeq(threadId),
      at: Date.now(),
      text,
    })
  }

  /** 开轮:记 usageBefore 快照 + 立刻插一条空 AI 占位(光标态,避免发送后空窗)。 */
  function beginTurn(): void {
    flushTokens()
    const threadId = currentThreadId.value
    activeTurnThread = threadId
    turnHasOutput.value = false

    const before = (turnByThread.value[threadId] ?? null)?.usageAfter
    turnByThread.value[threadId] = {
      turnId: newItemId(),
      status: 'streaming',
      startedAt: Date.now(),
      usageBefore:
        before === undefined
          ? { calls: 0, input_tokens: 0, output_tokens: 0 }
          : { calls: before.calls, input_tokens: before.input_tokens, output_tokens: before.output_tokens },
    }
    pushItem(threadId, {
      kind: 'assistant',
      id: newItemId(),
      seq: nextSeq(threadId),
      at: Date.now(),
      text: '',
      streaming: true,
    })
  }

  /** token 进**非响应式**缓冲,rAF 每帧最多落一次盘(坑 5:每 token 一次响应式写会卡)。 */
  function appendToken(token: string): void {
    turnHasOutput.value = true
    tokenBuf += token
    if (rafId !== null) return
    if (typeof requestAnimationFrame !== 'function') {
      flushTokens()
      return
    }
    rafId = requestAnimationFrame(() => {
      rafId = null
      flushTokens()
    })
  }

  /** 把缓冲并入末尾一条 streaming 的 assistant;没有则新起一条。 */
  function flushTokens(): void {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    const text = tokenBuf
    tokenBuf = ''
    if (text === '') return

    const threadId = turnThread()
    const list = itemsByThread.value[threadId]
    const last = list?.[list.length - 1]
    if (last !== undefined && last.kind === 'assistant' && last.streaming) {
      last.text += text
      return
    }
    pushItem(threadId, {
      kind: 'assistant',
      id: newItemId(),
      seq: nextSeq(threadId),
      at: Date.now(),
      text,
      streaming: true,
    })
  }

  /** route 事件:先落地已收 token,关掉当前 AI 段,再插轨迹项(轨迹之后的 token 另起一段)。 */
  function pushRoute(route: RoutePayload): void {
    turnHasOutput.value = true
    flushTokens()
    const threadId = turnThread()
    // 派发成功即置"待自动汇总":useTaskWatch 据此轮询,全批完成后主动出汇总(无需用户询问)
    if (route.next === 'dispatch' && (route.tasks?.length ?? 0) > 0) {
      setAwaitingTasks(threadId, true)
    }
    closeOrDropPlaceholder(threadId)
    pushItem(threadId, {
      kind: 'route',
      id: newItemId(),
      seq: nextSeq(threadId),
      at: Date.now(),
      route,
    })
  }

  /** interrupt 帧:落挂起占位项 + 记 pending(卡片交互在模块 08)。 */
  function setPending(envelope: InterruptEnvelope): void {
    turnHasOutput.value = true
    flushTokens()
    const threadId = turnThread()
    closeOrDropPlaceholder(threadId)

    const item: InterruptItem = {
      kind: 'interrupt',
      id: newItemId(),
      seq: nextSeq(threadId),
      at: Date.now(),
      sub: envelope.kind,
      text: envelope.text,
      status: 'waiting',
    }
    pushItem(threadId, item)
    pendingByThread.value[threadId] = {
      sub: item.sub,
      text: item.text,
      status: 'waiting',
      itemId: item.id,
    }
  }

  /** usage 帧是进程累计值 → 与轮首快照差分,本轮增量写到 AI 项上(坑 8)。 */
  function attachUsage(usage: UsageEvent): void {
    turnHasOutput.value = true
    const threadId = turnThread()
    const st = turnByThread.value[threadId]
    if (st === null || st === undefined) return
    st.usageAfter = usage

    const before = st.usageBefore ?? { calls: 0, input_tokens: 0, output_tokens: 0 }
    const item = lastAssistant(threadId)
    if (item === undefined) return
    const delta: TurnUsage = {
      calls: Math.max(0, usage.calls - before.calls),
      inputTokens: Math.max(0, usage.input_tokens - before.input_tokens),
      outputTokens: Math.max(0, usage.output_tokens - before.output_tokens),
    }
    item.usage = delta
  }

  /** 流正常结束:关光标、收尾轮次、空输出补兜底文案、本轮没新挂起则清旧挂起。 */
  function endTurn(): void {
    flushTokens()
    const threadId = turnThread()
    closeAssistantStream(threadId)

    const st = turnByThread.value[threadId]
    if (st !== null && st !== undefined) {
      st.status = 'done'
      st.finishedAt = Date.now()
    }

    const item = lastAssistant(threadId)
    if (item !== undefined && item.text.trim() === '' && item.note === undefined) {
      item.note = '本轮没有产生文本输出(可能已直接执行动作,如写入记忆)'
    }
    // 提交中的挂起卡随本轮正常结束落定(挂起已被后端受理)
    const list = itemsByThread.value[threadId]
    if (list !== undefined) {
      for (const it of list) {
        if (it.kind === 'interrupt' && it.status === 'submitting') it.status = 'resolved'
      }
    }
    // 挂起态只在"还有等待回答的卡"时保留:本轮新出的 ask 留着,已答/被忽略的清掉
    const pend = pendingByThread.value[threadId]
    if (pend !== undefined && pend !== null) {
      const pi = list?.find((it) => it.id === pend.itemId)
      pendingByThread.value[threadId] =
        pi !== undefined && pi.kind === 'interrupt' && pi.status === 'waiting' ? pend : null
    }

    activeTurnThread = null
    turnHasOutput.value = false
  }

  /** 用户点了「停止接收」:保留已收文本,标 aborted(坑 7:服务端未必真停)。 */
  function abortTurn(): void {
    flushTokens()
    const threadId = turnThread()
    closeAssistantStream(threadId)

    const note = '已停止接收;服务端可能仍完成了部分动作'
    const st = turnByThread.value[threadId]
    if (st !== null && st !== undefined) {
      st.status = 'aborted'
      st.finishedAt = Date.now()
      st.error = { message: note }
    }
    const item = lastAssistant(threadId)
    if (item !== undefined) item.note = note // 无论有无正文都留灰字提示(坑 7)

    activeTurnThread = null
    turnHasOutput.value = false
  }

  /** 失败(网络/非 2xx/流内 error 帧):已收文本保留,错误条给重试;挂起卡标失效并清挂起。 */
  function failTurn(message: string, status?: number): void {
    flushTokens()
    const threadId = turnThread()
    closeAssistantStream(threadId)

    const err = status === undefined ? { message } : { message, status }
    const st = turnByThread.value[threadId]
    if (st !== null && st !== undefined) {
      st.status = 'error'
      st.finishedAt = Date.now()
      st.error = err
    }

    const item = lastAssistant(threadId)
    if (item !== undefined) {
      item.error = err
      item.streaming = false
    }

    const pend = pendingByThread.value[threadId]
    if (pend !== null && pend !== undefined) {
      const pi = itemsByThread.value[threadId]?.find((it) => it.id === pend.itemId)
      if (pi !== undefined && pi.kind === 'interrupt') {
        pi.status = 'failed'
        pi.error = message
      }
      pendingByThread.value[threadId] = null
    }

    // 400 = 挂起已在别处恢复/已失效:业务提示 + 刷新会话元数据(坑 10)
    if (status === 400) {
      ui.toast(message, 'error')
      void loadThreads()
    }

    activeTurnThread = null
    turnHasOutput.value = false
  }

  /** 兜底文案按正常正文呈现(recursion_limit 不是错误,是一条回复)。 */
  function noteTurn(note: string): void {
    flushTokens()
    const item = lastAssistant(turnThread())
    if (item !== undefined) item.note = note
  }

  /** 挂起卡状态就地推进(answer/approved 由模块 08 的卡片写入)。 */
  type PendingPatch = Partial<Pick<InterruptItem, 'status' | 'answer' | 'approved' | 'error'>>

  function resolvePending(patch: PendingPatch): void {
    const threadId = currentThreadId.value
    const pend = pendingByThread.value[threadId]
    if (pend === null || pend === undefined) return

    const item = itemsByThread.value[threadId]?.find((it) => it.id === pend.itemId)
    if (item !== undefined && item.kind === 'interrupt') {
      if (patch.status !== undefined) item.status = patch.status
      if (patch.answer !== undefined) item.answer = patch.answer
      if (patch.approved !== undefined) item.approved = patch.approved
      if (patch.error !== undefined) item.error = patch.error
    }
    if (patch.status !== undefined) pend.status = patch.status
    // 提交中仍算挂起(Composer 继续禁用);已决/失效才解除
    if (patch.status !== undefined && patch.status !== 'waiting' && patch.status !== 'submitting') {
      pendingByThread.value[threadId] = null
    }
  }

  return {
    // 状态
    threadMeta,
    threads,
    currentThreadId,
    items,
    turn,
    pending,
    isStreaming,
    loadingThreads,
    threadsError,
    loadingHistory,
    currentTitle,
    sessionList,
    itemsByThread,
    pendingByThread,
    turnHasOutput,
    // 动作(模块 06 已实现)
    newThread,
    switchThread,
    loadThreads,
    ensureHydrated,
    hydrateFromServer,
    touchThread,
    setThreadTitle,
    hasAwaitingTasks,
    setAwaitingTasks,
    // 动作(模块 07 实现)
    pushUser,
    beginTurn,
    appendToken,
    flushTokens,
    pushRoute,
    setPending,
    attachUsage,
    endTurn,
    abortTurn,
    failTurn,
    noteTurn,
    resolvePending,
  }
})