<script setup lang="ts">
// 上下文栏(240px):按路由切换内部列表(UI-DESIGN §1.1/§1.3)。
// 对话=会话列表,知识库=文档列表,记忆=记忆条目,设置=节列表。
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import ThreadList from '@/components/chat/ThreadList.vue'
import DocMiniList from '@/components/knowledge/DocMiniList.vue'
import MemoryMiniList from '@/components/memory/MemoryMiniList.vue'
import SettingsNav from '@/components/settings/SettingsNav.vue'

const emit = defineEmits<{ collapse: [] }>()

const route = useRoute()

type PanelKind = 'chat' | 'knowledge' | 'memory' | 'settings' | 'none'

const kind = computed<PanelKind>(() => {
  const path = route.path
  if (path.startsWith('/chat')) return 'chat'
  if (path.startsWith('/knowledge')) return 'knowledge'
  if (path.startsWith('/memory')) return 'memory'
  if (path.startsWith('/settings')) return 'settings'
  return 'none'
})

const TITLES: Record<PanelKind, string> = {
  chat: '会话列表',
  knowledge: '文档列表',
  memory: '记忆条目',
  settings: '节列表',
  none: '',
}

const title = computed(() => TITLES[kind.value])
</script>

<template>
  <aside class="panel" aria-label="上下文栏">
    <header class="panel__head">
      <span class="panel__title">{{ title }}</span>
      <button
        type="button"
        class="panel__collapse"
        title="折叠上下文栏"
        aria-label="折叠上下文栏"
        @click="emit('collapse')"
      >
        «
      </button>
    </header>
    <div class="panel__body">
      <ThreadList v-if="kind === 'chat'" />
      <DocMiniList v-else-if="kind === 'knowledge'" />
      <MemoryMiniList v-else-if="kind === 'memory'" />
      <SettingsNav v-else-if="kind === 'settings'" />
      <p v-else class="panel__ph">当前页面没有侧栏内容</p>
    </div>
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  overflow: hidden;
}

.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-3) var(--sp-2);
  border-bottom: 1px solid var(--border-subtle);
}

.panel__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel__collapse {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
}

.panel__collapse:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.panel__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: var(--sp-3);
  overflow-y: auto;
}

.panel__ph {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}
</style>