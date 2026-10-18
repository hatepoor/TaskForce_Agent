<script setup lang="ts">
// 全站唯一单行输入原语(多行输入由后续 Composer 按需另做)。
const model = defineModel<string>({ default: '' })

withDefaults(
  defineProps<{
    placeholder?: string
    type?: 'text' | 'password' | 'search'
    disabled?: boolean
  }>(),
  { placeholder: '', type: 'text', disabled: false },
)
</script>

<template>
  <input
    v-model="model"
    class="input"
    :type="type"
    :placeholder="placeholder"
    :disabled="disabled"
  />
</template>

<style scoped>
.input {
  width: 100%;
  height: var(--ctl-h);
  padding: 0 var(--sp-3);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-primary);
  font-size: var(--fs-md);
  transition:
    border-color var(--t-fast),
    box-shadow var(--t-fast),
    background var(--t-fast);
}

.input::placeholder {
  color: var(--text-muted);
}

.input:hover:not(:disabled):not(:focus) {
  border-color: var(--border-strong);
}

.input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: var(--focus-glow);
  background: var(--bg-raised);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>