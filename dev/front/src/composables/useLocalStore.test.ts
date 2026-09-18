import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createFakeStorage } from '@/test-utils/fakeStorage'

import {
  CURRENT_THREAD_KEY,
  THREAD_META_KEY,
  readCurrentThreadId,
  useLocalStore,
  writeCurrentThreadId,
} from './useLocalStore'

describe('useLocalStore', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createFakeStorage())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('写入后可读回(模拟刷新:新实例读同一份存储)', () => {
    const a = useLocalStore<Record<string, { title: string }>>(THREAD_META_KEY, {})
    a.update((draft) => {
      draft['sess-1'] = { title: '第一条' }
    })

    const b = useLocalStore<Record<string, { title: string }>>(THREAD_META_KEY, {})
    expect(b.state.value).toEqual({ 'sess-1': { title: '第一条' } })
    expect(localStorage.getItem(THREAD_META_KEY)).toContain('"v":1')
  })

  it('update 是读-改-写:保留已有键,只改传入的字段', () => {
    const s = useLocalStore<Record<string, { n: number }>>('k', {})
    s.update((draft) => {
      draft['a'] = { n: 1 }
    })
    s.update((draft) => {
      draft['b'] = { n: 2 }
    })
    expect(s.state.value).toEqual({ a: { n: 1 }, b: { n: 2 } })
  })

  it('脏数据(非法 JSON)回退初值并移除键', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    localStorage.setItem('k', '{ 这不是 JSON')

    const s = useLocalStore<{ n: number }>('k', { n: 0 })
    expect(s.state.value).toEqual({ n: 0 })
    expect(localStorage.getItem('k')).toBeNull()
    expect(warn).toHaveBeenCalled()
  })

  it('信封版本不符时回退初值(不误读旧结构)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    localStorage.setItem('k', JSON.stringify({ v: 99, data: { n: 7 } }))

    const s = useLocalStore<{ n: number }>('k', { n: 0 })
    expect(s.state.value).toEqual({ n: 0 })
    expect(localStorage.getItem('k')).toBeNull()
    expect(warn).toHaveBeenCalled()
  })

  it('localStorage 不可用时静默降级:读写都不抛,内存态照常', () => {
    vi.stubGlobal('localStorage', undefined)
    const s = useLocalStore<{ n: number }>('k', { n: 0 })
    expect(() => s.write({ n: 1 })).not.toThrow()
    expect(s.state.value).toEqual({ n: 1 })
  })

  it('clear 重置为初值并移除键', () => {
    const s = useLocalStore<{ n: number }>('k', { n: 0 })
    s.write({ n: 5 })
    s.clear()
    expect(s.state.value).toEqual({ n: 0 })
    expect(localStorage.getItem('k')).toBeNull()
  })
})

describe('当前会话 id', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createFakeStorage())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('写入后可读回;空串视作无记录', () => {
    writeCurrentThreadId('sess-abc')
    expect(readCurrentThreadId()).toBe('sess-abc')

    localStorage.setItem(CURRENT_THREAD_KEY, '')
    expect(readCurrentThreadId()).toBeNull()
  })

  it('未写过时返回 null(由 store 回落到新 id)', () => {
    expect(readCurrentThreadId()).toBeNull()
  })
})