<script setup lang="ts">
// AI 正文:流式期纯文本 pre-wrap + 光标,结束后才走 Markdown(半截语法渲染不出正确结果,
// 顺便避掉每 token 一次 marked + DOMPurify 的 O(n²) 开销,ARCHITECTURE 坑 5)。
import { computed, onUnmounted, ref, watch } from 'vue'

import type { AssistantItem, UsageEvent } from '@/types/chat'
import { renderMarkdown } from '@/utils/markdown'

import AiAvatar from './AiAvatar.vue'
import ErrorNotice from './ErrorNotice.vue'
import UsageBadge from './UsageBadge.vue'

const props = defineProps<{ item: AssistantItem; cumulative?: UsageEvent }>()
const emit = defineEmits<{ retry: []; copy: [text: string] }>()

const html = computed(() => (props.item.streaming ? '' : renderMarkdown(props.item.text)))

/** 已开轮但还没有任何 token:头像呼吸 + 三点跳动,覆盖装配图/MCP/首字延迟这段等待 */
const thinking = computed(() => props.item.streaming && props.item.text === '')

const canRetry = computed(() => props.item.error !== undefined)
const canCopy = computed(() => props.item.error !== undefined && props.item.text.trim() !== '')

// 800ms 还没有任何事件 + 正文仍为空 → 补一行"正在路由…"(UI-DESIGN §3.4)
const waiting = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

watch(
  () => props.item.streaming && props.item.text === '',
  (on) => {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
    waiting.value = false
    if (on) {
      timer = setTimeout(() => {
        waiting.value = true
      }, 800)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  if (timer !== undefined) clearTimeout(timer)
})
</script>

<template>
  <div class="ai" data-testid="assistant-message">
    <AiAvatar :thinking="thinking" />

    <div class="ai__body">
      <p v-if="thinking" class="ai__thinking" data-testid="assistant-thinking">
        <span class="dots"><span /><span /><span /></span>
        <span v-if="waiting" class="ai__waiting">正在路由…</span>
      </p>

      <div v-if="item.streaming" class="ai__plain" data-testid="assistant-plain">
        {{ item.text }}<span v-if="item.text !== ''" class="ai__caret" />
      </div>
      <!-- eslint-disable-next-line vue/no-v-html — 内容已经 DOMPurify 清洗 -->
      <div v-else-if="item.text !== ''" class="ai__md" data-testid="assistant-markdown" v-html="html" />

      <p v-if="item.note" class="ai__note" data-testid="assistant-note">{{ item.note }}</p>

      <ErrorNotice
        v-if="item.error"
        :message="item.error.message"
        :status="item.error.status"
        :can-retry="canRetry"
        :can-copy="canCopy"
        @retry="emit('retry')"
        @copy="emit('copy', item.text)"
      />

      <UsageBadge v-if="item.usage" :usage="item.usage" :cumulative="cumulative" />
    </div>
  </div>
</template>

<style scoped>
.ai {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  min-width: 0;
}

.ai__body {
  flex: 1;
  min-width: 0;
}

.ai__thinking {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 26px;
}

/* 三点跳动:模型思考中的加载指示(不引骨架屏,UI-DESIGN §3.4 的无骨架屏约束保持) */
.dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dots span {
  width: 5px;
  height: 5px;
  border-radius: var(--r-full);
  background: var(--text-secondary);
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes dot-bounce {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.45;
  }
  40% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

.ai__waiting,
.ai__note {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.ai__plain {
  font-size: var(--fs-lg);
  line-height: var(--lh-body);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.ai__caret {
  display: inline-block;
  width: 1px;
  height: 1em;
  margin-left: 1px;
  vertical-align: text-bottom;
  background: var(--text-secondary);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.ai__md {
  font-size: var(--fs-lg);
  line-height: var(--lh-body);
  overflow-wrap: anywhere;
}

.ai__md :deep(p) + :deep(p) {
  margin-top: var(--sp-3);
}

/* 标题降一档(回答里的 h1 不该比页面标题还大),行距收紧 */
.ai__md :deep(h1),
.ai__md :deep(h2),
.ai__md :deep(h3),
.ai__md :deep(h4) {
  margin: var(--sp-4) 0 var(--sp-2);
  font-size: var(--fs-lg);
  font-weight: 600;
  line-height: var(--lh-tight);
  color: var(--text-primary);
}

.ai__md :deep(h1) + :deep(p),
.ai__md :deep(h2) + :deep(p),
.ai__md :deep(h3) + :deep(p) {
  margin-top: 0;
}

.ai__md :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.ai__md :deep(ul),
.ai__md :deep(ol) {
  margin: var(--sp-2) 0;
  padding-left: var(--sp-5);
}

.ai__md :deep(li + li) {
  margin-top: var(--sp-1);
}

.ai__md :deep(li) > :deep(p) {
  margin: 0;
}

.ai__md :deep(code) {
  padding: 1px 4px;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  font-family: var(--font-mono);
  font-size: var(--fs-code);
}

.ai__md :deep(pre) {
  margin: var(--sp-3) 0;
  padding: var(--sp-3);
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  overflow-x: auto;
  /* markdown 渲染抖动:给块级内容预留固有尺寸(UI-DESIGN §6.2 规则 7) */
  contain-intrinsic-size: auto 120px;
}

.ai__md :deep(pre code) {
  padding: 0;
  background: transparent;
  border: none;
  font-size: var(--fs-code);
  line-height: var(--lh-base);
}

.ai__md :deep(blockquote) {
  margin: var(--sp-3) 0;
  padding: var(--sp-1) 0 var(--sp-1) var(--sp-3);
  border-left: 2px solid var(--border-strong);
  color: var(--text-secondary);
}

.ai__md :deep(hr) {
  margin: var(--sp-4) 0;
  border: none;
  border-top: 1px solid var(--border-subtle);
}

.ai__md :deep(table) {
  margin: var(--sp-3) 0;
  border-collapse: collapse;
  font-size: var(--fs-md);
  contain-intrinsic-size: auto 80px;
}

.ai__md :deep(th),
.ai__md :deep(td) {
  padding: var(--sp-1) var(--sp-2);
  border: 1px solid var(--border-subtle);
  text-align: left;
}

.ai__md :deep(th) {
  background: var(--bg-panel);
  color: var(--text-secondary);
  font-weight: 500;
}

.ai__md :deep(a) {
  overflow-wrap: anywhere;
}

/* 动作按钮行(重试/复制)与用量角标:统一到正文下方的 meta 区 */
.ai__md :deep(img) {
  max-width: 100%;
  border-radius: var(--r-md);
}
</style>