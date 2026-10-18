<script setup lang="ts">
// 底部输入区:Enter 发送 / Shift+Enter 换行 / 中文输入法组合态 / 流中禁用与「停止接收」
// (UI-DESIGN §3.4 加载态、§6.1 键盘、坑 4 单飞)。
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import { useChatStream } from '@/composables/useChatStream'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const stream = useChatStream()

const el = ref<HTMLTextAreaElement | null>(null)
const draft = ref('')
/** 中文输入法组合态:只判 e.isComposing 在部分输入法下不可靠,必须显式维护 */
const composing = ref(false)
/** 上一次真正发出去的文本:请求失败且零输出时留在框里,并提示改走「重试」 */
const sentText = ref('')

const blocked = computed(() => chat.isStreaming || chat.pending !== null)
const canSend = computed(() => draft.value.trim() !== '' && !blocked.value)

// 首轮装配/路由可能较慢:1s 后给"正在思考…"反馈,防重复点击
const slowStart = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

watch(
  () => chat.isStreaming && !chat.turnHasOutput,
  (on) => {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
    slowStart.value = false
    if (on) {
      timer = setTimeout(() => {
        slowStart.value = true
      }, 1000)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  if (timer !== undefined) clearTimeout(timer)
})

// 有输出 = 这一轮真的发出去了,清空草稿;零输出失败则保留,内容不丢
watch(
  () => chat.turnHasOutput,
  (on) => {
    if (on) {
      draft.value = ''
      sentText.value = ''
    }
  },
)

watch(
  () => chat.turn?.status,
  (status) => {
    if (status === 'done' || status === 'aborted') {
      draft.value = ''
      sentText.value = ''
    }
  },
)

const failedNoOutput = computed(() => chat.turn?.status === 'error' && !chat.turnHasOutput)

const hint = computed(() => {
  if (chat.pending?.sub === 'plan') return '请先处理上方的调研计划确认'
  if (chat.pending !== null) return '请先回答上方问题'
  if (chat.isStreaming) return slowStart.value ? '正在思考…' : '流式进行中'
  if (failedNoOutput.value && sentText.value !== '' && draft.value.trim() === sentText.value) {
    return '上一轮请求失败 · 直接发送会重复上一条,建议点上方「重试」'
  }
  return 'Enter 发送 · Shift+Enter 换行'
})

async function submit(): Promise<void> {
  if (!canSend.value) return
  const text = draft.value.trim()
  sentText.value = text
  await stream.send(text)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key !== 'Enter') return
  if (composing.value || e.isComposing) return // 选词回车不算发送
  if (e.shiftKey) return // 换行
  e.preventDefault()
  void submit()
}

function autosize(): void {
  const node = el.value
  if (node === null) return
  node.style.height = 'auto'
  node.style.height = `${Math.min(node.scrollHeight, 160)}px`
}

watch(draft, () => {
  void nextTick(autosize)
})

/** 空态示例问句点击填入(不直接发送,UI-DESIGN §3.4)。 */
function fill(text: string): void {
  draft.value = text
  void nextTick(() => {
    el.value?.focus()
    autosize()
  })
}

defineExpose({ fill })
</script>

<template>
  <div class="composer">
    <div class="composer__inner">
      <div class="composer__box">
      <textarea
        ref="el"
        v-model="draft"
        class="composer__input"
        rows="1"
        placeholder="输入消息…"
        :disabled="blocked"
        data-testid="composer-input"
        @keydown="onKeydown"
        @compositionstart="composing = true"
        @compositionend="composing = false"
      />
      <AppButton
        v-if="chat.isStreaming"
        class="composer__action"
        data-testid="composer-stop"
        @click="stream.abort()"
      >
        停止接收
      </AppButton>
      <AppButton
        v-else
        variant="primary"
        class="composer__action"
        :disabled="!canSend"
        data-testid="composer-send"
        @click="submit"
      >
        发送
      </AppButton>
    </div>

      <p class="composer__hint" data-testid="composer-hint">{{ hint }}</p>
    </div>
  </div>
</template>

<style scoped>
/* 分隔线全宽贯穿主区,内容仍按阅读栏收窄居中 */
.composer {
  flex: none;
  padding: var(--sp-4) var(--sp-4) var(--sp-5);
  border-top: 1px solid var(--border-subtle);
}

.composer__inner {
  width: min(var(--measure-text), 100%);
  margin: 0 auto;
}

/* 输入盒是对话页的落笔处:纸面底 + 发丝描边,聚焦只换描边色 */
.composer__box {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-2);
  padding: 10px 12px;
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-md);
  transition: border-color var(--t-fast);
}

.composer__box:focus-within {
  border-color: var(--border-focus);
}

.composer__input {
  flex: 1;
  min-height: 24px;
  max-height: 160px;
  padding: 4px 2px 0;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  font-size: var(--fs-lg);
  line-height: var(--lh-body);
  overflow-y: auto;
}

.composer__input::placeholder {
  color: var(--text-muted);
}

.composer__input:disabled {
  cursor: not-allowed;
}

.composer__action {
  flex: none;
  height: var(--ctl-h);
  border-radius: var(--r-sm);
}

.composer__hint {
  margin-top: var(--sp-2);
  padding: 0 2px;
  color: var(--text-muted);
  font-size: var(--fs-xs);
  text-align: left;
}
</style>