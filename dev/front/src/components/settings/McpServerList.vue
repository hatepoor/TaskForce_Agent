<script setup lang="ts">
// MCP 服务器列表容器:拍平字典 → 有序条目,空态兜底(UI-DESIGN §2.4)。
import EmptyState from '@/components/common/EmptyState.vue'

import McpServerItem from './McpServerItem.vue'
import type { ServerEntry } from './mcpModel'

defineProps<{ entries: ServerEntry[] }>()
const emit = defineEmits<{ test: [name: string]; delete: [name: string] }>()
</script>

<template>
  <EmptyState
    v-if="entries.length === 0"
    data-testid="mcp-empty"
    title="还没有 MCP 服务器"
    hint="点右上角「+ 添加」接入外部工具服务器;保存后从下一轮会话装配开始生效。"
  />

  <ul v-else class="list" data-testid="mcp-list">
    <li v-for="e in entries" :key="e.name">
      <McpServerItem :name="e.name" :config="e.config" @delete="emit('delete', $event)" />
    </li>
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