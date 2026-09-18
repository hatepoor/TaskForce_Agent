<script setup lang="ts">
// 挂起卡容器:按 interrupt.kind 分派(UI-DESIGN §3.3)。
// unknown 绝不猜类型——猜错会把 approved=true 之类写进对话(坑 2),只给安全出口。
import AppButton from '@/components/common/AppButton.vue'
import { useChatStore } from '@/stores/chat'
import type { InterruptItem } from '@/types/chat'

import AskInterruptCard from './AskInterruptCard.vue'
import MemoryConfirmCard from './MemoryConfirmCard.vue'

const props = defineProps<{ item: InterruptItem }>()
const chat = useChatStore()
</script>

<template>
  <AskInterruptCard v-if="props.item.sub === 'ask'" :item="props.item" />
  <MemoryConfirmCard v-else-if="props.item.sub === 'memory'" :item="props.item" />
  <div v-else class="unknown" data-testid="interrupt-unknown">
    <p class="unknown__title">检测到未知类型的挂起</p>
    <p class="unknown__text">{{ props.item.text }}</p>
    <p class="unknown__hint">为避免把错误内容写进对话,这里不提供恢复入口;可以新开一个会话继续。</p>
    <AppButton data-testid="interrupt-new-thread" @click="chat.newThread()">新开会话</AppButton>
  </div>
</template>

<style scoped>
.unknown {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border-left: 2px solid var(--warning);
  border-radius: 0 var(--r-md) var(--r-md) 0;
  background: var(--bg-raised);
}

.unknown__title {
  color: var(--warning);
  font-size: var(--fs-sm);
}

.unknown__text {
  font-size: var(--fs-lg);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.unknown__hint {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}
</style>