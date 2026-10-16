/**
 * Markdown 渲染封装:marked + DOMPurify(助手输出可能含 HTML,XSS 防护必须)。
 * LRU 缓存以源文为 key:流结束后的重渲染命中缓存,不再重复解析 + 清洗(ARCHITECTURE 坑 5)。
 *
 * 只应渲染**已结束**的消息:流式半截语法渲染不出正确结果(见 AssistantMessage)。
 */
import DOMPurify from 'dompurify'
import { marked } from 'marked'

const CACHE_MAX = 50
const cache = new Map<string, string>()

marked.setOptions({ gfm: true, breaks: true })

// 外链一律新开标签页:同页跳转会把整个 SPA 带走(返回时聊天内容只在内存, 体感是"聊的全没了")。
// 只对 http(s) 外链加, 站内锚点(#...)保持同页跳转。
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  const href = node.getAttribute('href') ?? ''
  if (node.tagName === 'A' && /^https?:/i.test(href)) {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

export function renderMarkdown(src: string): string {
  const hit = cache.get(src)
  if (hit !== undefined) {
    cache.delete(src)
    cache.set(src, hit)
    return hit
  }

  const html = DOMPurify.sanitize(marked.parse(src, { async: false }))
  cache.set(src, html)

  if (cache.size > CACHE_MAX) {
    const oldest = cache.keys().next().value
    if (oldest !== undefined) cache.delete(oldest)
  }
  return html
}

/** 清空渲染缓存(测试用)。 */
export function clearMarkdownCache(): void {
  cache.clear()
}