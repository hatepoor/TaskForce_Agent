<script setup lang="ts">
// 右下角轻提示宿主:3s 自动消失、最多 3 条(UI-DESIGN §1.3);动效仅 120ms 淡入淡出。
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <TransitionGroup name="toast" tag="div" class="toast-host" aria-live="polite">
    <div v-for="t in ui.toasts" :key="t.id" class="toast" :class="`toast--${t.type}`" role="status">
      <span class="toast__dot" />
      <span class="toast__msg">{{ t.msg }}</span>
    </div>
  </TransitionGroup>
</template>

<style scoped>
.toast-host {
  position: fixed;
  right: var(--sp-4);
  bottom: var(--sp-4);
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--sp-2);
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  max-width: 360px;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-pop);
  color: var(--text-primary);
  font-size: var(--fs-md);
  line-height: var(--lh-base);
}

.toast__dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: var(--r-full);
}

.toast--success .toast__dot {
  background: var(--success);
}

.toast--error .toast__dot {
  background: var(--danger);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--t-fast);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}
</style>