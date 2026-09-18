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
  height: 28px;
  padding: 0 var(--sp-2);
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-primary);
  font-size: var(--fs-md);
}

.input::placeholder {
  color: var(--text-muted);
}

.input:focus {
  border-color: var(--border-focus);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>