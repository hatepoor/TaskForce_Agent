<script setup lang="ts">
// 一个对话轮次 = 用户消息 + 轨迹 + AI 正文(UI-DESIGN §3.1)。
// 轨迹条按设计"聚合本轮全部 route 事件"渲染一条,固定排在用户消息之后。
import { computed } from 'vue'

import type { ChatItem } from '@/types/chat'

import AssistantMessage from './AssistantMessage.vue'
import InterruptCard from './InterruptCard.vue'
import RouteTrail from './RouteTrail.vue'
import UserBubble from './UserBubble.vue'

const props = defineProps<{ items: ChatItem[] }>()
const emit = defineEmits<{ retry: []; copy: [text: string] }>()

const user = computed(() => props.items.find((it) => it.kind === 'user'))
const routesClean = computed(() => props.items.flatMap((it) => (it.kind === 'route' ? [it.route] : [])))
const rest = computed(() => props.items.filter((it) => it.kind !== 'route' && it.kind !== 'user'))
const streaming = computed(() =>
  props.items.some((it) => it.kind === 'assistant' && it.streaming),
)
</script>

<template>
  <div class="turn" data-testid="turn-block">
    <UserBubble v-if="user !== undefined && user.kind === 'user'" :item="user" />

    <RouteTrail v-if="routesClean.length > 0" :routes="routesClean" :streaming="streaming" />

    <template v-for="it in rest" :key="it.id">
      <AssistantMessage
        v-if="it.kind === 'assistant'"
        :item="it"
        @retry="emit('retry')"
        @copy="emit('copy', $event)"
      />
      <!-- 挂起卡:按 interrupt.kind 分派(模块 08) -->
      <InterruptCard v-else-if="it.kind === 'interrupt'" :item="it" />
    </template>
  </div>
</template>

<style scoped>
.turn {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  /* 新轮次/回填时轻微入场(流式更新不会重挂载节点,因此不会反复播) */
  animation: turn-in 160ms ease-out;
}

@keyframes turn-in {
  from {
    opacity: 0;
    transform: translateY(3px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .turn {
    animation: none;
  }
}
</style>