/**
 * 展示型组件的渲染冒烟测试(node 环境 + @vue/server-renderer,无 DOM、无浏览器)。
 * 覆盖三条视觉契约:health 原文本直出 / stdio 与 http 摘要区分且缺省字段不报错 /
 * ok:false 呈现为"未连通"而非系统错误。
 */
import { renderToString } from '@vue/server-renderer'
import { createPinia, setActivePinia } from 'pinia'
import type { Component } from 'vue'
import { createSSRApp } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'

import HealthCard from './HealthCard.vue'
import McpServerItem from './McpServerItem.vue'
import McpTestResult from './McpTestResult.vue'
import ModelCard from './ModelCard.vue'
import { MODEL_GROUPS, emptyValues } from './modelsModel'
import SettingsView from '@/views/SettingsView.vue'

function render(comp: Component, props: Record<string, unknown>): Promise<string> {
  return renderToString(createSSRApp(comp, props))
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('HealthCard', () => {
  it('db 异常文本原样直出(不截断、不转义语义)', async () => {
    const html = await render(HealthCard, {
      name: 'db',
      label: '数据库',
      state: 'err',
      value: 'error: 连接串拒绝连接',
      detail: '数据库不可用:会话与记忆均不可读写',
    })
    expect(html).toContain('data-testid="health-card-db"')
    expect(html).toContain('error: 连接串拒绝连接')
    expect(html).toContain('dot--err')
  })

  it('sandbox 非 ok:原文本直出且不是红点', async () => {
    const html = await render(HealthCard, {
      name: 'sandbox',
      label: '沙箱',
      state: 'warn',
      value: 'unreachable',
      detail: '沙箱非 ok 即异常,代码执行能力可能不可用',
    })
    expect(html).toContain('unreachable')
    expect(html).toContain('dot--warn')
    expect(html).not.toContain('dot--err')
  })
})

describe('McpServerItem', () => {
  it('stdio:徽标为 stdio,摘要拼命令行,args 缺失也不报错', async () => {
    const html = await render(McpServerItem, { name: 'fs', config: { transport: 'stdio', command: 'npx' } })
    expect(html).toContain('data-testid="mcp-row"')
    expect(html).toContain('data-server="fs"')
    expect(html).toContain('mcp-badge-fs')
    expect(html).toContain('stdio')
    expect(html).toContain('npx')
    expect(html).toContain('data-testid="mcp-test"')
    expect(html).toContain('data-testid="mcp-delete"')
  })

  it('http:徽标为 http,摘要给 URL', async () => {
    const html = await render(McpServerItem, {
      name: 'c7',
      config: { transport: 'http', url: 'https://mcp.context7.com/mcp' },
    })
    expect(html).toContain('http')
    expect(html).toContain('https://mcp.context7.com/mcp')
    expect(html).toContain('未测试')
  })
})

describe('McpTestResult', () => {
  it('ok:true 列出工具名', async () => {
    const html = await render(McpTestResult, {
      result: { ok: true, name: 'c7', tools: ['resolve-library-id', 'get-library-docs'] },
      error: '',
    })
    expect(html).toContain('工具:')
    expect(html).toContain('resolve-library-id')
    expect(html).toContain('get-library-docs')
  })

  it('ok:false 呈现"未连通",且不带红色系统错误语义(outcome.ok=false 时只给 danger 文案)', async () => {
    const html = await render(McpTestResult, {
      result: { ok: false, name: 'fake', tools: [] },
      error: '',
    })
    expect(html).toContain('无法连接')
    expect(html).toContain('result__line--fail')
  })

  it('对象数组形状的工具也能渲染(B8 落地前防御式)', async () => {
    const html = await render(McpTestResult, {
      result: { ok: true, name: 'x', tools: [{ name: 'read_file' }, { name: 'write_file' }] },
      error: '',
    })
    expect(html).toContain('read_file')
    expect(html).toContain('write_file')
  })

  it('请求层失败(超时)走 error 分支', async () => {
    const html = await render(McpTestResult, { result: null, error: '测试超时(30 秒):远端 MCP 未在时限内响应' })
    expect(html).toContain('测试失败:')
    expect(html).toContain('测试超时')
  })
})

describe('SettingsView(按路由参数分节渲染)', () => {
  /** 装一个内存路由再渲染:SettingsView 现在按 route.params.section 决定渲哪一节 */
  async function renderAt(comp: Component, path: string): Promise<string> {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/settings/:section(mcp|skills|health|models)?', component: { template: '<div />' } }],
    })
    await router.push(path)
    await router.isReady()
    const app = createSSRApp(comp)
    app.use(router)
    return renderToString(app)
  }

  it('mcp 节:只渲 MCP,不渲其它节', async () => {
    const html = await renderAt(SettingsView, '/settings/mcp')
    expect(html).toContain('data-testid="settings-view"')
    expect(html).toContain('data-testid="mcp-section"')
    expect(html).toContain('data-testid="mcp-empty"')
    expect(html).not.toContain('data-testid="skills-section"')
    expect(html).not.toContain('data-testid="health-section"')
  })

  it('skills 节:只渲 Skills,含重启后端提示', async () => {
    const html = await renderAt(SettingsView, '/settings/skills')
    expect(html).toContain('data-testid="skills-section"')
    expect(html).toContain('data-testid="skills-empty"') // SSR 不跑 onMounted
    expect(html).toContain('重启后端')
    expect(html).not.toContain('data-testid="mcp-section"')
  })

  it('health 节:只渲 Health', async () => {
    const html = await renderAt(SettingsView, '/settings/health')
    expect(html).toContain('data-testid="health-section"')
    expect(html).toContain('还没有检测结果') // SSR 不跑 onMounted,首帧无数据
    expect(html).not.toContain('data-testid="mcp-section"')
  })

  it('无 section 参数时默认 MCP 节', async () => {
    const html = await renderAt(SettingsView, '/settings')
    expect(html).toContain('data-testid="mcp-section"')
  })

  it('models 节:只渲模型节,含 OpenAI 协议提示与两张卡(SSR 不跑 onMounted)', async () => {
    const html = await renderAt(SettingsView, '/settings/models')
    expect(html).toContain('data-testid="models-section"')
    expect(html).toContain('OpenAI 兼容协议')
    expect(html).toContain('data-testid="model-card-llm"')
    expect(html).toContain('data-testid="model-card-embedding"')
    expect(html).not.toContain('data-testid="mcp-section"')
  })
})
describe('ModelCard', () => {
  function llmFields() {
    const group = MODEL_GROUPS.find((g) => g.key === 'llm')
    if (group === undefined) throw new Error('缺少 llm 分组')
    return group.fields
  }

  it('渲染三项输入:密钥走密码框、覆盖项打标、base_url 原样直出', async () => {
    const html = await render(ModelCard, {
      groupKey: 'llm',
      title: '主模型(对话)',
      hint: 'supervisor 与子智能体共用',
      fields: llmFields(),
      values: {
        ...emptyValues(),
        llm_base_url: 'https://ark.example/api/v3',
        llm_api_key: 'sk-a****wxyz',
        llm_model: 'doubao-seed',
      },
      overridden: ['llm_model'],
    })
    expect(html).toContain('data-testid="model-card-llm"')
    expect(html).toContain('https://ark.example/api/v3')
    expect(html).toContain('type="password"') // api_key 掩码框
    expect(html).toContain('sk-a****wxyz')
    expect(html).toContain('已覆盖') // llm_model 来自设置页覆盖
    expect(html).toContain('data-testid="model-reset-llm"')
  })

  it('未被覆盖时不出现覆盖徽标', async () => {
    const html = await render(ModelCard, {
      groupKey: 'embedding',
      title: 'Embedding(向量)',
      hint: '知识库用',
      fields: llmFields(),
      values: emptyValues(),
      overridden: [],
    })
    expect(html).toContain('data-testid="model-card-embedding"')
    expect(html).not.toContain('设置页覆盖')
  })
})
