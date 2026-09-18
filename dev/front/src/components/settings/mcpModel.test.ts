import { describe, expect, it } from 'vitest'

import type { MCPServerConfig, MCPTestResult } from '@/types/mcp'

import {
  NAME_RE,
  buildConfig,
  deleteMessage,
  emptyDraft,
  emptyRow,
  hasEmptyKeyRow,
  isDuplicateName,
  isTimeoutError,
  overwriteMessage,
  rowsToRecord,
  serverEntries,
  splitArgs,
  summarizeConfig,
  testOutcome,
  toolLabel,
  toolLabels,
  validateDraft,
} from './mcpModel'
import type { McpFormDraft } from './mcpModel'

function draftOf(patch: Partial<McpFormDraft>): McpFormDraft {
  return { ...emptyDraft(), ...patch }
}

describe('splitArgs', () => {
  it('按空白(含换行)切分并丢空段', () => {
    expect(splitArgs('-y @modelcontextprotocol/server-filesystem ./')).toEqual([
      '-y',
      '@modelcontextprotocol/server-filesystem',
      './',
    ])
    expect(splitArgs('-y\n  --port\n\t8080')).toEqual(['-y', '--port', '8080'])
    expect(splitArgs('   ')).toEqual([])
    expect(splitArgs('')).toEqual([])
  })
})

describe('rowsToRecord / hasEmptyKeyRow', () => {
  it('键为空的整行跳过,重复键后者覆盖', () => {
    expect(rowsToRecord([{ key: 'A', value: '1' }, { key: ' ', value: 'x' }, { key: 'A', value: '2' }])).toEqual({
      A: '2',
    })
    expect(rowsToRecord([])).toEqual({})
  })

  it('有值无键的行算填写错误;纯空行不算', () => {
    expect(hasEmptyKeyRow([emptyRow()])).toBe(false)
    expect(hasEmptyKeyRow([{ key: '', value: 'ghp_x' }])).toBe(true)
    expect(hasEmptyKeyRow([{ key: 'TOKEN', value: '' }])).toBe(false)
  })
})

describe('validateDraft', () => {
  it('名称必填且匹配 ^[a-z0-9_-]+$', () => {
    expect(validateDraft(draftOf({ name: '' }))).toBe('名称不能为空')
    expect(validateDraft(draftOf({ name: 'GitHub MCP' }))).toContain('只能包含小写字母')
    expect(NAME_RE.test('github-mcp_2')).toBe(true)
  })

  it('stdio:命令必填;http:URL 必填且须带协议头', () => {
    const stdio = draftOf({ name: 'ok-name', transport: 'stdio' })
    expect(validateDraft(stdio)).toContain('命令不能为空')

    const http = draftOf({ name: 'ok-name', transport: 'http' })
    expect(validateDraft(http)).toBe('URL 不能为空')

    http.http.url = 'mcp.context7.com/mcp'
    expect(validateDraft(http)).toContain('http:// 或 https://')

    http.http.url = 'https://mcp.context7.com/mcp'
    expect(validateDraft(http)).toBe('')
  })

  it('只校验当前 transport 的字段:stdio 草稿里的空 URL 不影响 stdio 提交', () => {
    const d = draftOf({ name: 'ok-name', transport: 'stdio' })
    d.stdio.command = 'npx'
    d.http.url = '' // 没填的 http 草稿
    expect(validateDraft(d)).toBe('')
  })

  it('键值对存在空键时报错', () => {
    const d = draftOf({ name: 'ok-name', transport: 'stdio' })
    d.stdio.command = 'npx'
    d.stdio.env = [{ key: '', value: 'ghp_x' }]
    expect(validateDraft(d)).toContain('空键')
  })
})

describe('buildConfig', () => {
  it('stdio:只带 transport/command/args/env,空可选项整个不发', () => {
    const d = draftOf({ name: 'fs', transport: 'stdio' })
    d.stdio.command = ' npx '
    d.stdio.argsText = '-y @modelcontextprotocol/server-filesystem ./'
    d.stdio.env = [{ key: 'TOKEN', value: 'x' }, emptyRow()]
    expect(buildConfig(d)).toEqual({
      transport: 'stdio',
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-filesystem', './'],
      env: { TOKEN: 'x' },
    })
  })

  it('stdio:不带 http 字段(url 填了也不发)', () => {
    const d = draftOf({ name: 'fs', transport: 'stdio' })
    d.stdio.command = 'npx'
    d.http.url = 'https://example.com/mcp'
    d.http.headers = [{ key: 'Authorization', value: 'Bearer x' }]
    expect(buildConfig(d)).toEqual({ transport: 'stdio', command: 'npx' })
  })

  it('http:只带 transport/url/headers,不带 stdio 残留字段', () => {
    const d = draftOf({ name: 'c7', transport: 'http' })
    d.stdio.command = 'npx'
    d.stdio.argsText = '-y something'
    d.http.url = ' https://mcp.context7.com/mcp '
    d.http.headers = [{ key: 'Authorization', value: 'Bearer sk-x' }]
    expect(buildConfig(d)).toEqual({
      transport: 'http',
      url: 'https://mcp.context7.com/mcp',
      headers: { Authorization: 'Bearer sk-x' },
    })
  })

  it('切换 transport 只改 transport 字段,两份草稿都还在', () => {
    const d = draftOf({ name: 'both' })
    d.stdio.command = 'npx'
    d.stdio.argsText = '-y foo'
    d.http.url = 'https://a.example/mcp'

    d.transport = 'http'
    expect(buildConfig(d)).toEqual({ transport: 'http', url: 'https://a.example/mcp' })

    d.transport = 'stdio'
    expect(buildConfig(d)).toEqual({ transport: 'stdio', command: 'npx', args: ['-y', 'foo'] })
  })
})

describe('summarizeConfig', () => {
  it('stdio 拼命令行,缺 args 也不报错', () => {
    expect(summarizeConfig({ transport: 'stdio', command: 'npx' })).toEqual({
      badge: 'stdio',
      summary: 'npx',
    })
    expect(
      summarizeConfig({ transport: 'stdio', command: 'npx', args: ['-y', 'foo'] }),
    ).toEqual({ badge: 'stdio', summary: 'npx -y foo' })
  })

  it('http 给 URL', () => {
    expect(summarizeConfig({ transport: 'http', url: 'https://mcp.context7.com/mcp' })).toEqual({
      badge: 'http',
      summary: 'https://mcp.context7.com/mcp',
    })
  })
})

describe('serverEntries', () => {
  it('字典拍平成按 name 升序的数组;null/undefined 给空数组', () => {
    const servers: Record<string, MCPServerConfig> = {
      zeta: { transport: 'http', url: 'https://z.example/mcp' },
      alpha: { transport: 'stdio', command: 'npx' },
    }
    expect(serverEntries(servers).map((e) => e.name)).toEqual(['alpha', 'zeta'])
    expect(serverEntries(null)).toEqual([])
    expect(serverEntries(undefined)).toEqual([])
  })
})

describe('重名与弹窗文案', () => {
  it('重名判定忽略首尾空白;空名不算重名', () => {
    expect(isDuplicateName(' github-mcp ', ['github-mcp'])).toBe(true)
    expect(isDuplicateName('github-mcp', ['context7'])).toBe(false)
    expect(isDuplicateName('', [''])).toBe(false)
  })

  it('覆盖 / 删除文案点名服务器', () => {
    expect(overwriteMessage('github-mcp')).toContain('github-mcp')
    expect(overwriteMessage('github-mcp')).toContain('覆盖')
    expect(deleteMessage('github-mcp')).toContain('github-mcp')
    expect(deleteMessage('github-mcp')).toContain('下次会话装配')
  })
})

describe('toolLabel / toolLabels(防御式渲染)', () => {
  it('字符串直接用,对象取 name,怪值退化 JSON 文本', () => {
    expect(toolLabel('read_file')).toBe('read_file')
    expect(toolLabel({ name: 'write_file' })).toBe('write_file')
    expect(toolLabel({ name: '' })).toBe('{"name":""}')
    expect(toolLabel({ title: 'no-name' })).toBe('{"title":"no-name"}')
    expect(toolLabel(42)).toBe('42')
    expect(toolLabel(null)).toBe('null')
    expect(toolLabel(undefined)).toBe('undefined')
  })

  it('循环引用不抛(兜底 String)', () => {
    const cyc: Record<string, unknown> = {}
    cyc.self = cyc
    expect(typeof toolLabel(cyc)).toBe('string')
  })

  it('截断到 max 个,余量走 more', () => {
    const tools = ['a', 'b', 'c', 'd']
    expect(toolLabels(tools, 2)).toEqual({ labels: ['a', 'b'], more: 2 })
    expect(toolLabels([], 2)).toEqual({ labels: [], more: 0 })
    expect(toolLabels(undefined, 2)).toEqual({ labels: [], more: 0 })
  })
})

describe('testOutcome', () => {
  it('ok:true 给工具名列表', () => {
    const r: MCPTestResult = { ok: true, name: 'context7', tools: ['resolve-library-id', 'get-library-docs'] }
    const out = testOutcome(r)
    expect(out.badge).toBe('已连通 · 2 个工具')
    expect(out.labels).toEqual(['resolve-library-id', 'get-library-docs'])
    expect(out.detail).toBe('')
  })

  it('ok:false 是正常业务返回:未连通,不是系统错误', () => {
    const out = testOutcome({ ok: false, name: 'fake', tools: [] })
    expect(out.ok).toBe(false)
    expect(out.badge).toBe('未连通')
    expect(out.detail).toContain('无法连接')
    expect(out.labels).toEqual([])
  })

  it('工具是对象数组也能渲染', () => {
    const out = testOutcome({ ok: true, name: 'x', tools: [{ name: 'read_file' }, { name: 'write_file' }] })
    expect(out.badge).toBe('已连通 · 2 个工具')
    expect(out.labels).toEqual(['read_file', 'write_file'])
  })

  it('ok:true 但零工具时给兜底说明', () => {
    const out = testOutcome({ ok: true, name: 'x', tools: [] })
    expect(out.badge).toBe('已连通')
    expect(out.detail).toContain('未发现任何工具')
  })
})

describe('isTimeoutError', () => {
  it('TimeoutError / AbortError 均判超时', () => {
    expect(isTimeoutError(new DOMException('t', 'TimeoutError'))).toBe(true)
    expect(isTimeoutError(new DOMException('a', 'AbortError'))).toBe(true)
    expect(isTimeoutError(new Error('HTTP 404'))).toBe(false)
    expect(isTimeoutError('boom')).toBe(false)
  })
})