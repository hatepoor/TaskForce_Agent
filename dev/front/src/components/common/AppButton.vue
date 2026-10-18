<script setup lang="ts">
// 全站唯一按钮原语:视图不再另写按钮;键盘焦点环由 base.css 全局提供。
// 层级:primary = 墨黑实底(唯一强动作)、ghost = 纸面描边(次级)、danger = 仅文字。
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
  height: var(--ctl-h);
  padding: 0 var(--sp-3);
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
  line-height: var(--lh-tight);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  transition:
    background var(--t-fast),
    color var(--t-fast),
    border-color var(--t-fast);
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:focus-visible {
  outline: none;
  box-shadow: var(--focus-glow);
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 次级:纸面底 + 发丝描边,悬停只加深描边,不改变层级 */
.btn--ghost {
  border-color: var(--border-strong);
  background: var(--bg-raised);
}

.btn--ghost:hover:not(:disabled) {
  border-color: var(--text-muted);
  background: var(--bg-raised);
  color: var(--text-primary);
}

/* 主操作:墨黑实底,全站同一个动作色 */
.btn--primary {
  background: var(--text-primary);
  color: var(--text-inverse);
}

.btn--primary:hover:not(:disabled) {
  background: #33302a;
}

.btn--danger {
  border-color: transparent;
  color: var(--danger);
}

.btn--danger:hover:not(:disabled) {
  background: var(--danger-soft);
  border-color: var(--danger);
}
</style>
