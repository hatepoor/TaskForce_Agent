/**
 * MCP 资源类型镜像(唯一事实源:API-CONTRACT.md §2.6)。
 *
 * 后端 `model_dump(exclude_none=True)`:未设置的字段不会出现(整个键缺失),
 * 故可选字段全部以 `?:` 声明,渲染时按可选处理。
 */

/** stdio 传输:command 必填,args/env 可选。 */
export interface StdioServer {
  transport: 'stdio'
  command: string
  args?: string[]
  env?: Record<string, string>
}

/** http 传输:url 必填,headers 可选。 */
export interface HttpServer {
  transport: 'http'
  url: string
  headers?: Record<string, string>
}

/** MCP 服务器配置判别联合:类型层按 transport 收窄。 */
export type MCPServerConfig = StdioServer | HttpServer

/** GET /mcp/servers 响应:name → config 字典。 */
export interface MCPServerListResponse {
  servers: Record<string, MCPServerConfig>
}

/** POST /mcp/servers 与 DELETE /mcp/servers/{name} 响应。 */
export interface MCPServerOpResult {
  ok: boolean
  name: string
}

/**
 * POST /mcp/servers/{name}/test 响应。
 * `ok: false` 是正常业务返回(探测降级,不抛),UI 显示"未连通"而非红色报错。
 */
export interface MCPTestResult {
  ok: boolean
  name: string
  /**
   * B8 落地前后端未归一化:可能是 string[],也可能是对象数组;
   * 渲染层需防御式处理(见契约 §2.6 的 label 取值示例)。
   */
  tools: unknown[]
}