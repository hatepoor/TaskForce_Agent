<script setup lang="ts">
// 上传队列单行:排队 / 上传中(进度条)/ 已入库 / 失败四态(UI-DESIGN §4.1)。
// 失败项保留在队列里可重试;超限项前端已拦,不给重试入口(重试也没意义)。
import { computed } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import { type UploadItem, doneText, fmtBytes, isOversize, progressText } from '@/utils/knowledge'

const props = defineProps<{
  item: UploadItem
  /** 该 doc_id 的切片数(取自上传后刷新的列表;拿不到则为 undefined) */
  chunks: number | undefined
}>()

const emit = defineEmits<{ retry: [] }>()

const MARKS: Record<UploadItem['state'], string> = {
  queued: '○',
  uploading: '⟳',
  done: '✓',
  failed: '✗',
}

const mark = computed(() => MARKS[props.item.state])

const sizeText = computed(() => fmtBytes(props.item.size))

const statusText = computed(() => {
  const it = props.item
  if (it.state === 'queued') return '排队中'
  if (it.state === 'uploading') return progressText(it.percent)
  if (it.state === 'done') return doneText(it.created, props.chunks)
  return `失败:${it.message}`
})

const retryable = computed(() => props.item.state === 'failed' && !isOversize(props.item.size))
</script>

<template>
  <li class="qi" :class="`qi--${item.state}`" data-testid="upload-queue-item">
    <span class="qi__mark" aria-hidden="true">{{ mark }}</span>
    <span class="qi__name" :title="item.name" data-testid="upload-item-name">{{ item.name }}</span>
    <span class="qi__size">{{ sizeText }}</span>
    <span class="qi__status" data-testid="upload-item-status">{{ statusText }}</span>
    <span
      v-if="item.state === 'uploading'"
      class="qi__track"
      role="progressbar"
      aria-label="上传进度"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="item.percent"
    >
      <span class="qi__fill" :style="{ width: `${item.percent}%` }" />
    </span>
    <AppButton v-if="retryable" data-testid="upload-item-retry" @click="emit('retry')">
      重试
    </AppButton>
  </li>
</template>

<style scoped>
.qi {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--fs-sm);
}

.qi:last-child {
  border-bottom: none;
}

.qi__mark {
  flex: none;
  width: 12px;
  text-align: center;
  color: var(--text-muted);
}

.qi--done .qi__mark {
  color: var(--success);
}

.qi--failed .qi__mark {
  color: var(--danger);
}

.qi__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}

.qi__size {
  flex: none;
  font-family: var(--font-mono);
  color: var(--text-muted);
}

.qi__status {
  flex: none;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.qi--done .qi__status {
  color: var(--success);
}

.qi--failed .qi__status {
  color: var(--danger);
}

.qi__track {
  flex: none;
  width: 96px;
  height: 4px;
  border-radius: var(--r-full);
  background: var(--bg-hover);
  overflow: hidden;
}

.qi__fill {
  display: block;
  height: 100%;
  border-radius: var(--r-full);
  background: var(--accent);
}
</style>