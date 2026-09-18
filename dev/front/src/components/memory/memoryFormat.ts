/**
 * 记忆页纯函数:排序 / 本地过滤 / source 文案 / 时间与条数文案。
 * 全部无副作用、不碰 DOM —— 可在 node 环境直接单测(见 memoryFormat.test.ts)。
 * 契约:API-CONTRACT §2.4(字段缺失时为 "")、§1.4(无分页,`/memory` 硬编码 limit=100)。
 */
import type { MemoryItem as MemoryRecord } from '@/types/memory'
import { fmtRelative } from '@/utils/time'

/** 后端固定返回条数上限(§1.4);达到该条数说明可能有更早的记忆未返回。 */
export const MEMORY_LIMIT = 100

export type SourceKind = 'explicit' | 'confirmed' | 'unknown'

export interface SourceMeta {
  /** 样式种类,对应徽标修饰类 */
  kind: SourceKind
  /** 徽标文案 */
  label: string
  /** 徽标释义(tooltip):两种写入路径不同,必须能区分 */
  hint: string
}

const SOURCE_META: Record<SourceKind, SourceMeta> = {
  explicit: {
    kind: 'explicit',
    label: '用户明示',
    hint: '你在对话里明说「记住…」,直接写入',
  },
  confirmed: {
    kind: 'confirmed',
    label: '自动确认',
    hint: '智能体自主提案,经你确认后写入',
  },
  unknown: {
    kind: 'unknown',
    label: '来源未知',
    hint: '后端未返回可识别的 source 字段',
  },
}

/** source → 徽标文案 + 样式种类;空串与未知值一律落到 unknown,不抛错。 */
export function sourceMeta(source: string): SourceMeta {
  if (source === 'explicit') return SOURCE_META.explicit
  if (source === 'confirmed') return SOURCE_META.confirmed
  return SOURCE_META.unknown
}

/** ISO 8601 → 毫秒时间戳;缺失 / 空串 / 非法一律返回 0(与 fmtRelative 的"未知时间"约定一致)。 */
export function parseIsoMs(iso: string): number {
  const ms = Date.parse(iso ?? '')
  return Number.isFinite(ms) ? ms : 0
}

/** 列表时间文案:相对时间(按本地时区渲染);未知时间返回空串,由调用方决定不渲染。 */
export function fmtMemoryTime(iso: string, now: number = Date.now()): string {
  return fmtRelative(parseIsoMs(iso), now)
}

/** 悬停提示用的绝对本地时间(如 `2026-09-09 16:52`);未知时间返回空串。 */
export function fmtMemoryAbsolute(iso: string): string {
  const ms = parseIsoMs(iso)
  if (ms === 0) return ''
  const d = new Date(ms)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * 按 created_at 降序。
 * 后端本身已降序,这里再排一次:不依赖服务端顺序,且时间缺失(0)的条目稳定落到末尾。
 */
export function sortByCreatedAtDesc(items: readonly MemoryRecord[]): MemoryRecord[] {
  return [...items].sort((a, b) => {
    const ta = parseIsoMs(a.created_at)
    const tb = parseIsoMs(b.created_at)
    if (ta === tb) return 0
    if (ta === 0) return 1
    if (tb === 0) return -1
    return tb - ta
  })
}

/**
 * 纯前端过滤:对 content 做大小写不敏感的 `includes` 匹配(后端无搜索参数,不假装成搜索接口)。
 * 关键字为空 / 全空白时原样返回全部条目。
 */
export function filterMemories(items: readonly MemoryRecord[], keyword: string): MemoryRecord[] {
  const kw = keyword.trim().toLowerCase()
  if (kw === '') return [...items]
  return items.filter((it) => (it.content ?? '').toLowerCase().includes(kw))
}

/** 条数文案:过滤生效时补上匹配数,避免"列表变短"被误读成丢数据。 */
export function countText(total: number, matched: number): string {
  if (total <= 0) return '暂无记忆'
  if (matched >= total) return `${total} 条`
  return `${total} 条 · 匹配 ${matched} 条`
}

/** 命中后端上限时的提示;未命中返回空串(配合 v-if 使用)。UI 不承诺"显示全部"。 */
export function limitHint(count: number): string {
  return count >= MEMORY_LIMIT
    ? `后端固定返回最近 ${MEMORY_LIMIT} 条(按创建时间降序),更早的记忆未在此列出。`
    : ''
}