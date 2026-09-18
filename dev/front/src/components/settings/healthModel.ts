/**
 * Health 数据归一化(纯函数,可单测;契约 API-CONTRACT §2.2 + UI-DESIGN §4.4)。
 *
 * 两条硬约束:
 * 1. `sandbox` **值域不封闭**(`unknown` | `ok` | `sandbox_health()` 的 error 文本 | `unreachable`),
 *    一律按"非 `ok` 即异常"处理,禁精确匹配其他值——后端随时可能多一个新值;
 * 2. `db` 异常时内嵌**完整异常文本**(`"error: {异常信息}"`),必须原样展示:
 *    本地工具里错误信息越直白越好。
 */
import type { HealthStatus } from '@/api/health'

/** 状态灯四态(与 common/StatusDot.vue 对齐)。 */
export type DotState = 'ok' | 'warn' | 'err' | 'unknown'

export type HealthKey = 'status' | 'db' | 'sandbox'

export interface HealthCardModel {
  key: HealthKey
  label: string
  state: DotState
  /** 卡片主值:后端原文本直出(status / db / sandbox 三个字段原文)。 */
  value: string
  /** 一行补充说明(解释这个字段意味着什么)。 */
  detail: string
}

/** 取值优先级:err > warn > unknown > ok(用于把三张卡聚合成导航轨的一个点)。 */
const RANK: Record<DotState, number> = { ok: 0, unknown: 1, warn: 2, err: 3 }

/** `ok` 判定:去空白 + 忽略大小写(后端固定小写,防御式兜底)。 */
export function isOkValue(v: unknown): boolean {
  return typeof v === 'string' && v.trim().toLowerCase() === 'ok'
}

/** status:`ok` 绿 / `degraded` 黄(DB 异常导致降级)/ 未知值域灰。 */
export function statusState(status: string): DotState {
  if (isOkValue(status)) return 'ok'
  if (status.trim().toLowerCase() === 'degraded') return 'warn'
  return 'unknown'
}

/** db:`ok` 绿;其余必为 `"error: …"` 文本,一律红(数据库不可用是硬故障)。 */
export function dbState(db: string): DotState {
  return isOkValue(db) ? 'ok' : 'err'
}

/** sandbox:非 `ok` 即异常(值域不封闭,不精确匹配 `unknown` / `unreachable`)。 */
export function sandboxState(sandbox: string): DotState {
  return isOkValue(sandbox) ? 'ok' : 'warn'
}

/** 多个状态取最差(聚合用)。 */
export function worstState(states: readonly DotState[]): DotState {
  let out: DotState = 'ok'
  for (const s of states) {
    if (RANK[s] > RANK[out]) out = s
  }
  return out
}

/** 三张卡的模型顺序固定:状态 / 数据库 / 沙箱。 */
export function healthCards(h: HealthStatus | null): HealthCardModel[] {
  if (h === null) return []
  return [
    {
      key: 'status',
      label: '状态',
      state: statusState(h.status),
      value: h.status,
      detail: isOkValue(h.status) ? '后端存活' : '数据库异常,服务已降级',
    },
    {
      key: 'db',
      label: '数据库',
      state: dbState(h.db),
      value: h.db,
      detail: isOkValue(h.db) ? 'PostgreSQL 连通' : '数据库不可用:会话与记忆均不可读写',
    },
    {
      key: 'sandbox',
      label: '沙箱',
      state: sandboxState(h.sandbox),
      value: h.sandbox,
      detail: isOkValue(h.sandbox) ? '远程沙箱可达' : '沙箱非 ok 即异常,代码执行能力可能不可用',
    },
  ]
}

/** 导航轨状态点:三字段取最差;无数据(尚未拉到 / 拉取失败)为灰。 */
export function overallState(h: HealthStatus | null): DotState {
  if (h === null) return 'unknown'
  return worstState([statusState(h.status), dbState(h.db), sandboxState(h.sandbox)])
}

/** 导航轨 tooltip 文案:db / sandbox 明细原文本直出。 */
export function healthTooltip(h: HealthStatus | null): string {
  if (h === null) return '尚未取到健康状态'
  return `db: ${h.db} · sandbox: ${h.sandbox}`
}