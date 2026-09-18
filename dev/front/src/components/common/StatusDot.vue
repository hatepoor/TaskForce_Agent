<script setup lang="ts">
// 四态状态点:ok 绿 / warn 黄 / err 红 / unknown 灰(UI-DESIGN §1.2)。
defineProps<{ state: 'ok' | 'warn' | 'err' | 'unknown' }>()
</script>

<template>
  <span class="dot" :class="`dot--${state}`" />
</template>

<style scoped>
.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--r-full);
}

.dot--ok {
  background: var(--success);
}

.dot--warn {
  background: var(--warning);
}

.dot--err {
  background: var(--danger);
}

.dot--unknown {
  background: var(--text-muted);
}
</style>