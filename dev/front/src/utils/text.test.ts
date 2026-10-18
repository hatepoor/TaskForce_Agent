import { describe, expect, it } from 'vitest'

import { normalizeInterruptText } from './text'

describe('normalizeInterruptText', () => {
  it('把字面量 \\n / \\r\\n / \\t 还原成真实控制字符', () => {
    expect(normalizeInterruptText('第一行\\n第二行')).toBe('第一行\n第二行')
    expect(normalizeInterruptText('a\\r\\nb')).toBe('a\nb')
    expect(normalizeInterruptText('a\\tb')).toBe('a\tb')
  })

  it('已有真实换行的文本保持原样', () => {
    expect(normalizeInterruptText('第一行\n第二行')).toBe('第一行\n第二行')
  })
})
