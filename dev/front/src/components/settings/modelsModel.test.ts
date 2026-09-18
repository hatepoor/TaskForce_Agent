import { describe, expect, it } from 'vitest'

import {
  MODEL_GROUPS,
  clearGroup,
  diffValues,
  emptyValues,
  isMaskedKey,
  sameValues,
  validateValues,
} from './modelsModel'

describe('模型设置节纯逻辑', () => {
  it('分组恰好覆盖六个字段且不重复', () => {
    const fields = MODEL_GROUPS.flatMap((g) => g.fields.map((f) => f.field))
    expect([...fields].sort()).toEqual([
      'embedding_api_key',
      'embedding_base_url',
      'embedding_model',
      'llm_api_key',
      'llm_base_url',
      'llm_model',
    ])
  })

  it('validateValues:base_url 非空时必须 http(s),留空合法(回落 .env)', () => {
    const v = emptyValues()
    expect(validateValues(v)).toBe('')

    v.llm_base_url = 'api.example.com/v1'
    expect(validateValues(v)).toContain('主模型 base_url')

    v.llm_base_url = 'https://api.example.com/v1'
    expect(validateValues(v)).toBe('')

    v.embedding_base_url = 'ftp://x'
    expect(validateValues(v)).toContain('Embedding base_url')
  })

  it('isMaskedKey:识别掩码占位(空串不算——空串是"清除覆盖")', () => {
    expect(isMaskedKey('sk-a****wxyz')).toBe(true)
    expect(isMaskedKey('sk-real-key')).toBe(false)
    expect(isMaskedKey('')).toBe(false)
  })

  it('clearGroup:只清该组三项且不改原对象', () => {
    const v = { ...emptyValues(), llm_api_key: 'sk-real', llm_model: 'm1', embedding_model: 'e1' }
    const next = clearGroup(v, 'llm')
    expect(next).toMatchObject({ llm_api_key: '', llm_model: '', embedding_model: 'e1' })
    expect(v.llm_model).toBe('m1')
  })

  it('sameValues:脏检查(保存按钮禁用判据)', () => {
    expect(sameValues(emptyValues(), emptyValues())).toBe(true)
    expect(sameValues({ ...emptyValues(), llm_model: 'x' }, emptyValues())).toBe(false)
  })

  it('diffValues:只带改动项(清空发空串、未动不发、密钥掩码不动不进包)', () => {
    const loaded = {
      ...emptyValues(),
      llm_model: 'm1',
      llm_api_key: 'sk-a****wxyz', // 服务端回显的掩码
      embedding_model: 'e1',
    }
    expect(diffValues(loaded, loaded)).toEqual({})

    const edited = { ...loaded, llm_model: 'm2', llm_base_url: 'https://x.example/v1' }
    expect(diffValues(edited, loaded)).toEqual({
      llm_model: 'm2',
      llm_base_url: 'https://x.example/v1',
    })

    const cleared = { ...loaded, llm_model: '' }
    expect(diffValues(cleared, loaded)).toEqual({ llm_model: '' }) // 清空 = 清除覆盖
  })
})