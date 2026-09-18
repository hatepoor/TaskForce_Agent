/**
 * 知识库文档列表的共享数据源:知识库页与上下文栏(侧栏)读同一份,
 * 上传 / 删除后两边自动同步;侧栏点击通过 highlightId 让主区滚动定位。
 *
 * 说明:管理页数据本可各页局部持有,但侧栏也要展示同一份内容,故提取为模块级单例。
 */
import { ref } from 'vue'

import { errText } from '@/api/http'
import { listDocs } from '@/api/knowledge'
import type { KDoc } from '@/types/knowledge'
import { sortDocsByCreatedAt } from '@/utils/knowledge'

/** 高亮持续时长,与知识库页"刚上传行"的反馈一致 */
const HIGHLIGHT_MS = 2000

const docs = ref<KDoc[]>([])
const loading = ref(false)
const error = ref('')
const highlightId = ref('')

let inflight: Promise<void> | null = null
let clearTimer: ReturnType<typeof setTimeout> | undefined

/** 拉列表;并发调用共用同一个请求(侧栏与主区同时进入时不会打两次) */
async function load(): Promise<void> {
  if (inflight !== null) return inflight
  loading.value = true
  error.value = ''
  inflight = (async () => {
    try {
      const res = await listDocs()
      docs.value = sortDocsByCreatedAt(res.docs)
    } catch (e) {
      error.value = errText(e)
    } finally {
      loading.value = false
      inflight = null
    }
  })()
  return inflight
}

/** 定位某篇文档:主区表格滚动到该行并高亮 2s(侧栏点击与上传成功都走这里) */
function focusDoc(docId: string): void {
  highlightId.value = docId
  if (clearTimer !== undefined) clearTimeout(clearTimer)
  clearTimer = setTimeout(() => {
    highlightId.value = ''
  }, HIGHLIGHT_MS)
}

/** 删除后本地摘除一行(避免整表重拉时的闪烁) */
function removeDoc(docId: string): void {
  docs.value = docs.value.filter((it) => it.doc_id !== docId)
}

export function useDocsFeed() {
  return { docs, loading, error, highlightId, load, focusDoc, removeDoc }
}