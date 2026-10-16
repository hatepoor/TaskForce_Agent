# 4. SSE 客户端设计(上):约束与传输层

> 一句话: SSE 客户端四条约束与传输层 src/api/sse.ts 的帧切分 / 解析实现
> 体系: 前端文档 · ARCHITECTURE · SSE 设计分片
> 上游: [README](./README.md)
> 下游: [04b-SSE客户端设计-领域层与错误处理.md](./04b-SSE客户端设计-领域层与错误处理.md)
> 细节见: [手册索引](./README.md)

## 4. SSE 客户端设计

### 4.1 约束

1. **POST 不能用 `EventSource`**(只支持 GET、不能带 body,且自动重连对本项目有害——会重复触发一轮对话)。必须 `fetch` + `response.body.getReader()`。
2. 帧格式 `data: {json}\n\n`,JSON 单键对象,键名即事件类型;前端不需解析 `event:` 字段,但解析器按 SSE 规范兼容多行 `data:` 与注释行,防未来加心跳。
3. 事件五种(信封后):`token`(string)/ `route`(RoutePayload)/ `interrupt`(`{kind, text}` 对象,B3)/ `usage`(UsageEvent)/ `error`(B4,`{message, code?}`)。
4. 当前后端攒完再吐(B4 前),渲染层按"可能一次性到达一大批帧"设计(rAF 合并,§7 坑 5);解析器本就逐帧消费,B4 落地后零改动。

### 4.2 传输层:`src/api/sse.ts`

```ts
// 纯传输层,不含业务语义,便于单测
import type { RoutePayload, InterruptEnvelope, UsageEvent, ErrorEvent } from '@/types/chat'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

export type SseEvent =
  | { type: 'token'; data: string }
  | { type: 'route'; data: RoutePayload }
  | { type: 'interrupt'; data: InterruptEnvelope }
  | { type: 'usage'; data: UsageEvent }
  | { type: 'error'; data: ErrorEvent }
  | { type: 'unknown'; data: unknown }   // 未知键:记录并忽略,不中断流

/** 把累计缓冲切成完整帧;返回剩余的不完整尾巴。 */
export function splitFrames(buf: string): { frames: string[]; rest: string } {
  // 关键:先归一化 CRLF。某些代理会把 \n\n 变成 \r\n\r\n,
  // 只按 '\n\n' 切会永远切不开,表现为"流不结束、界面无输出"。
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
    obj = JSON.parse(dataLines.join('\n'))
  } catch {
    return null                                  // 半帧/损坏帧:丢弃,不断流
  }
  const key = Object.keys(obj)[0]
  if (!key) return null
  const data = obj[key]
  switch (key) {
    case 'token':     return { type: 'token', data: String(data) }
    case 'route':     return { type: 'route', data: data as RoutePayload }
    case 'interrupt': return { type: 'interrupt', data: data as InterruptEnvelope }   // B3 信封:{kind, text}
    case 'usage':     return { type: 'usage', data: data as UsageEvent }
    case 'error':     return { type: 'error', data: data as ErrorEvent }
    default:          return { type: 'unknown', data }
  }
}

export interface SseHandlers {
  onToken?: (t: string) => void
  onRoute?: (r: RoutePayload) => void
  onInterrupt?: (i: InterruptEnvelope) => void
  onUsage?: (u: UsageEvent) => void
  onErrorEvent?: (e: ErrorEvent) => void        // 流内 error 帧(B4)
  onError?: (e: SseError) => void               // 传输层错误:非 2xx / 无 body / 网络中断
  onDone?: () => void                           // 流正常结束(挂起也算:服务端本轮流就此打住)
}

export class SseError extends Error {
  constructor(
    public kind: 'http' | 'network' | 'nobody' | 'parse',
    public status: number,
    message: string,
  ) { super(message) }
}

export async function sseFetch(
  path: string, body: unknown, handlers: SseHandlers, signal?: AbortSignal,
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
    handlers.onError?.(new SseError('network', 0, '无法连接后端,请确认 uvicorn 已启动'))
    return
  }

  if (!res.ok) {
    // 非 2xx:后端在 StreamingResponse 之前抛了 HTTPException,body 是 JSON
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (typeof data?.detail === 'string') detail = data.detail
      else if (data?.detail) detail = JSON.stringify(data.detail)
    } catch { /* 非 JSON 错误体:保留状态码文案 */ }
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

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      // 必须 { stream: true }:中文 3 字节,网络分片劈开多字节字符会出乱码
      buf += decoder.decode(value, { stream: true })

      const { frames, rest } = splitFrames(buf)
      buf = rest
      for (const raw of frames) {
        const ev = parseFrame(raw)
        if (!ev) { badFrames += 1; continue }
        switch (ev.type) {
          case 'token':     handlers.onToken?.(ev.data); break
          case 'route':     handlers.onRoute?.(ev.data); break
          case 'interrupt': handlers.onInterrupt?.(ev.data); break
          case 'usage':     handlers.onUsage?.(ev.data); break
          case 'error':     handlers.onErrorEvent?.(ev.data); break
          case 'unknown':   console.warn('[sse] 未知事件类型', ev.data); break
        }
      }
    }
    buf += decoder.decode()                     // 冲掉解码器内部残留
    if (buf.trim()) {
      const ev = parseFrame(buf)
      if (ev?.type === 'token') handlers.onToken?.(ev.data)
    }
    if (badFrames > 0) console.warn(`[sse] 丢弃了 ${badFrames} 个无法解析的帧`)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    handlers.onError?.(new SseError('network', 0, '流读取中断'))
    return
  } finally {
    reader.releaseLock()
  }
  handlers.onDone?.()
}
```
