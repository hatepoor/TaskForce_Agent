import { describe, expect, it } from 'vitest'

import type { HealthStatus } from '@/api/health'

import {
  dbState,
  healthCards,
  healthTooltip,
  isOkValue,
  overallState,
  sandboxState,
  statusState,
  worstState,
} from './healthModel'

const OK: HealthStatus = { status: 'ok', db: 'ok', sandbox: 'ok' }

describe('isOkValue', () => {
  it('只有 ok(去空白/忽略大小写)算 ok', () => {
    expect(isOkValue('ok')).toBe(true)
    expect(isOkValue(' OK ')).toBe(true)
    expect(isOkValue('unknown')).toBe(false)
    expect(isOkValue('')).toBe(false)
    expect(isOkValue(undefined)).toBe(false)
    expect(isOkValue(1)).toBe(false)
  })
})

describe('statusState', () => {
  it('ok 绿 / degraded 黄 / 未知值灰', () => {
    expect(statusState('ok')).toBe('ok')
    expect(statusState('degraded')).toBe('warn')
    expect(statusState('weird')).toBe('unknown')
  })
})

describe('dbState', () => {
  it('非 ok 一律红(异常文本内嵌,值域只有 ok 与 error: …)', () => {
    expect(dbState('ok')).toBe('ok')
    expect(dbState('error: 连接串拒绝连接')).toBe('err')
    expect(dbState('')).toBe('err')
  })
})

describe('sandboxState', () => {
  it('非 ok 即异常,不精确匹配 unreachable / unknown', () => {
    expect(sandboxState('ok')).toBe('ok')
    expect(sandboxState('unreachable')).toBe('warn')
    expect(sandboxState('unknown')).toBe('warn')
    expect(sandboxState('连接超时')).toBe('warn')
    expect(sandboxState('未来新增的某个值')).toBe('warn')
  })
})

describe('worstState', () => {
  it('取最差:err > warn > unknown > ok', () => {
    expect(worstState(['ok', 'ok'])).toBe('ok')
    expect(worstState(['ok', 'unknown'])).toBe('unknown')
    expect(worstState(['unknown', 'warn'])).toBe('warn')
    expect(worstState(['warn', 'err', 'ok'])).toBe('err')
    expect(worstState([])).toBe('ok')
  })
})

describe('healthCards', () => {
  it('无数据返回空数组;正常态三卡全绿', () => {
    expect(healthCards(null)).toEqual([])
    const cards = healthCards(OK)
    expect(cards.map((c) => c.key)).toEqual(['status', 'db', 'sandbox'])
    expect(cards.every((c) => c.state === 'ok')).toBe(true)
  })

  it('DB 异常:status 黄、db 红,且异常文本原样直出', () => {
    const cards = healthCards({ status: 'degraded', db: 'error: 连接串拒绝连接', sandbox: 'ok' })
    expect(cards[0]?.state).toBe('warn')
    expect(cards[1]?.state).toBe('err')
    expect(cards[1]?.value).toBe('error: 连接串拒绝连接')
    expect(cards[2]?.state).toBe('ok')
  })

  it('sandbox 未配置(unreachable):黄点且原文本直出,不是红色错误', () => {
    const cards = healthCards({ status: 'ok', db: 'ok', sandbox: 'unreachable' })
    const sandbox = cards[2]
    expect(sandbox?.state).toBe('warn')
    expect(sandbox?.value).toBe('unreachable')
  })
})

describe('overallState / healthTooltip', () => {
  it('无数据显示灰点与提示文案', () => {
    expect(overallState(null)).toBe('unknown')
    expect(healthTooltip(null)).toBe('尚未取到健康状态')
  })

  it('DB 故障时导航轨点为红;沙箱异常为黄', () => {
    expect(overallState({ status: 'degraded', db: 'error: x', sandbox: 'ok' })).toBe('err')
    expect(overallState({ status: 'ok', db: 'ok', sandbox: 'unreachable' })).toBe('warn')
    expect(overallState(OK)).toBe('ok')
  })

  it('tooltip 直出 db / sandbox 原文本', () => {
    expect(healthTooltip({ status: 'degraded', db: 'error: 连接串拒绝连接', sandbox: 'unreachable' })).toBe(
      'db: error: 连接串拒绝连接 · sandbox: unreachable',
    )
  })
})