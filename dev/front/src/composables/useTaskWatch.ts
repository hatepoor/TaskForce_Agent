/**
 * 后台任务监视(Web 侧"主动汇总"):派发后轮询 /chat/tasks,全批完成即自动发起汇总轮。
 *
 * 与 REPL 的 _auto_summary_worker 同语义(同一触发语 AUTO_NOTICE、同一条 run_turn 业务层):
 * - **用户优先**:用户轮正在流式时不抢跑,等这一轮结束的下一拍再汇总(对应 REPL 的 turn_lock);
 * - **按会话**:只盯当前会话(状态取自 chat store 的 awaitingTasks,派发时置位、随元数据持久化,
 *   刷新页面后继续等);切走会话暂停,切回来续上;
 * - **省电**:页面隐藏 / 视图被 KeepAlive 失活时暂停(与 useHealthPoll 同约定);
 * - **不消费**:peek 端点只读;真正的结果由服务端在汇总轮里 drain,这里只看计数。
 *
 * 触发条件:status.pending === 0 且 status.done > 0。pending===0 且 done===0 说明结果已被
 * 别的轮次消费(用户在完成前先提问),清位收工,不再汇总。轮询失败静默重试(本地单机,
 * 后端没起不该弹错);超过上限时长停止本次轮询(标记留在盘上,下次进会话重来)。
 */
import { onActivated, onDeactivated, onMounted, onUnmounted, watch } from 'vue'

import { fetchTaskStatus } from '@/api/chat'
import type { TaskStatusResponse } from '@/types/chat'
import { useChatStream } from '@/composables/useChatStream'
import { useChatStore } from '@/stores/chat'

/** 轮询间隔:后台任务以分钟计,3s 足够及时又不扰民。 */
export const TASK_POLL_MS = 3_000
/** 单次监视时长上限:任务卡死时不要无限轮询(15 分钟;标记保留,下次进会话重来)。 */
export const TASK_POLL_MAX_MS = 15 * 60_000

/** 一拍轮询的处置:等着 / 发起汇总 / 清位收工。 */
export type WatchAction = 'wait' | 'summarize' | 'clear'

/**
 * 轮询决策(纯函数,便于单测):
 * - 还有任务在跑(pending>0)→ 等全批;
 * - 无待汇总项(done===0)→ 清位(结果已被别的轮次消费,或本来就没派发成功);
 * - 用户轮流式中 → 让位,下一拍再来(用户优先,对应 REPL 的 turn_lock);
 * - 全批完成且有结果 → 发起自动汇总轮。
 */
export function decideStatus(st: TaskStatusResponse, isStreaming: boolean): WatchAction {
  if (st.pending > 0) return 'wait'
  if (st.done === 0) return 'clear'
  if (isStreaming) return 'wait'
  return 'summarize'
}

export function useTaskWatch(): void {
  const chat = useChatStore()
  const stream = useChatStream()

  let timer: ReturnType<typeof setInterval> | null = null
  let mounted = false
  let active = true // KeepAlive 视角下当前是否可见
  let startedAt = 0
  let inFlight = false

  function visible(): boolean {
    return typeof document === 'undefined' || document.visibilityState !== 'hidden'
  }

  function canPoll(): boolean {
    return mounted && active && visible()
  }

  function stop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  async function tick(): Promise<void> {
    if (inFlight) return
    const threadId = chat.currentThreadId
    if (!chat.hasAwaitingTasks(threadId) || Date.now() - startedAt > TASK_POLL_MAX_MS) {
      stop() // 没人等结果(或等太久了):收工
      return
    }
    inFlight = true
    try {
      const st = await fetchTaskStatus(threadId)
      if (!chat.hasAwaitingTasks(threadId)) return // await 期间被清位/切走
      const action = decideStatus(st, chat.isStreaming)
      if (action === 'wait') return
      if (action === 'clear') {
        chat.setAwaitingTasks(threadId, false) // 结果已被别的轮次消费(用户先问了),无需再汇总
        stop()
        return
      }
      await stream.summarizeThread(threadId)
    } catch {
      /* 静默重试:下一拍自动重来 */
    } finally {
      inFlight = false
    }
  }

  /** 起轮询:可见 + 已挂载 + 未失活 + 当前会话确实有待汇总任务才开表,并立刻探一次。 */
  function resume(): void {
    stop()
    if (!canPoll()) return
    if (!chat.hasAwaitingTasks(chat.currentThreadId)) return
    startedAt = Date.now()
    void tick()
    timer = setInterval(() => {
      if (canPoll()) void tick()
    }, TASK_POLL_MS)
  }

  function onVisibilityChange(): void {
    if (visible()) resume()
    else stop()
  }

  // 派发落位(置位后开表)与切换会话(切到有待汇总的会话续上)都要重新评估
  watch(() => chat.hasAwaitingTasks(chat.currentThreadId), (on) => {
    if (on) resume()
  })
  watch(() => chat.currentThreadId, () => resume())

  onMounted(() => {
    mounted = true
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange)
    }
    resume()
  })

  onActivated(() => {
    active = true
    resume()
  })

  onDeactivated(() => {
    active = false
    stop()
  })

  onUnmounted(() => {
    mounted = false
    active = false
    stop()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  })
}