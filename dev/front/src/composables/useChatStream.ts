/**
 * 领域层:把 SSE 传输事件翻译成 chat store 的动作(ARCHITECTURE §4.3)。
 * **唯一允许调用 sseFetch 的地方**——组件只调本组合函数,不直接碰传输层。
 *
 * 单飞:store 的 isStreaming 是第二道闸门(UI 禁用是第一道);不自动重试
 * (重试会重复触发整轮任务,见坑 4)。
 */
import { ref } from 'vue'

import { send, submitAnswer, submitConfirm, summarize } from '@/api/chat'
import type { SseHandlers } from '@/api/sse'
import { useChatStore } from '@/stores/chat'

export function useChatStream() {
  const chat = useChatStore()
  const controller = ref<AbortController | null>(null)

  function handlers(): SseHandlers {
    return {
      onToken: (t) => chat.appendToken(t),
      onRoute: (r) => chat.pushRoute(r),
      onInterrupt: (i) => chat.setPending(i),
      onUsage: (u) => chat.attachUsage(u),
      onErrorEvent: (e) => {
        // 递归超深是"正常回复"的一种(B4 的 error 帧带 code),不标错误态
        if (e.code === 'recursion_limit') chat.noteTurn(e.message)
        else chat.failTurn(e.message)
      },
      onError: (e) => chat.failTurn(e.message, e.kind === 'http' ? e.status : undefined),
      onDone: () => chat.endTurn(),
    }
  }

  /** 统一入口:占位轮次 + 发起请求 + 收尾(abort 判定)。 */
  async function start(invoke: (h: SseHandlers, signal: AbortSignal) => Promise<void>): Promise<void> {
    const ac = new AbortController()
    controller.value = ac
    chat.beginTurn()
    try {
      await invoke(handlers(), ac.signal)
    } finally {
      chat.flushTokens()
      if (ac.signal.aborted) chat.abortTurn()
      controller.value = null
    }
  }

  /** 发一条新消息:用户气泡落列表 → 开轮 → POST /chat。 */
  async function sendText(text: string): Promise<void> {
    const t = text.trim()
    if (t === '' || chat.isStreaming) return
    chat.pushUser(t)
    await start((h, signal) => send({ thread_id: chat.currentThreadId, text: t }, h, signal))
  }

  /** 重试:不重复插入用户气泡(仅用于请求失败/零输出场景)。 */
  async function resend(text: string): Promise<void> {
    const t = text.trim()
    if (t === '' || chat.isStreaming) return
    await start((h, signal) => send({ thread_id: chat.currentThreadId, text: t }, h, signal))
  }

  /** 回答 ask 问询(POST /chat/answer)。 */
  async function answer(text: string): Promise<void> {
    const t = text.trim()
    if (t === '' || chat.isStreaming) return
    await start((h, signal) => submitAnswer({ thread_id: chat.currentThreadId, text: t }, h, signal))
  }

  /** 确认/忽略 memory 提案(POST /chat/confirm)。 */
  async function confirm(approved: boolean): Promise<void> {
    if (chat.isStreaming) return
    await start((h, signal) => submitConfirm({ thread_id: chat.currentThreadId, approved }, h, signal))
  }

  /**
   * 后台任务全批完成后的自动汇总轮(POST /chat/summary,useTaskWatch 触发)。
   * 不插用户气泡:这轮由服务端以 AUTO_NOTICE 触发,不是用户说的话;历史回填也会过滤掉它。
   */
  async function summarizeThread(threadId: string): Promise<void> {
    if (chat.isStreaming) return
    if (chat.currentThreadId !== threadId) return // 切走会话就不代汇总,切回来由 watch 续上
    await start((h, signal) => summarize({ thread_id: threadId }, h, signal))
  }

  /** 仅停前端消费;服务端那轮仍会跑完(坑 7),文案用「停止接收」。 */
  function abort(): void {
    controller.value?.abort()
  }

  return { send: sendText, resend, answer, confirm, summarizeThread, abort }
}