// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'

import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('http(s) 外链带 target=_blank 与 rel(新开标签页, 不带走 SPA)', () => {
    const html = renderMarkdown('见 [示例](https://example.com/a?b=1)')

    expect(html).toContain('href="https://example.com/a?b=1"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('站内锚点保持同页跳转(不加 target)', () => {
    const html = renderMarkdown('跳到 [小节](#section)')

    expect(html).toContain('href="#section"')
    expect(html).not.toContain('target="_blank"')
  })

  it('XSS 清洗不受 hook 影响', () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">')

    expect(html).not.toContain('onerror')
  })
})
