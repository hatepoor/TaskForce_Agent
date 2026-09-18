<script setup lang="ts">
// 全站唯一按钮原语:视图不再另写按钮;键盘焦点环由 base.css 全局提供(UI-DESIGN §5.1)。
// danger 只用于删除 / 危险操作。
withDefaults(
  defineProps<{
    variant?: 'primary' | 'ghost' | 'danger'
    type?: 'button' | 'submit'
    disabled?: boolean
  }>(),
  { variant: 'ghost', type: 'button', disabled: false },
)
</script>

<template>
  <button class="btn" :class="`btn--${variant}`" :type="type" :disabled="disabled">
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-1);
  height: 28px;
  padding: 0 var(--sp-3);
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-md);
  line-height: var(--lh-tight);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  transition:
    background var(--t-fast),
    color var(--t-fast),
    border-color var(--t-fast);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn--ghost {
  border-color: var(--border-strong);
}

.btn--ghost:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn--primary {
  background: var(--accent);
  color: var(--text-inverse);
}

.btn--primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn--danger {
  border-color: var(--danger);
  color: var(--danger);
}

.btn--danger:hover:not(:disabled) {
  background: var(--danger-soft);
}
</style>