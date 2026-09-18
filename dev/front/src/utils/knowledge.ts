/**
 * 知识库页(模块 09)纯函数与常量:体积预检 / 展示格式化 / 上传队列状态推导。
 * 只放纯函数(node 环境可直测);网络与组件状态不放这里。
 */
import type { KDoc } from '@/types/knowledge'

/** 后端单文件上限(契约 §2.3):前端先拦一次。 */
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

/** 与后端 400 detail 原文一致:双保险两边文案相同,用户看不出差别。 */
export const OVERSIZE_MSG = '文件超过 20MB 上限'

/** 删除不存在的文档时的过渡文案(B7 落地前后端返 500,落地后返 404,契约 §1.3)。 */
export const DOC_GONE_MSG = '该文档可能已不存在,已刷新列表'

/** doc_id 内联"已复制"反馈时长(UI-DESIGN §6.3)。 */
export const COPY_FEEDBACK_MS = 1500

/** 上传成功后的列表新行高亮时长(UI-DESIGN §4.1)。 */
export const NEW_DOC_HIGHLIGHT_MS = 2000

/** 队列四态:排队 / 上传中 / 已入库 / 失败。 */
export type UploadState = 'queued' | 'uploading' | 'done' | 'failed'

export interface UploadItem {
  /** 本地自增 id:同一文件可重复入队,不能拿文件名当 key */
  id: number
  name: string
  size: number
  state: UploadState
  /** 0..100 */
  percent: number
  /** 失败原因(errText 原文);成功项留空,完成文案由 doneText 现算 */
  message: string
  /** 成功后回填 */
  docId: string
  /** 成功后回填:false = 内容判重命中,不是错误(契约 §2.3) */
  created: boolean
}

/** 超限判定:严格大于 20MB 放行边界与后端 `len(content) > 20MB` 同义。 */
export function isOversize(size: number): boolean {
  return size > MAX_UPLOAD_BYTES
}

/** 入队项:超限的直接落 failed(不发请求),其余排队等串行推进。 */
export function makeQueueItem(file: { name: string; size: number }, id: number): UploadItem {
  const oversize = isOversize(file.size)
  return {
    id,
    name: file.name,
    size: file.size,
    state: oversize ? 'failed' : 'queued',
    percent: 0,
    message: oversize ? OVERSIZE_MSG : '',
    docId: '',
    created: false,
  }
}

/** 串行推进:下一个待发项的下标;-1 表示没有(重试会把 failed 改回 queued 再来一轮)。 */
export function nextQueuedIndex(items: readonly UploadItem[]): number {
  return items.findIndex((it) => it.state === 'queued')
}

/** XHR 进度归一:total 为 0(无 Content-Length)时给 0,不显示假进度。 */
export function progressPercent(loaded: number, total: number): number {
  if (!Number.isFinite(total) || total <= 0) return 0
  const pct = Math.round((loaded / total) * 100)
  return Math.min(100, Math.max(0, pct))
}

/** 上传中文案:请求体发完后后端还在解析 + embedding,别让进度条看起来卡死。 */
export function progressText(percent: number): string {
  return percent >= 100 ? '解析入库中…' : `上传中 ${percent}%`
}

/**
 * 完成文案:`created: false` 是内容判重命中(复用已有 doc_id),不算失败也不算普通成功。
 * 切片数取自上传后刷新的列表,拿不到就只显示前半句。
 */
export function doneText(created: boolean, chunks: number | undefined): string {
  const head = created ? '已入库' : '已存在,已复用'
  if (chunks === undefined || !Number.isFinite(chunks)) return head
  return `${head} · ${chunks} 切片`
}

/** 删除失败的状态码分支:B7 落地前删不存在的文档是 500、落地后是 404,两者同一处理。 */
export function isDocGoneStatus(status: number): boolean {
  return status === 404 || status === 500
}

/** 体积展示(队列行用):B / KB / MB,1 位小数并去掉多余的 .0。 */
export function fmtBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0B'
  const kb = 1024
  const mb = kb * 1024
  if (n < kb) return `${Math.round(n)}B`
  if (n < mb) return `${trimZero(n / kb)}KB`
  return `${trimZero(n / mb)}MB`
}

function trimZero(v: number): string {
  return v.toFixed(1).replace(/\.0$/, '')
}

/** 入库时间:后端给带时区偏移的 ISO 8601,这里按浏览器本地时区显示 `MM-DD HH:mm`。 */
export function fmtDateTime(iso: string): string {
  const ts = Date.parse(iso)
  if (!Number.isFinite(ts)) return ''
  const d = new Date(ts)
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** doc_id 展示:32 位 hex 截前 8 位 + 省略号(UI-DESIGN §4.1 线框);复制始终给完整值。 */
export function shortDocId(docId: string): string {
  return docId.length <= 8 ? docId : `${docId.slice(0, 8)}…`
}

/** 列表排序:契约已按 created_at 升序,这里防御性重排(缺失/非法时间视为最早,稳定排序)。 */
export function sortDocsByCreatedAt(docs: readonly KDoc[]): KDoc[] {
  return [...docs].sort((a, b) => tsOf(a.created_at) - tsOf(b.created_at))
}

function tsOf(iso: string): number {
  const t = Date.parse(iso)
  return Number.isFinite(t) ? t : 0
}