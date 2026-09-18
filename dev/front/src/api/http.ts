/**
 * 统一请求层:BASE 拼接 / 默认超时 / 错误归一化。
 * - BASE 是全项目唯一 BaseURL 来源(只此一处读 VITE_API_BASE);
 * - SSE 不走本模块(见后续 api/sse.ts,单独的超时与分帧解析策略)。
 */

/** 全项目唯一 BaseURL 来源:开发期 /api(由 vite proxy 剥离),生产期空(同源直连)。 */
export const BASE: string = import.meta.env.VITE_API_BASE ?? ''

/** 业务错误:携带 HTTP 状态码与后端 detail 原文。 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(`HTTP ${status}`)
    this.name = 'ApiError'
  }
}

const DEFAULT_TIMEOUT_MS = 15_000

/** 统一 fetch 封装:非 2xx 解析 detail 抛 ApiError;默认 15s 超时(调用方可传 signal 覆盖)。 */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    signal: init.signal ?? AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })

  if (!res.ok) {
    let detail: unknown
    try {
      const body: unknown = await res.json()
      detail =
        typeof body === 'object' && body !== null && 'detail' in body
          ? (body as { detail: unknown }).detail
          : body
    } catch {
      detail = undefined // 非 JSON 错误体:保留状态码兜底文案
    }
    throw new ApiError(res.status, detail === undefined ? `HTTP ${res.status}` : detail)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** 错误归一化为可读文案:兼容 detail 为 string 与 FastAPI 422 的 object[]。 */
export function errText(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail
    if (typeof d === 'string' && d) return d
    if (Array.isArray(d)) {
      return d
        .map((it) =>
          typeof it === 'object' && it !== null && 'msg' in it
            ? String((it as { msg: unknown }).msg)
            : JSON.stringify(it),
        )
        .join(';')
    }
    if (d != null) return JSON.stringify(d)
    return `请求失败(HTTP ${e.status})`
  }
  if (e instanceof DOMException && e.name === 'TimeoutError') {
    return '请求超时(15 秒),请检查后端服务是否已启动'
  }
  if (e instanceof DOMException && e.name === 'AbortError') return '请求已取消'
  if (e instanceof TypeError) return '无法连接后端,请确认 uvicorn 已启动'
  if (e instanceof Error) return e.message
  return String(e)
}