/**
 * SSE 传输层(契约 §三;实现以 ARCHITECTURE §4.2 为准,另加静默看门狗)。
 *
 * - 纯传输:不认识 store / 会话,只把帧搬给 handlers(唯一调用方 = 模块 07 useChatStream);
 * - POST 不能用 EventSource:fetch + ReadableStream 手工分帧;
 * - 纯函数 splitFrames / parseFrame 可单测(模块 05 task2);
 * - BASE 统一取自 @/api/http(全项目唯一拼接处,此处不重复读环境变量);
 * - 不设总超时:静默看门狗 120s,每收到数据重置(首轮惰性装配图几十秒内不误杀)。
 */
import type { ErrorEvent, InterruptEnvelope, RoutePayload, UsageEvent } from '@/types/chat'

import { BASE } from './http'

/** 五类事件 + unknown 兜底(未知键记录后忽略,不中断流)。 */
export type SseEvent =
  | { type: 'token'; data: string }
  | { type: 'route'; data: RoutePayload }
  | { type: 'interrupt'; data: InterruptEnvelope }
  | { type: 'usage'; data: UsageEvent }
  | { type: 'error'; data: ErrorEvent }
  | { type: 'unknown'; data: unknown }

/**
 * 把累计缓冲切成完整帧;返回剩余的不完整尾巴。
 * 关键:先归一化 CRLF。某些代理会把 \n\n 变成 \r\n\r\n,
 * 只按 '\n\n' 切会永远切不开,表现为"流不结束、界面无输出"。
 */
export function splitFrames(buf: string): { frames: string[]; rest: string } {
  const normalized = buf.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const rest = parts.pop() ?? ''
  return { frames: parts, rest }
}

/** 解析单个 SSE 帧;注释帧/心跳/坏 JSON 返回 null,由调用方计数。 */
export function parseFrame(raw: string): SseEvent | null {
  const dataLines = raw
    .split('\n')
    .filter((l) => l.startsWith('data:'))
    .map((l) => l.slice(5).replace(/^ /, ''))
  if (dataLines.length === 0) return null
  let obj: Record<string, unknown>
  try {
    obj = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  } catch {
    return null // 半帧/损坏帧:丢弃,不断流
  }
  const key = Object.keys(obj)[0]
  if (!key) return null
  const data = obj[key]
  switch (key) {
    case 'token':
      return { type: 'token', data: String(data) }
    case 'route':
      return { type: 'route', data: data as RoutePayload }
    case 'interrupt':
      return { type: 'interrupt', data: data as InterruptEnvelope }
    case 'usage':
      return { type: 'usage', data: data as UsageEvent }
    case 'error':
      return { type: 'error', data: data as ErrorEvent }
    default:
      return { type: 'unknown', data }
  }
}

export interface SseHandlers {
  onToken?: (t: string) => void
  onRoute?: (r: RoutePayload) => void
  onInterrupt?: (i: InterruptEnvelope) => void
  onUsage?: (u: UsageEvent) => void
  /** 流内 error 帧(B4 已落地) */
  onErrorEvent?: (e: ErrorEvent) => void
  /** 传输层错误:非 2xx / 无 body / 网络中断 / 静默超时 */
  onError?: (e: SseError) => void
  /** 流正常结束(挂起也算:服务端本轮流就此打住) */
  onDone?: () => void
}

export class SseError extends Error {
  constructor(
    public kind: 'http' | 'network' | 'nobody' | 'parse',
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'SseError'
  }
}

/** 静默看门狗:连续 120s 未收到任何数据视为卡死(每收到数据重置,不设总超时)。 */
const WATCHDOG_MS = 120_000

export async function sseFetch(
  path: string,
  body: unknown,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    handlers.onError?.(new SseError('network', 0, '无法连接后端,请确认服务已启动'))
    return
  }

  if (!res.ok) {
    // 非 2xx:后端在 StreamingResponse 之前抛了 HTTPException,body 是普通 JSON
    let detail = `HTTP ${res.status}`
    try {
      const data = (await res.json()) as { detail?: unknown }
      if (typeof data?.detail === 'string') detail = data.detail
      else if (data?.detail) detail = JSON.stringify(data.detail)
    } catch {
      /* 非 JSON 错误体:保留状态码文案 */
    }
    handlers.onError?.(new SseError('http', res.status, detail))
    return
  }
  if (!res.body) {
    handlers.onError?.(new SseError('nobody', res.status, '响应没有可读流'))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  let badFrames = 0
  let timedOut = false

  let watchdog: ReturnType<typeof setTimeout> | undefined
  const resetWatchdog = (): void => {
    if (watchdog !== undefined) clearTimeout(watchdog)
    watchdog = setTimeout(() => {
      timedOut = true
      handlers.onError?.(new SseError('network', 0, '静默超时:120 秒未收到任何数据,已停止读取'))
      reader.cancel().catch(() => {})
    }, WATCHDOG_MS)
  }
  resetWatchdog()

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      resetWatchdog()
      // 必须 { stream: true }:中文 3 字节,网络分片劈开多字节字符会出乱码(坑 1)
      buf += decoder.decode(value, { stream: true })

      const { frames, rest } = splitFrames(buf)
      buf = rest
      for (const raw of frames) {
        const ev = parseFrame(raw)
        if (!ev) {
          badFrames += 1
          continue
        }
        switch (ev.type) {
          case 'token':
            handlers.onToken?.(ev.data)
            break
          case 'route':
            handlers.onRoute?.(ev.data)
            break
          case 'interrupt':
            handlers.onInterrupt?.(ev.data)
            break
          case 'usage':
            handlers.onUsage?.(ev.data)
            break
          case 'error':
            handlers.onErrorEvent?.(ev.data)
            break
          case 'unknown':
            console.warn('[sse] 未知事件类型', ev.data)
            break
        }
      }
    }
    if (!timedOut) {
      buf += decoder.decode() // 冲掉解码器内部残留
      if (buf.trim()) {
        const ev = parseFrame(buf)
        if (ev?.type === 'token') handlers.onToken?.(ev.data)
      }
      if (badFrames > 0) console.warn(`[sse] 丢弃了 ${badFrames} 个无法解析的帧`)
    }
  } catch (e) {
    if (timedOut) return
    if (e instanceof DOMException && e.name === 'AbortError') return
    handlers.onError?.(new SseError('network', 0, '流读取中断'))
    return
  } finally {
    if (watchdog !== undefined) clearTimeout(watchdog)
    reader.releaseLock()
  }
  if (timedOut) return
  handlers.onDone?.()
}