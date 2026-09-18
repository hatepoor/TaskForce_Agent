import { describe, expect, it } from 'vitest'

import type { MemoryItem as MemoryRecord } from '@/types/memory'

import {
  MEMORY_LIMIT,
  countText,
  filterMemories,
  fmtMemoryAbsolute,
  fmtMemoryTime,
  limitHint,
  parseIsoMs,
  sortByCreatedAtDesc,
  sourceMeta,
} from './memoryFormat'

/** 本地时区构造 ISO 串:断言与运行机器时区无关 */
function localIso(y: number, mo: number, d: number, h: number, mi: number): string {
  return new Date(y, mo - 1, d, h, mi).toISOString()
}

const NOW = new Date(2026, 8, 17, 12, 0).getTime() // 2026-09-17 12:00 本地时间

function mem(key: string, content: string, created: string, source: MemoryRecord['source'] = 'explicit'): MemoryRecord {
  return { key, content, source, created_at: created }
}

describe('sourceMeta', () => {
  it('explicit / confirmed 映射为不同中文徽标(两值必须可区分)', () => {
    expect(sourceMeta('explicit').label).toBe('用户明示')
    expect(sourceMeta('confirmed').label).toBe('自动确认')
    expect(sourceMeta('explicit').kind).toBe('explicit')
    expect(sourceMeta('confirmed').kind).toBe('confirmed')
    expect(sourceMeta('explicit').label).not.toBe(sourceMeta('confirmed').label)
    expect(sourceMeta('explicit').hint).not.toBe(sourceMeta('confirmed').hint)
  })

  it('缺失 / 未知值落到 unknown,不抛错', () => {
    for (const bad of ['', 'unknown', 'EXPLICIT']) {
      expect(sourceMeta(bad).kind).toBe('unknown')
      expect(sourceMeta(bad).label).toBe('来源未知')
    }
  })
})

describe('parseIsoMs / 时间文案', () => {
  it('合法 ISO(含微秒与 +00:00 偏移)解析为毫秒', () => {
    const iso = localIso(2026, 9, 9, 16, 52)
    expect(parseIsoMs(iso)).toBe(new Date(2026, 8, 9, 16, 52).getTime())
  })

  it('缺失 / 空串 / 非法值一律为 0,文案降级为空串', () => {
    for (const bad of ['', 'not-a-date']) {
      expect(parseIsoMs(bad)).toBe(0)
      expect(fmtMemoryTime(bad, NOW)).toBe('')
      expect(fmtMemoryAbsolute(bad)).toBe('')
    }
  })

  it('相对时间按本地时区换算,并沿用 fmtRelative 的分档', () => {
    expect(fmtMemoryTime(localIso(2026, 9, 17, 11, 30), NOW)).toBe('30 分钟前')
    expect(fmtMemoryTime(localIso(2026, 9, 16, 12, 0), NOW)).toBe('1 天前')
    expect(fmtMemoryTime(localIso(2026, 9, 1, 12, 0), NOW)).toBe('9 月 1 日')
  })

  it('绝对时间用于悬停提示,未知时间返回空串', () => {
    expect(fmtMemoryAbsolute(localIso(2026, 9, 9, 16, 52))).toBe('2026-09-09 16:52')
    expect(fmtMemoryAbsolute(localIso(2026, 9, 9, 8, 5))).toBe('2026-09-09 08:05')
  })
})

describe('sortByCreatedAtDesc', () => {
  it('按 created_at 降序,且不改动入参', () => {
    const items = [
      mem('a', '早', localIso(2026, 9, 1, 10, 0)),
      mem('b', '晚', localIso(2026, 9, 9, 10, 0)),
      mem('c', '中', localIso(2026, 9, 5, 10, 0)),
    ]
    expect(sortByCreatedAtDesc(items).map((it) => it.key)).toEqual(['b', 'c', 'a'])
    expect(items.map((it) => it.key)).toEqual(['a', 'b', 'c'])
  })

  it('时间缺失 / 非法的条目排到最后,且彼此保持原相对顺序', () => {
    const items = [
      mem('no-time-1', '缺时间', ''),
      mem('ok', '有时间', localIso(2026, 9, 9, 10, 0)),
      mem('bad', '坏时间', 'oops'),
      mem('no-time-2', '也缺时间', ''),
    ]
    expect(sortByCreatedAtDesc(items).map((it) => it.key)).toEqual(['ok', 'no-time-1', 'bad', 'no-time-2'])
  })

  it('全部缺时间时保持原顺序', () => {
    const items = [mem('a', 'x', ''), mem('b', 'y', ''), mem('c', 'z', '')]
    expect(sortByCreatedAtDesc(items).map((it) => it.key)).toEqual(['a', 'b', 'c'])
  })
})

describe('filterMemories', () => {
  const items = [
    mem('m_1', '用户偏好用 uv 管理 Python 依赖', localIso(2026, 9, 9, 10, 0)),
    mem('m_2', '用户的开发机是 Windows', localIso(2026, 9, 8, 10, 0)),
    mem('m_3', '用户在做 LangGraph 练手项目', localIso(2026, 9, 7, 10, 0)),
  ]

  it('空 / 全空白关键字返回全部(副本)', () => {
    expect(filterMemories(items, '')).toHaveLength(3)
    expect(filterMemories(items, '   ')).toHaveLength(3)
    const out = filterMemories(items, '')
    expect(out).not.toBe(items)
  })

  it('按子串匹配正文,大小写不敏感,前后空白忽略', () => {
    expect(filterMemories(items, 'uv').map((it) => it.key)).toEqual(['m_1'])
    expect(filterMemories(items, 'langgraph').map((it) => it.key)).toEqual(['m_3'])
    expect(filterMemories(items, '  Windows  ').map((it) => it.key)).toEqual(['m_2'])
    expect(filterMemories(items, '用户').map((it) => it.key)).toEqual(['m_1', 'm_2', 'm_3'])
  })

  it('匹配不到返回空数组;不匹配 key 字段(正文之外的字段不参与)', () => {
    expect(filterMemories(items, '不存在的关键字')).toEqual([])
    expect(filterMemories(items, 'm_2')).toEqual([])
  })
})

describe('countText / limitHint', () => {
  it('条数文案:未过滤只报总数,过滤生效补匹配数,空列表给"暂无记忆"', () => {
    expect(countText(4, 4)).toBe('4 条')
    expect(countText(4, 1)).toBe('4 条 · 匹配 1 条')
    expect(countText(4, 0)).toBe('4 条 · 匹配 0 条')
    expect(countText(0, 0)).toBe('暂无记忆')
  })

  it('命中后端上限(100)才提示,未命中为空串', () => {
    expect(limitHint(MEMORY_LIMIT - 1)).toBe('')
    expect(limitHint(MEMORY_LIMIT)).toContain('100 条')
    expect(MEMORY_LIMIT).toBe(100)
  })
})