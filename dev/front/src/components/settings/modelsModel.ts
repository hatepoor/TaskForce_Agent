/**
 * 模型设置节的纯逻辑:字段分组 / 草稿校验 / 掩码判定 / 变更比较。
 * 组件只管渲染与请求,判断全在这里(便于单测,与 mcpModel/healthModel 同约定)。
 */
import type { ModelConfigValues, ModelField } from '@/types/models'

export interface ModelFieldSpec {
  field: ModelField
  label: string
  placeholder: string
  /** 密码框 + 掩码提示 */
  secret?: boolean
}

export interface ModelGroup {
  key: string
  title: string
  hint: string
  fields: readonly ModelFieldSpec[]
}

/** 六个字段分两张卡:主模型 / Embedding。 */
export const MODEL_GROUPS: readonly ModelGroup[] = [
  {
    key: 'llm',
    title: '主模型(对话)',
    hint: 'supervisor 路由、answer 汇总与三个子智能体共用',
    fields: [
      {
        field: 'llm_base_url',
        label: 'base_url',
        placeholder: 'https://ark.cn-beijing.volces.com/api/v3',
      },
      {
        field: 'llm_api_key',
        label: 'api_key',
        placeholder: '显示的是掩码;留空=清除覆盖,回落 .env',
        secret: true,
      },
      { field: 'llm_model', label: '模型名', placeholder: 'doubao-seed-1-6-250615' },
    ],
  },
  {
    key: 'embedding',
    title: 'Embedding(向量)',
    hint: '知识库入库与检索用;换模型可能改变向量维度,重建索引才生效',
    fields: [
      { field: 'embedding_base_url', label: 'base_url', placeholder: 'https://open.bigmodel.cn/api/paas/v4' },
      {
        field: 'embedding_api_key',
        label: 'api_key',
        placeholder: '显示的是掩码;留空=清除覆盖,回落 .env',
        secret: true,
      },
      { field: 'embedding_model', label: '模型名', placeholder: 'embedding-3' },
    ],
  },
]

export const FIELD_LABELS: Record<ModelField, string> = {
  llm_base_url: '主模型 base_url',
  llm_api_key: '主模型 api_key',
  llm_model: '主模型名',
  embedding_base_url: 'Embedding base_url',
  embedding_api_key: 'Embedding api_key',
  embedding_model: 'Embedding 模型名',
}

const URL_FIELDS: readonly ModelField[] = ['llm_base_url', 'embedding_base_url']

/** 全空草稿(加载前的初始态)。 */
export function emptyValues(): ModelConfigValues {
  return {
    llm_base_url: '',
    llm_api_key: '',
    llm_model: '',
    embedding_base_url: '',
    embedding_api_key: '',
    embedding_model: '',
  }
}

/**
 * 提交前本地校验(与后端同规则,先拦一道少一次往返):
 * base_url 非空时必须 http(s);其余字段留空合法(= 清除覆盖,回落 .env)。
 */
export function validateValues(values: ModelConfigValues): string {
  for (const field of URL_FIELDS) {
    const v = values[field].trim()
    if (v !== '' && !/^https?:\/\/.+/.test(v)) {
      return `${FIELD_LABELS[field]} 需以 http:// 或 https:// 开头`
    }
  }
  return ''
}

/** 掩码占位判定(与后端 is_masked 同规则):原样回传即表示"不改动"。 */
export function isMaskedKey(value: string): boolean {
  return value.includes('****')
}

/** 清空某组三项(恢复 .env 默认 = 提交空串清除覆盖)。 */
export function clearGroup(values: ModelConfigValues, groupKey: string): ModelConfigValues {
  const group = MODEL_GROUPS.find((g) => g.key === groupKey)
  const next = { ...values }
  if (group === undefined) return next
  for (const f of group.fields) next[f.field] = ''
  return next
}

/** 草稿与已加载值是否一致(保存按钮的禁用判据)。 */
export function sameValues(a: ModelConfigValues, b: ModelConfigValues): boolean {
  return (Object.keys(a) as ModelField[]).every((k) => a[k] === b[k])
}

/**
 * 只提交发生变化的字段(后端契约:缺项 = 不动)。
 * 清空的项发空串(清除覆盖,回落 .env),改动的发新值,没动的不发——
 * 全量提交会把 .env 现值顺手复制成覆盖,日后改 .env 会被静默压住。
 * 密钥项未动时草稿里是掩码(与 loaded 相同)→ 自然不进 patch,不会被冲掉。
 */
export function diffValues(
  draft: ModelConfigValues,
  loaded: ModelConfigValues,
): Partial<ModelConfigValues> {
  const out: Partial<ModelConfigValues> = {}
  for (const k of Object.keys(draft) as ModelField[]) {
    const value = draft[k]
    if (value !== loaded[k]) out[k] = value
  }
  return out
}