<script setup lang="ts">
// memory 确认卡:提案引用块 + 「忽略」/「记入记忆」(UI-DESIGN §3.3)。
// 默认焦点在「忽略」——回车不误触写入;两个按钮都走 POST /chat/confirm(true/false)。
import { computed, nextTick, onMounted, ref } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import { useChatStream } from '@/composables/useChatStream'
import { useChatStore } from '@/stores/chat'
import type { InterruptItem } from '@/types/chat'
import { fmtClock } from '@/utils/time'

const props = defineProps<{ item: InterruptItem }>()
const chat = useChatStore()
const stream = useChatStream()

const root = ref<HTMLElement | null>(null)
const ignoreBtn = ref<InstanceType<typeof AppButton> | null>(null)

const pendingState = computed(() => props.item.status === 'waiting' || props.item.status === 'submitting')

async function decide(approved: boolean): Promise<void> {
  if (props.item.status !== 'waiting' || chat.isStreaming) return
  chat.resolvePending({ status: 'submitting', approved })
  await stream.confirm(approved)
}

onMounted(() => {
  if (props.item.status !== 'waiting') return
  root.value?.scrollIntoView({ block: 'nearest' })
  // 默认焦点落在「忽略」:直接回车也不会写入记忆
  void nextTick(() => {
    const el = ignoreBtn.value?.$el
    if (el instanceof HTMLElement) el.focus()
  })
})
</script>

<template>
  <div ref="root" class="mem" data-testid="interrupt-memory">
    <template v-if="pendingState">
      <p class="mem__title">记忆写入确认</p>
      <p class="mem__lead">将写入长期记忆(仅存于你本地的 pgvector):</p>
      <blockquote class="mem__quote" data-testid="memory-proposal">{{ item.text }}</blockquote>

      <div class="mem__foot">
        <span class="mem__source">来源:本轮对话自动提案</span>
        <span class="mem__actions">
          <AppButton
            ref="ignoreBtn"
            :disabled="item.status === 'submitting'"
            data-testid="memory-ignore"
            @click="decide(false)"
          >
            忽略
          </AppButton>
          <AppButton
            variant="primary"
            :disabled="item.status === 'submitting'"
            data-testid="memory-approve"
            @click="decide(true)"
          >
            记入记忆
          </AppButton>
        </span>
      </div>
    </template>

    <template v-else-if="item.status === 'resolved'">
      <p class="mem__done" data-testid="interrupt-resolved">
        <span class="mem__mark">{{ item.approved === true ? '✓' : '⊘' }}</span>
        <span class="mem__done-text">{{ item.approved === true ? '已记入长期记忆' : '未记入长期记忆' }}</span>
        <span class="mem__time">{{ fmtClock(item.at) }}</span>
      </p>
    </template>

    <template v-else>
      <p class="mem__failed" data-testid="interrupt-failed">
        <span class="mem__mark">!</span>
        <span>该挂起已失效{{ item.error ? `:${item.error}` : '' }}</span>
      </p>
    </template>
  </div>
</template>

<style scoped>
.mem {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border-left: 2px solid var(--accent);
  border-radius: 0 var(--r-md) var(--r-md) 0;
  background: var(--bg-raised);
}

.mem__title {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.mem__lead {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.mem__quote {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-left: 2px solid var(--border-strong);
  background: var(--bg-input);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  font-size: var(--fs-lg);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.mem__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
}

.mem__source,
.mem__time {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.mem__actions {
  display: flex;
  gap: var(--sp-2);
}

.mem__done,
.mem__failed {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
}

.mem__done {
  color: var(--text-secondary);
}

.mem__failed {
  color: var(--warning);
}

.mem__done-text {
  flex: 1;
  min-width: 0;
}
</style>