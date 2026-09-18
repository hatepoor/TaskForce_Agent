/**
 * 全局 UI store:目前仅 toast 队列(UI-DESIGN §1.3:3s 自动消失、最多堆叠 3 条)。
 * toast 是全局轻提示的唯一入口;成功/错误反馈一律经此,不在视图内自建浮层。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastType = 'success' | 'error'

export interface ToastItem {
  id: number
  msg: string
  type: ToastType
}

const TOAST_TTL_MS = 3000
const TOAST_MAX = 3

export const useUiStore = defineStore('ui', () => {
  const toasts = ref<ToastItem[]>([])
  const timers = new Map<number, ReturnType<typeof setTimeout>>()
  let nextId = 0

  function dismiss(id: number): void {
    const timer = timers.get(id)
    if (timer !== undefined) {
      clearTimeout(timer)
      timers.delete(id)
    }
    toasts.value = toasts.value.filter((it) => it.id !== id)
  }

  /** 全局轻提示唯一入口;返回 toast id 便于手动 dismiss */
  function toast(msg: string, type: ToastType = 'success'): number {
    const id = nextId
    nextId += 1
    toasts.value.push({ id, msg, type })

    // 超出上限:挤掉最旧一条
    while (toasts.value.length > TOAST_MAX) {
      const oldest = toasts.value[0]
      if (oldest === undefined) break
      dismiss(oldest.id)
    }

    timers.set(
      id,
      setTimeout(() => dismiss(id), TOAST_TTL_MS),
    )
    return id
  }

  return { toasts, toast, dismiss }
})