import { describe, expect, it } from 'vitest'

import { ApiError, BASE, errText } from './http'

describe('errText', () => {
  it('detail 为字符串:原文返回', () => {
    expect(errText(new ApiError(400, '该会话没有待处理的挂起'))).toBe('该会话没有待处理的挂起')
  })

  it('detail 为 FastAPI 422 的 object[]:拼接各项 msg', () => {
    const e = new ApiError(422, [{ msg: 'field required' }, { msg: 'not a valid integer' }])
    expect(errText(e)).toBe('field required;not a valid integer')
  })

  it('detail 为对象或缺失:序列化 / 状态码兜底,不出现 undefined', () => {
    expect(errText(new ApiError(500, { foo: 'bar' }))).toBe('{"foo":"bar"}')
    expect(errText(new ApiError(500, undefined))).toBe('请求失败(HTTP 500)')
  })

  it('普通 Error 与未知值:返回可读文案', () => {
    expect(errText(new Error('boom'))).toBe('boom')
    expect(errText('oops')).toBe('oops')
  })
})

describe('ApiError', () => {
  it('name / status / detail 正确暴露,可被 instanceof 捕获', () => {
    const e = new ApiError(404, 'not found')
    expect(e).toBeInstanceOf(Error)
    expect(e).toBeInstanceOf(ApiError)
    expect(e.name).toBe('ApiError')
    expect(e.status).toBe(404)
    expect(e.detail).toBe('not found')
  })
})

describe('BASE', () => {
  it('类型安全:测试环境无 VITE_API_BASE 时兜底为空串(非 undefined)', () => {
    expect(typeof BASE).toBe('string')
  })
})