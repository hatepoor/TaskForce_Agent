import { request } from './http'

/** GET /health 响应(契约 §2.2)。 */
export interface HealthStatus {
  /** "ok" | "degraded"(degraded 即 DB 异常)。 */
  status: 'ok' | 'degraded'
  /** "ok" | "error: {异常信息}"(内嵌完整异常文本)。 */
  db: string
  /** 值域不封闭:unknown | ok | error 文本 | unreachable;UI 层按"非 ok 即异常"处理。 */
  sandbox: string
}

export function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/health')
}