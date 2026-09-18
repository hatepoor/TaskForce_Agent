/**
 * 后台任务轮询的决策表单测(纯函数,node 环境)。
 * 覆盖三条硬语义:全批才汇总(半批等)、用户轮优先(流式中让位)、结果已被消费就收工。
 */
import { describe, expect, it } from 'vitest'

import { decideStatus } from './useTaskWatch'

describe('decideStatus(轮询一拍怎么处置)', () => {
  it('还有任务未完成:等全批,不发起汇总', () => {
    expect(decideStatus({ pending: 1, done: 2 }, false)).toBe('wait')
    expect(decideStatus({ pending: 3, done: 0 }, false)).toBe('wait')
  })

  it('全批完成且有结果:发起自动汇总', () => {
    expect(decideStatus({ pending: 0, done: 3 }, false)).toBe('summarize')
  })

  it('用户轮正在流式:让位,下一拍再来(用户优先,对应 REPL turn_lock)', () => {
    expect(decideStatus({ pending: 0, done: 3 }, true)).toBe('wait')
  })

  it('全批完成但无待汇总结果:清位收工(结果已被别的轮次消费)', () => {
    expect(decideStatus({ pending: 0, done: 0 }, false)).toBe('clear')
    expect(decideStatus({ pending: 0, done: 0 }, true)).toBe('clear')
  })
})