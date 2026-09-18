<script setup lang="ts">
// ask 问询卡:问题文本 + 内联输入 + 提交(UI-DESIGN §3.3)。
// 提交 → 原地折叠为已答态,新流追加到**同一轮次**(轮次不结束)。
import { computed, nextTick, onMounted, ref } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import { useChatStream } from '@/composables/useChatStream'
import { useChatStore } from '@/stores/chat'
import type { InterruptItem } from '@/types/chat'
import { fmtClock } from '@/utils/time'

const props = defineProps<{ item: InterruptItem }>()
const chat = useChatStore()
const stream = useChatStream()

const draft = ref('')
const composing = ref(false)
const root = ref<HTMLElement | null>(null)
const box = ref<HTMLTextAreaElement | null>(null)

const pendingState = computed(() => props.item.status === 'waiting' || props.item.status === 'submitting')
const canSubmit = computed(() => draft.value.trim() !== '' && props.item.status === 'waiting' && !chat.isStreaming)

async function submit(): Promise<void> {
  const text = draft.value.trim()
  if (text === '' || props.item.status !== 'waiting' || chat.isStreaming) return
  chat.resolvePending({ status: 'submitting', answer: text })
  draft.value = ''
  // 400(挂起已在别处恢复)由 store 的 failTurn 收尾:卡片标失效 + toast
  await stream.answer(text)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key !== 'Enter') return
  if (composing.value || e.isComposing) return // 输入法选词回车不算提交
  if (e.shiftKey) return // 换行
  e.preventDefault()
  void submit()
}

onMounted(() => {
  if (props.item.status !== 'waiting') return
  root.value?.scrollIntoView({ block: 'nearest' })
  void nextTick(() => box.value?.focus())
})
</script>

<template>
  <div ref="root" class="ask" data-testid="interrupt-ask">
    <template v-if="pendingState">
      <p class="ask__title">需要补充信息</p>
      <p class="ask__question">{{ item.text }}</p>

      <textarea
        ref="box"
        v-model="draft"
        class="ask__input"
        rows="2"
        placeholder="输入你的回答…"
        :disabled="item.status === 'submitting'"
        data-testid="ask-input"
        @keydown="onKeydown"
        @compositionstart="composing = true"
        @compositionend="composing = false"
      />

      <div class="ask__foot">
        <span class="ask__hint">Enter 发送 · Shift+Enter 换行</span>
        <AppButton
          variant="primary"
          :disabled="!canSubmit"
          data-testid="ask-submit"
          @click="submit"
        >
          {{ item.status === 'submitting' ? '提交中…' : '发送' }}
        </AppButton>
      </div>
    </template>

    <template v-else-if="item.status === 'resolved'">
      <p class="ask__done" data-testid="interrupt-resolved">
        <span class="ask__mark">✓</span>
        <span class="ask__done-text">已补充回答 · “{{ item.answer }}”</span>
        <span class="ask__time">{{ fmtClock(item.at) }}</span>
      </p>
    </template>

    <template v-else>
      <p class="ask__failed" data-testid="interrupt-failed">
        <span class="ask__mark">!</span>
        <span>该挂起已失效{{ item.error ? `:${item.error}` : '' }}</span>
      </p>
    </template>
  </div>
</template>

<style scoped>
.ask {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border-left: 2px solid var(--accent);
  border-radius: 0 var(--r-md) var(--r-md) 0;
  background: var(--bg-raised);
}

.ask__title {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.ask__question {
  font-size: var(--fs-lg);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.ask__input {
  width: 100%;
  padding: var(--sp-2);
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  font-size: var(--fs-md);
  line-height: var(--lh-base);
  resize: vertical;
}

.ask__input:focus {
  border-color: var(--border-focus);
  outline: none;
}

.ask__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}

.ask__hint,
.ask__time {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.ask__done,
.ask__failed {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
}

.ask__done {
  color: var(--text-secondary);
}

.ask__failed {
  color: var(--warning);
}

.ask__done-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>