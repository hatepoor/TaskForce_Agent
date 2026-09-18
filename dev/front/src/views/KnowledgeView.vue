<script setup lang="ts">
// 知识库管理页(模块 09):上传队列 + 文档列表 + 删除确认。
// 数据局部持有(管理页不进 Pinia,UI-DESIGN §2.2):上传成功与删除后都重拉列表,
// 队列行显示的切片数也从同一份列表回填(develop.md §模块关键约束:同一数据源)。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ApiError, errText } from '@/api/http'
import { removeDoc } from '@/api/knowledge'
import AppButton from '@/components/common/AppButton.vue'
import DeleteDocDialog from '@/components/knowledge/DeleteDocDialog.vue'
import DocTable from '@/components/knowledge/DocTable.vue'
import UploadPanel from '@/components/knowledge/UploadPanel.vue'
import { useDocsFeed } from '@/composables/useDocsFeed'
import { useUiStore } from '@/stores/ui'
import type { KDoc } from '@/types/knowledge'
import { COPY_FEEDBACK_MS, DOC_GONE_MSG, isDocGoneStatus } from '@/utils/knowledge'

const ui = useUiStore()

// 列表与上下文栏(侧栏)共用一份数据源:侧栏点击写 highlightId,这里滚动定位并高亮
const {
  docs,
  loading,
  error,
  highlightId,
  load: reload,
  focusDoc,
  removeDoc: dropDoc,
} = useDocsFeed()

/** 处于「已复制」内联反馈期的 doc_id(1.5s) */
const copiedId = ref('')
/** 待删除文档:非空即弹确认框 */
const pending = ref<KDoc | null>(null)
const deleting = ref(false)

let copyTimer: ReturnType<typeof setTimeout> | undefined

/** doc_id → 切片数:上传队列行「已入库 N 切片」用 */
const chunkMap = computed<Record<string, number>>(() => {
  const map: Record<string, number> = {}
  for (const doc of docs.value) map[doc.doc_id] = doc.chunks
  return map
})

/** 拉列表:失败在页面侧提示(侧栏那份只显示错误条,不重复弹 toast) */
async function load(): Promise<void> {
  await reload()
  if (error.value !== '') ui.toast(error.value, 'error')
}

/** 上传成功:刷新列表 + 定位新行并高亮 2s(UI-DESIGN §4.1) */
async function onUploaded(docId: string): Promise<void> {
  await load()
  focusDoc(docId)
}

// 侧栏点击 / 上传成功 → 把对应行滚入视野(高亮样式由 highlightId 透传给 DocTable)
watch(highlightId, (id) => {
  if (id === '') return
  void nextTick(() => {
    const rows = [...document.querySelectorAll<HTMLElement>('[data-doc-id]')]
    rows.find((row) => row.dataset.docId === id)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
})

async function onCopyId(docId: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(docId)
  } catch {
    ui.toast('复制失败,请手动选中复制', 'error')
    return
  }
  copiedId.value = docId
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => {
    copiedId.value = ''
  }, COPY_FEEDBACK_MS)
}

function askDelete(doc: KDoc): void {
  pending.value = doc
}

function cancelDelete(): void {
  if (deleting.value) return
  pending.value = null
}

async function confirmDelete(): Promise<void> {
  const doc = pending.value
  if (doc === null || deleting.value) return

  deleting.value = true
  try {
    await removeDoc(doc.doc_id)
    dropDoc(doc.doc_id) // 本地摘除:侧栏列表同步少一行
    ui.toast(`已删除:${doc.filename}`)
    pending.value = null
    await load()
  } catch (e) {
    // B7 未落地:删不存在的文档后端返 500(落地后返 404),两者都按"可能已不存在"过渡处理(契约 §1.3)
    if (e instanceof ApiError && isDocGoneStatus(e.status)) {
      ui.toast(DOC_GONE_MSG, 'error')
      pending.value = null
      await load()
    } else {
      // 其余错误保留弹窗,用户可重试
      ui.toast(errText(e), 'error')
    }
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  void load()
})

onBeforeUnmount(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})
</script>

<template>
  <section class="view" data-testid="knowledge-view">
    <header class="view__head">
      <h1 class="view__title">知识库</h1>
      <AppButton :disabled="loading" data-testid="docs-refresh" @click="load()">刷新</AppButton>
    </header>

    <UploadPanel :chunk-map="chunkMap" @uploaded="onUploaded" />

    <DocTable
      :docs="docs"
      :loading="loading"
      :error="error"
      :highlight-id="highlightId"
      :copied-id="copiedId"
      @copy-id="onCopyId"
      @remove="askDelete"
      @retry="load"
    />

    <DeleteDocDialog
      v-if="pending"
      :doc="pending"
      :busy="deleting"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </section>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  width: min(var(--measure-page), 100%);
  margin: 0 auto;
  padding: var(--sp-4);
}

.view__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}

.view__title {
  font-size: var(--fs-xl);
  font-weight: 600;
}
</style>