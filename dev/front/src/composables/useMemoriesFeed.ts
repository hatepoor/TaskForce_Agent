/**
 * 长期记忆列表的共享数据源:记忆页与上下文栏(侧栏)读同一份,删除后两边同步;
 * 侧栏点击通过 highlightId 让主区滚动定位(与知识库侧栏同一套交互)。
 */
import { ref } from 'vue'

import { errText } from '@/api/http'
import { listMemories } from '@/api/memory'
import type { MemoryItem as MemoryRecord } from '@/types/memory'

const HIGHLIGHT_MS = 2000

const items = ref<MemoryRecord[]>([])
const loading = ref(false)
const error = ref('')
const highlightId = ref('')

let inflight: Promise<void> | null = null
let clearTimer: ReturnType<typeof setTimeout> | undefined

async function load(): Promise<void> {
  if (inflight !== null) return inflight
  loading.value = true
  error.value = ''
  inflight = (async () => {
    try {
      const res = await listMemories()
      items.value = res.items
    } catch (e) {
      error.value = errText(e)
    } finally {
      loading.value = false
      inflight = null
    }
  })()
  return inflight
}

function focusMemory(key: string): void {
  highlightId.value = key
  if (clearTimer !== undefined) clearTimeout(clearTimer)
  clearTimer = setTimeout(() => {
    highlightId.value = ''
  }, HIGHLIGHT_MS)
}

function removeMemory(key: string): void {
  items.value = items.value.filter((it) => it.key !== key)
}

export function useMemoriesFeed() {
  return { items, loading, error, highlightId, load, focusMemory, removeMemory }
}