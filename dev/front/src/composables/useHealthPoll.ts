/**
 * Health 数据源(模块级单例):导航轨状态点与设置页 HealthSection 读**同一份**数据、只跑**一条**轮询
 * (11-系统设置页 develop.md 的「NavRail 接线」配方落地于此)。
 *
 * 轮询策略(UI-DESIGN §4.4):
 * - 30s 间隔;`document.visibilityState === 'hidden'` 时暂停(后台零请求),回到前台立即补一次;
 * - 消费方按组件注册:KeepAlive 失活 / 卸载即注销,**最后一个**消费方离开才真正停表;
 * - 失败处理:`refresh()` 把错误文案**返回**给调用方——手动刷新失败弹 toast,后台轮询失败只落
 *   `error` 就地展示,避免后端一挂就每 30s 弹一次。
 *
 * 单例说明:状态与定时器在模块作用域,`visibilitychange` 监听只注册一次(随页面生命周期,
 * 不做注销——页面本身卸载时浏览器会回收)。
 */
import { onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue'
import type { Ref } from 'vue'

import { fetchHealth } from '@/api/health'
import type { HealthStatus } from '@/api/health'
import { errText } from '@/api/http'

/** 轮询间隔(30s,UI-DESIGN §4.4)。 */
export const HEALTH_POLL_MS = 30_000

export interface UseHealthPoll {
  data: Ref<HealthStatus | null>
  loading: Ref<boolean>
  /** 最近一次失败文案(`''` = 无错)。 */
  error: Ref<string>
  /** 最近一次成功时间戳(0 = 从未成功)。 */
  updatedAt: Ref<number>
  /** 拉一次;返回错误文案(`''` = 成功)。 */
  refresh: () => Promise<string>
}

// ---- 模块级共享状态 ----
const data = ref<HealthStatus | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref(0)

/** 活跃消费方(Set 天然去重:KeepAlive 组件首挂载时 onMounted 与 onActivated 都会触发) */
const consumers = new Set<symbol>()
let timer: ReturnType<typeof setInterval> | null = null
let bound = false

function visible(): boolean {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden'
}

function stop(): void {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

async function refresh(): Promise<string> {
  loading.value = true
  try {
    data.value = await fetchHealth()
    updatedAt.value = Date.now()
    error.value = ''
    return ''
  } catch (e) {
    error.value = errText(e)
    return error.value
  } finally {
    loading.value = false
  }
}

/** 起表:有消费方且页面可见才跑,并立刻补一次(在途请求不重复发)。 */
function resume(): void {
  stop()
  if (consumers.size === 0 || !visible()) return
  if (!loading.value) void refresh()
  timer = setInterval(() => {
    if (consumers.size > 0 && visible()) void refresh()
  }, HEALTH_POLL_MS)
}

function onVisibilityChange(): void {
  if (visible()) resume()
  else stop()
}

export function useHealthPoll(): UseHealthPoll {
  const id = Symbol('health-consumer')

  onMounted(() => {
    consumers.add(id)
    if (!bound && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange)
      bound = true
    }
    resume()
  })

  // KeepAlive:切走即注销(最后一个走才停表),切回来立即补一次
  onActivated(() => {
    consumers.add(id)
    resume()
  })

  onDeactivated(() => {
    consumers.delete(id)
    if (consumers.size === 0) stop()
  })

  onUnmounted(() => {
    consumers.delete(id)
    if (consumers.size === 0) stop()
  })

  return { data, loading, error, updatedAt, refresh }
}