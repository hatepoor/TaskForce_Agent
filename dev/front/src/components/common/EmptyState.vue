<script setup lang="ts">
// 空列表统一空态:一行标题 + 一行灰字说明 + 可选下一步动作(不放插画,UI-DESIGN §2.1)。
withDefaults(defineProps<{ title?: string; hint?: string }>(), { title: '', hint: '' })
</script>

<template>
  <div class="empty">
    <p v-if="title" class="empty__title">{{ title }}</p>
    <p v-if="hint" class="empty__hint">{{ hint }}</p>
    <div class="empty__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-6) var(--sp-4);
  text-align: center;
}

.empty__title {
  color: var(--text-secondary);
  font-size: var(--fs-md);
}

.empty__hint {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.empty__action {
  margin-top: var(--sp-2);
}
</style>