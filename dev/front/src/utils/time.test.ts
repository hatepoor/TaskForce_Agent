import { describe, expect, it } from 'vitest'

import { fmtClock, fmtRelative } from './time'

const NOW = new Date('2026-09-17T12:00:00').getTime()
const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

describe('fmtRelative', () => {
  it('0 与非法值返回空串(历史消息没有时间戳)', () => {
    expect(fmtRelative(0, NOW)).toBe('')
    expect(fmtRelative(Number.NaN, NOW)).toBe('')
    expect(fmtRelative(-1, NOW)).toBe('')
  })

  it('1 分钟内为"刚刚",未来时间戳(时钟回拨)同样兜底', () => {
    expect(fmtRelative(NOW - 30_000, NOW)).toBe('刚刚')
    expect(fmtRelative(NOW + 5 * MIN, NOW)).toBe('刚刚')
  })

  it('分钟 / 小时 / 天三档边界正确', () => {
    expect(fmtRelative(NOW - MIN, NOW)).toBe('1 分钟前')
    expect(fmtRelative(NOW - 59 * MIN, NOW)).toBe('59 分钟前')
    expect(fmtRelative(NOW - HOUR, NOW)).toBe('1 小时前')
    expect(fmtRelative(NOW - 23 * HOUR, NOW)).toBe('23 小时前')
    expect(fmtRelative(NOW - DAY, NOW)).toBe('1 天前')
    expect(fmtRelative(NOW - 6 * DAY, NOW)).toBe('6 天前')
  })

  it('满 7 天退化为日期,跨年份补年份', () => {
    expect(fmtRelative(NOW - 7 * DAY, NOW)).toBe('9 月 10 日')
    expect(fmtRelative(new Date('2025-12-31T08:00:00').getTime(), NOW)).toBe('2025 年 12 月 31 日')
  })
})

describe('fmtClock', () => {
  it('输出 HH:mm,未知时间返回空串', () => {
    expect(fmtClock(new Date('2026-09-17T14:22:00').getTime())).toBe('14:22')
    expect(fmtClock(new Date('2026-09-17T09:05:00').getTime())).toBe('09:05')
    expect(fmtClock(0)).toBe('')
    expect(fmtClock(Number.NaN)).toBe('')
  })
})