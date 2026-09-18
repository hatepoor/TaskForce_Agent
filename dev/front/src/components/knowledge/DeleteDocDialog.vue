<script setup lang="ts">
// 删除确认弹窗:回显文件名 + 切片数,危险操作必须二次确认(UI-DESIGN §4.1)。
// 删除中只有按钮内联 loading,不整页遮罩;Esc 取消(UI-DESIGN §6.1)。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import type { KDoc } from '@/types/knowledge'

const props = defineProps<{
  doc: KDoc
  /** 删除请求进行中 */
  busy: boolean
}>()

const emit = defineEmits<{ confirm: []; cancel: [] }>()

const dlgEl = ref<HTMLDivElement | null>(null)

const chunks = computed(() => props.doc.chunks)

function onCancel(): void {
  if (props.busy) return
  emit('cancel')
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape') onCancel()
}

onMounted(() => {
  // 默认焦点给弹窗容器(不是确认钮):回车不会误删
  dlgEl.value?.focus()
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div class="mask" data-testid="delete-doc-dialog" @click.self="onCancel">
    <div
      ref="dlgEl"
      class="dlg"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-doc-title"
      tabindex="-1"
    >
      <h2 id="delete-doc-title" class="dlg__title">删除文档</h2>
      <p class="dlg__body">
        <span class="dlg__name" data-testid="delete-doc-filename">{{ doc.filename }}</span>
        的 {{ chunks }} 个向量切片将一并移除,不可恢复。
      </p>
      <div class="dlg__ops">
        <AppButton :disabled="busy" data-testid="delete-doc-cancel" @click="onCancel">取消</AppButton>
        <AppButton
          variant="danger"
          :disabled="busy"
          data-testid="delete-doc-confirm"
          @click="emit('confirm')"
        >
          <Spinner v-if="busy" :size="12" />
          {{ busy ? '删除中…' : '删除' }}
        </AppButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
}

.dlg {
  width: 380px;
  max-width: calc(100% - var(--sp-6));
  padding: var(--sp-4);
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-pop);
}

.dlg:focus-visible {
  outline: var(--focus-ring);
  outline-offset: var(--focus-offset);
}

.dlg__title {
  font-size: var(--fs-lg);
  font-weight: 600;
}

.dlg__body {
  margin-top: var(--sp-2);
  color: var(--text-secondary);
  font-size: var(--fs-md);
  line-height: var(--lh-base);
  overflow-wrap: anywhere;
}

.dlg__name {
  color: var(--text-primary);
  font-weight: 600;
}

.dlg__ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  margin-top: var(--sp-4);
}
</style>