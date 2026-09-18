<script setup lang="ts">
// 上传区:拖拽 / 多选 → **串行** N 个请求(不并发)+ 四态队列(UI-DESIGN §4.1)。
// 接口只收单个 `file` 字段(契约 §2.3),排队逐个发;进度靠 XHR 的 upload.onprogress。
import { ref } from 'vue'

import { errText } from '@/api/http'
import AppButton from '@/components/common/AppButton.vue'
import { useUiStore } from '@/stores/ui'
import {
  OVERSIZE_MSG,
  type UploadItem,
  isOversize,
  makeQueueItem,
  nextQueuedIndex,
} from '@/utils/knowledge'

import UploadQueueItem from './UploadQueueItem.vue'
import { uploadDocWithProgress } from './xhrUpload'

defineProps<{
  /** doc_id → 切片数:上传成功后由列表刷新回填,队列行据此显示「已入库 42 切片」 */
  chunkMap: Record<string, number>
}>()

const emit = defineEmits<{ uploaded: [docId: string] }>()

const ui = useUiStore()

const items = ref<UploadItem[]>([])
const dragging = ref(false)
const inputEl = ref<HTMLInputElement | null>(null)

/** File 不进响应式状态(大对象、无需渲染),按 item id 旁路存放 */
const files = new Map<number, File>()
let nextId = 0
/** 串行闸门:同一时刻只有一个 drain 在跑 */
let draining = false

function pick(): void {
  inputEl.value?.click()
}

function onPick(e: Event): void {
  const el = e.target as HTMLInputElement
  addFiles(el.files)
  // 清空 value:同一文件再选一次也要能触发 change
  el.value = ''
}

function onDrop(e: DragEvent): void {
  dragging.value = false
  addFiles(e.dataTransfer?.files)
}

function addFiles(list: ArrayLike<File> | null | undefined): void {
  if (list === null || list === undefined) return
  const picked = Array.from(list)
  if (picked.length === 0) return

  const added: UploadItem[] = []
  for (const file of picked) {
    const item = makeQueueItem(file, nextId)
    nextId += 1
    files.set(item.id, file)
    added.push(item)
    // 20MB 前端先拦(后端 400 是双保险):超限项不发请求
    if (item.state === 'failed') ui.toast(`${item.name}:${OVERSIZE_MSG}`, 'error')
  }
  items.value = [...items.value, ...added]
  void drain()
}

function retry(id: number): void {
  const item = items.value.find((it) => it.id === id)
  if (item === undefined || item.state !== 'failed') return

  const file = files.get(id)
  if (file === undefined) {
    ui.toast('文件已失效,请重新选择', 'error')
    return
  }
  if (isOversize(file.size)) {
    ui.toast(`${item.name}:${OVERSIZE_MSG}`, 'error')
    return
  }

  item.state = 'queued'
  item.message = ''
  item.percent = 0
  void drain()
}

/** 串行推进:一次只发一个,前一个落地(成功或失败)才发下一个 */
async function drain(): Promise<void> {
  if (draining) return
  draining = true
  try {
    for (;;) {
      const idx = nextQueuedIndex(items.value)
      if (idx < 0) break
      await uploadAt(idx)
    }
  } finally {
    draining = false
  }
}

async function uploadAt(idx: number): Promise<void> {
  const item = items.value[idx]
  if (item === undefined) return

  const file = files.get(item.id)
  if (file === undefined) {
    item.state = 'failed'
    item.message = '文件已失效,请重新选择'
    return
  }

  item.state = 'uploading'
  item.percent = 0
  item.message = ''

  try {
    const res = await uploadDocWithProgress(file, (percent) => {
      item.percent = percent
    })
    item.state = 'done'
    item.percent = 100
    item.created = res.created
    item.docId = res.doc_id
    files.delete(item.id)

    // created:false 是内容判重命中:不算失败,也不算普通成功(契约 §2.3)
    if (res.created) ui.toast(`已入库:${item.name}`)
    else ui.toast('该文档已存在,已复用')

    emit('uploaded', res.doc_id)
  } catch (e) {
    item.state = 'failed'
    item.message = errText(e)
    ui.toast(`${item.name}:${item.message}`, 'error')
  }
}
</script>

<template>
  <section class="up" data-testid="upload-panel">
    <div
      class="up__drop"
      :class="{ 'up__drop--over': dragging }"
      data-testid="upload-dropzone"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <p class="up__text">拖拽文件到此处,或</p>
      <AppButton data-testid="upload-pick" @click="pick()">选择文件</AppButton>
      <p class="up__hint">支持 pdf / docx / md / txt,单文件 ≤ 20MB;多选会逐个上传</p>
      <input
        ref="inputEl"
        class="up__input"
        type="file"
        multiple
        data-testid="upload-input"
        @change="onPick"
      />
    </div>

    <div v-if="items.length > 0" class="up__queue" data-testid="upload-queue">
      <p class="up__queue-title">上传队列</p>
      <ul class="up__list">
        <UploadQueueItem
          v-for="it in items"
          :key="it.id"
          :item="it"
          :chunks="chunkMap[it.docId]"
          @retry="retry(it.id)"
        />
      </ul>
    </div>
  </section>
</template>

<style scoped>
.up {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.up__drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-5) var(--sp-4);
  border: 1px dashed var(--border-strong);
  border-radius: var(--r-md);
  background: var(--bg-panel);
  text-align: center;
}

.up__drop--over {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.up__text {
  color: var(--text-secondary);
  font-size: var(--fs-md);
}

.up__hint {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.up__input {
  display: none;
}

.up__queue {
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  overflow: hidden;
}

.up__queue-title {
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-strong);
  color: var(--text-muted);
  font-size: var(--fs-xs);
}

.up__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
</style>