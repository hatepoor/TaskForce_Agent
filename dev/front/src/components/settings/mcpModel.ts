/**
 * MCP 表单 / 列表的纯逻辑层(可单测;契约 API-CONTRACT §2.6 + UI-DESIGN §4.2)。
 *
 * 三处契约坑位:
 * 1. **切换 transport 不丢草稿**:stdio / http 各维护一份草稿,提交时只取当前类型字段,
 *    但 `transport` 必带(discriminator,缺了后端直接 422);
 * 2. **未设置字段整个缺失**:后端 `model_dump(exclude_none=True)`,`args` / `env` / `headers`
 *    可能整个键不存在,渲染与摘要全部按可选处理;
 * 3. **tools 形状未归一化**(B8 落地前):可能 `string[]` 也可能对象数组,渲染必须防御式。
 */
import type { HttpServer, MCPServerConfig, MCPTestResult, StdioServer } from '@/types/mcp'

export type Transport = 'stdio' | 'http'

/** 名称正则:与后端 `_check_name` 同源(`^[a-z0-9_-]+$`)。 */
export const NAME_RE = /^[a-z0-9_-]+$/

/** 分区控件默认值(UI-DESIGN §4.2)。 */
export const DEFAULT_TRANSPORT: Transport = 'stdio'

/** 键值对行编辑器的单行(env / headers 共用)。 */
export interface KeyValueRow {
  key: string
  value: string
}

export interface StdioDraft {
  command: string
  /** 参数多行文本:提交时按空白切分(UI-DESIGN §4.2)。 */
  argsText: string
  env: KeyValueRow[]
}

export interface HttpDraft {
  url: string
  headers: KeyValueRow[]
}

/** 新增表单的全部草稿:两份子草稿一直并存,切换 transport 只改 `transport` 字段。 */
export interface McpFormDraft {
  name: string
  transport: Transport
  stdio: StdioDraft
  http: HttpDraft
}

export function emptyRow(): KeyValueRow {
  return { key: '', value: '' }
}

export function emptyDraft(): McpFormDraft {
  return {
    name: '',
    transport: DEFAULT_TRANSPORT,
    stdio: { command: '', argsText: '', env: [] },
    http: { url: '', headers: [] },
  }
}

/** args 文本 → 数组:按任意空白(含换行)切分,丢空段。 */
export function splitArgs(text: string): string[] {
  return text.split(/\s+/).filter((s) => s !== '')
}

/** 键值对行 → 对象:键为空的整行跳过;重复键后者覆盖前者。 */
export function rowsToRecord(rows: readonly KeyValueRow[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const row of rows) {
    const k = row.key.trim()
    if (k === '') continue
    out[k] = row.value
  }
  return out
}

/** 有值但没键的行:属填写错误,提交前拦下(纯空行则是没填完的空槽,忽略)。 */
export function hasEmptyKeyRow(rows: readonly KeyValueRow[]): boolean {
  return rows.some((r) => r.key.trim() === '' && r.value.trim() !== '')
}

/** 提交前校验:返回错误文案(`''` = 通过)。 */
export function validateDraft(d: McpFormDraft): string {
  const name = d.name.trim()
  if (name === '') return '名称不能为空'
  if (!NAME_RE.test(name)) return '名称只能包含小写字母、数字、下划线、连字符(如 github-mcp)'

  if (d.transport === 'stdio') {
    if (d.stdio.command.trim() === '') return '命令不能为空(如 npx)'
    if (hasEmptyKeyRow(d.stdio.env)) return '环境变量存在空键:请填写键名或删除该行'
    return ''
  }

  const url = d.http.url.trim()
  if (url === '') return 'URL 不能为空'
  if (!/^https?:\/\//i.test(url)) return 'URL 必须以 http:// 或 https:// 开头'
  if (hasEmptyKeyRow(d.http.headers)) return '请求头存在空键:请填写键名或删除该行'
  return ''
}

/** 提交体:只带当前 transport 的字段,且必带 `transport`;空的可选字段整个不发。 */
export function buildConfig(d: McpFormDraft): MCPServerConfig {
  if (d.transport === 'stdio') {
    const cfg: StdioServer = { transport: 'stdio', command: d.stdio.command.trim() }
    const args = splitArgs(d.stdio.argsText)
    if (args.length > 0) cfg.args = args
    const env = rowsToRecord(d.stdio.env)
    if (Object.keys(env).length > 0) cfg.env = env
    return cfg
  }

  const cfg: HttpServer = { transport: 'http', url: d.http.url.trim() }
  const headers = rowsToRecord(d.http.headers)
  if (Object.keys(headers).length > 0) cfg.headers = headers
  return cfg
}

/** 列表摘要:stdio 拼命令行(http 只有 URL);徽标即 transport 原文。 */
export function summarizeConfig(cfg: MCPServerConfig): { badge: Transport; summary: string } {
  if (cfg.transport === 'stdio') {
    return { badge: 'stdio', summary: [cfg.command, ...(cfg.args ?? [])].join(' ') }
  }
  return { badge: 'http', summary: cfg.url }
}

/** name → config 字典拍平成有序数组(按 name 升序,列表渲染不依赖对象键序)。 */
export interface ServerEntry {
  name: string
  config: MCPServerConfig
}

export function serverEntries(servers: Record<string, MCPServerConfig> | null | undefined): ServerEntry[] {
  if (servers === null || servers === undefined) return []
  return Object.entries(servers)
    .map(([name, config]) => ({ name, config }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

/** 是否重名(同名保存 = 后端静默覆盖,UI 层必须先二次确认)。 */
export function isDuplicateName(name: string, existing: readonly string[]): boolean {
  const n = name.trim()
  return n !== '' && existing.includes(n)
}

/** 覆盖确认弹窗正文(后端同名是静默覆盖,不是合并)。 */
export function overwriteMessage(name: string): string {
  return `已存在同名服务器「${name}」。保存会覆盖它的全部配置(不是合并),旧配置无法找回。是否继续?`
}

/** 删除确认弹窗正文(UI-DESIGN §4.2 文案)。 */
export function deleteMessage(name: string): string {
  return `将从 mcp_config.json 移除「${name}」;其工具在下次会话装配时不再可用。`
}

/**
 * 单个工具的展示标签(契约 §2.6 的防御式取值):
 * 字符串直接用;对象取 `name`;其余(数字 / null / 嵌套怪值)退化为 JSON 文本,绝不抛。
 */
export function toolLabel(t: unknown): string {
  if (typeof t === 'string') return t
  if (t !== null && typeof t === 'object') {
    const name = (t as { name?: unknown }).name
    if (typeof name === 'string' && name !== '') return name
  }
  try {
    return JSON.stringify(t) ?? String(t)
  } catch {
    return String(t)
  }
}

/** 工具列表归一化 + 截断(默认最多显示 8 个,其余折成"等 N 个")。 */
export function toolLabels(
  tools: readonly unknown[] | null | undefined,
  max = 8,
): { labels: string[]; more: number } {
  const all = (tools ?? []).map(toolLabel)
  return { labels: all.slice(0, max), more: Math.max(0, all.length - max) }
}

/** 测试结果视图模型:`ok:false` 是正常业务返回,文案不能写成红色系统错误。 */
export interface TestOutcome {
  ok: boolean
  /** 行内状态标签(未测试 / 测试中… / 已连通 · N 个工具 / 未连通)。 */
  badge: string
  /** 就地展开的明细行。 */
  detail: string
  labels: string[]
  more: number
}

export function testOutcome(result: MCPTestResult): TestOutcome {
  const { labels, more } = toolLabels(result.tools)
  if (!result.ok) {
    return {
      ok: false,
      badge: '未连通',
      detail: '无法连接:命令不存在、URL 不可达或启动超时',
      labels: [],
      more: 0,
    }
  }
  const n = result.tools?.length ?? 0
  return {
    ok: true,
    badge: n > 0 ? `已连通 · ${n} 个工具` : '已连通',
    detail: n > 0 ? '' : '连通但未发现任何工具(该服务器可能没有暴露 tool)',
    labels,
    more,
  }
}

/** 请求层超时判定(前端 30s 超时;后端内部 10s,超时说明对端没在时限内回话)。 */
export function isTimeoutError(e: unknown): boolean {
  return (
    (e instanceof DOMException && (e.name === 'TimeoutError' || e.name === 'AbortError')) ||
    (e instanceof Error && e.name === 'TimeoutError')
  )
}

/** 测试超时话术:别复用 errText 的 15s 默认超时提示(测试端点是 30s)。 */
export const TEST_TIMEOUT_TEXT = '测试超时(30 秒):远端 MCP 未在时限内响应,可稍后重试'