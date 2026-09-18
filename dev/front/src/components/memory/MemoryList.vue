<script setup lang="ts">
// 记忆条目列表容器:行渲染 + 删除事件上抛;空态与加载态由 MemoryView 统一裁决(UI-DESIGN §2.3)。
import type { MemoryItem as MemoryRecord } from '@/types/memory'

import MemoryItem from './MemoryItem.vue'

defineProps<{
  items: MemoryRecord[]
  /** 侧栏点击定位到的条目 key(短暂高亮) */
  highlightKey?: string
}>()

const emit = defineEmits<{ delete: [item: MemoryRecord] }>()
</script>

<template>
  <ul class="list" data-testid="memory-list">
    <MemoryItem
      v-for="(item, i) in items"
      :key="item.key || `memory-${i}`"
      :item="item"
      :highlight="highlightKey !== undefined && item.key === highlightKey"
      @delete="emit('delete', $event)"
    />
  </ul>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
</style>