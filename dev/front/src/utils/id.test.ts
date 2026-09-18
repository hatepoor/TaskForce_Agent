import { afterEach, describe, expect, it, vi } from 'vitest'

import { THREAD_ID_PREFIX, isThreadId, newItemId, newThreadId } from './id'

describe('newThreadId', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('恒以 sess- 开头', () => {
    const id = newThreadId()
    expect(id.startsWith(THREAD_ID_PREFIX)).toBe(true)
    expect(id.length).toBeGreaterThan(THREAD_ID_PREFIX.length)
    expect(isThreadId(id)).toBe(true)
  })

  it('多次生成互不重复', () => {
    const ids = new Set(Array.from({ length: 100 }, () => newThreadId()))
    expect(ids.size).toBe(100)
  })

  it('非安全上下文(无 crypto.randomUUID)走降级分支,仍带前缀', () => {
    vi.stubGlobal('crypto', {})
    const id = newThreadId()
    expect(id.startsWith(THREAD_ID_PREFIX)).toBe(true)
    expect(id.length).toBeGreaterThan(THREAD_ID_PREFIX.length)
  })

  it('isThreadId 拒绝裸 UUID 与空串', () => {
    expect(isThreadId('3f2a9c1b-1111-2222-3333-444455556666')).toBe(false)
    expect(isThreadId('')).toBe(false)
  })
})

describe('newItemId', () => {
  it('与 thread_id 不同源:不带 sess- 前缀且互不重复', () => {
    const a = newItemId()
    const b = newItemId()
    expect(a).not.toBe(b)
    expect(a.startsWith(THREAD_ID_PREFIX)).toBe(false)
  })
})