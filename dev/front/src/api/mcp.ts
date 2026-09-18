/**
 * MCP 服务器管理封装(契约 §2.6)。
 *
 * ⚠️ 坑 12(B6 落地前):POST /mcp/servers 的 name 在 **query string** 里
 * (`?name=`),body 直接是 config 对象——FastAPI "标量参数 + 单一 dict 体"的默认行为。
 * 本文件消化该形状,组件层无感;B6 落地后只改本文件,请勿在别处直连。
 */
import type {
  MCPServerConfig,
  MCPServerListResponse,
  MCPServerOpResult,
  MCPTestResult,
} from '@/types/mcp'

import { request } from './http'

/** GET /mcp/servers — 服务器列表(name → config;未设置字段整个缺失)。 */
export function listServers(): Promise<MCPServerListResponse> {
  return request<MCPServerListResponse>('/mcp/servers')
}

/** POST /mcp/servers?name= — 新增/覆盖服务器(同名静默覆盖,UI 层做二次确认)。 */
export function createServer(name: string, config: MCPServerConfig): Promise<MCPServerOpResult> {
  return request<MCPServerOpResult>(`/mcp/servers?name=${encodeURIComponent(name)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
}

/** DELETE /mcp/servers/{name} — 删除服务器(不存在返 404)。 */
export function removeServer(name: string): Promise<MCPServerOpResult> {
  return request<MCPServerOpResult>(`/mcp/servers/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

/**
 * POST /mcp/servers/{name}/test — 连通性探测。
 * 后端最长阻塞 ~10s,前端超时 30s(契约 §3.6);ok:false 是正常业务返回,不抛。
 */
export function testServer(name: string): Promise<MCPTestResult> {
  return request<MCPTestResult>(`/mcp/servers/${encodeURIComponent(name)}/test`, {
    method: 'POST',
    signal: AbortSignal.timeout(30_000),
  })
}