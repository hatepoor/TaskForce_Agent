<script setup lang="ts">
// 通用确认弹窗(settings 域内共用:删除 MCP 服务器 / 同名覆盖确认)。
// 默认焦点落在「取消」,危险操作回车不误触;Esc 关闭;支持忙碌态禁用两个按钮。
import { nextTick, onUnmounted, ref, watch } from 'vue'

import AppButton from '@/components/common/AppButton.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmText?: string
    variant?: 'primary' | 'danger'
    /** 请求在途:两个按钮都禁用,防重复提交 */
    busy?: boolean
  }>(),
  { confirmText: '确认', variant: 'primary', busy: false },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()

const cancelEl = ref<InstanceType<typeof AppButton> | null>(null)

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && !props.busy) emit('cancel')
}

// 打开时:焦点给「取消」+ 挂 Esc 监听;关闭时移除,不做常驻监听
watch(
  () => props.open,
  (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      document.addEventListener('keydown', onKeydown)
      void nextTick(() => {
        const el = cancelEl.value?.$el as HTMLElement | undefined
        el?.focus()
      })
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
)

onUnmounted(() => {
  if (typeof document !== 'undefined') document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div v-if="open" class="scrim" role="dialog" aria-modal="true" @click.self="!busy && emit('cancel')">
    <div class="dialog">
      <h2 class="dialog__title">{{ title }}</h2>
      <p class="dialog__message">{{ message }}</p>

      <div class="dialog__foot">
        <AppButton ref="cancelEl" data-testid="dialog-cancel" :disabled="busy" @click="emit('cancel')">
          取消
        </AppButton>
        <AppButton
          data-testid="dialog-confirm"
          :variant="variant"
          :disabled="busy"
          @click="emit('confirm')"
        >
          {{ busy ? '处理中…' : confirmText }}
        </AppButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrim {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
}

.dialog {
  width: min(420px, calc(100% - var(--sp-6)));
  padding: var(--sp-4);
  background: var(--bg-panel);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-pop);
}

.dialog__title {
  font-size: var(--fs-lg);
  font-weight: 600;
}

.dialog__message {
  margin-top: var(--sp-2);
  color: var(--text-secondary);
  font-size: var(--fs-md);
  line-height: var(--lh-base);
  word-break: break-word;
}

.dialog__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  margin-top: var(--sp-4);
}
</style>