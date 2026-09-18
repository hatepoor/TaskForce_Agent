<script setup lang="ts">
// 文档列表单行:文件名 / doc_id(点击复制) / 入库时间 / 切片数 / 复制 + 删除。
// id 等宽 + 点击复制 + 1.5s 内联「已复制」;数字列右对齐(UI-DESIGN §5.1 / §6.3)。
import { computed } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import type { KDoc } from '@/types/knowledge'
import { fmtDateTime, shortDocId } from '@/utils/knowledge'

const props = defineProps<{
  doc: KDoc
  /** 刚上传成功的行:2s 高亮 */
  highlight: boolean
  /** 该行处于「已复制」内联反馈期 */
  copied: boolean
}>()

const emit = defineEmits<{ copyId: [docId: string]; remove: [doc: KDoc] }>()

const timeText = computed(() => fmtDateTime(props.doc.created_at))
const idText = computed(() => shortDocId(props.doc.doc_id))
</script>

<template>
  <tr class="row" :class="{ 'row--hl': highlight }" data-testid="doc-row" :data-doc-id="doc.doc_id">
    <td class="row__cell row__name" :title="doc.filename" data-testid="doc-name">
      {{ doc.filename }}
    </td>
    <td class="row__cell">
      <button
        type="button"
        class="row__id"
        :title="`点击复制 ${doc.doc_id}`"
        data-testid="doc-id"
        @click="emit('copyId', doc.doc_id)"
      >
        {{ copied ? '已复制' : idText }}
      </button>
    </td>
    <td class="row__cell row__time" :title="doc.created_at" data-testid="doc-time">
      {{ timeText }}
    </td>
    <td class="row__cell row__num" data-testid="doc-chunks">{{ doc.chunks }}</td>
    <td class="row__cell">
      <div class="row__ops">
        <AppButton data-testid="doc-copy" @click="emit('copyId', doc.doc_id)">复制</AppButton>
        <AppButton variant="danger" data-testid="doc-delete" @click="emit('remove', doc)">
          删除
        </AppButton>
      </div>
    </td>
  </tr>
</template>

<style scoped>
.row:hover {
  background: var(--bg-raised);
}

/* 新入库行 2s 高亮(UI-DESIGN §4.1) */
.row--hl,
.row--hl:hover {
  background: var(--accent-soft);
}

.row__cell {
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--fs-sm);
  vertical-align: middle;
}

.row__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}

.row__id {
  padding: 0;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  /* id 必须可选中(UI-DESIGN §6.3) */
  user-select: text;
  cursor: pointer;
}

.row__id:hover {
  color: var(--accent);
}

.row__time {
  color: var(--text-secondary);
  white-space: nowrap;
}

.row__num {
  text-align: right;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

.row__ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  white-space: nowrap;
}
</style>