<script setup lang="ts">
// 加载指示;reduced-motion 下由 base.css 全局降速处理,不做额外分支。
withDefaults(defineProps<{ size?: number }>(), { size: 14 })
</script>

<template>
  <span
    class="spinner"
    :style="{ width: `${size}px`, height: `${size}px` }"
    role="status"
    aria-label="加载中"
  />
</template>

<style scoped>
.spinner {
  display: inline-block;
  border: 2px solid var(--border-strong);
  border-top-color: var(--text-secondary);
  border-radius: var(--r-full);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>