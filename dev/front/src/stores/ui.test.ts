import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useUiStore } from './ui'

describe('useUiStore.toast', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('push 后 3s 自动消失', () => {
    const ui = useUiStore()
    ui.toast('已复制')
    expect(ui.toasts).toHaveLength(1)

    vi.advanceTimersByTime(2999)
    expect(ui.toasts).toHaveLength(1)

    vi.advanceTimersByTime(1)
    expect(ui.toasts).toHaveLength(0)
  })

  it('最多堆叠 3 条:第 4 条挤掉最旧一条', () => {
    const ui = useUiStore()
    ui.toast('一')
    ui.toast('二')
    ui.toast('三')
    ui.toast('四')

    expect(ui.toasts.map((t) => t.msg)).toEqual(['二', '三', '四'])
  })

  it('dismiss 手动清除后不再受定时器影响', () => {
    const ui = useUiStore()
    const id = ui.toast('临时')
    ui.dismiss(id)
    expect(ui.toasts).toHaveLength(0)

    vi.advanceTimersByTime(5000)
    expect(ui.toasts).toHaveLength(0)
  })

  it('type 缺省为 success', () => {
    const ui = useUiStore()
    ui.toast('ok')
    expect(ui.toasts[0]?.type).toBe('success')
  })
})