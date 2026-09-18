<script setup lang="ts">
// 对话主视图:消息列表 + 输入区 + 会话身份同步(模块 07 装配)。
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import Composer from '@/components/chat/Composer.vue'
import MessageList from '@/components/chat/MessageList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useChatStream } from '@/composables/useChatStream'
import { useTaskWatch } from '@/composables/useTaskWatch'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'

const chat = useChatStore()
const stream = useChatStream()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

// 后台任务监视:派发后全批完成自动出汇总,用户无需再问一句
useTaskWatch()

const composer = ref<InstanceType<typeof Composer> | null>(null)

/** 空态示例问句:点击**填入**输入框,不直接发送(UI-DESIGN §3.4) */
const EXAMPLES = [
  { text: '总结一下 docs/ 里关于记忆设计的那部分', tag: '知识库检索' },
  { text: '查一下 pgvector 0.7 的 HNSW 参数默认值,给出建议', tag: '联网调研 + 知识库检索' },
  { text: '写段脚本统计 docs/ 下每个 md 的字数', tag: '沙箱执行' },
]

const routeThreadId = computed(() => {
  const raw = route.params.threadId
  return typeof raw === 'string' ? raw : ''
})

// 深链:URL 带 threadId 时切过去;刷新后 URL 为空,由 localStorage 存的当前会话兜底
watch(
  routeThreadId,
  (id) => {
    if (id !== '' && id !== chat.currentThreadId) chat.switchThread(id)
  },
  { immediate: true },
)

// 反向同步:切会话后 URL 跟上(hash 模式,不经过后端路由)
watch(
  () => chat.currentThreadId,
  (id) => {
    if (routeThreadId.value !== id) void router.replace({ name: 'chat', params: { threadId: id } })
  },
  { immediate: true },
)

onMounted(() => {
  chat.ensureHydrated()
})

const lastUserText = computed(() => {
  const users = chat.items.flatMap((it) => (it.kind === 'user' ? [it.text] : []))
  return users[users.length - 1] ?? ''
})

/** 重试:重发最后一条用户消息,不重复插气泡(仅请求失败/零输出情形给这个入口) */
function onRetry(): void {
  const text = lastUserText.value
  if (text === '') return
  void stream.resend(text)
}

async function onCopy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    ui.toast('已复制已生成内容')
  } catch {
    ui.toast('复制失败,请手动选中复制', 'error')
  }
}
</script>

<template>
  <section class="view" data-testid="chat-view">
    <header class="view__head">
      <h1 class="view__title">{{ chat.currentTitle || '新会话' }}</h1>
      <span class="view__tid" :title="chat.currentThreadId" data-testid="current-thread-id">
        {{ chat.currentThreadId }}
      </span>
    </header>

    <div v-if="chat.loadingHistory" class="view__skeleton" data-testid="history-loading" aria-label="正在加载历史消息">
      <div v-for="i in 3" :key="i" class="sk">
        <span class="sk__line sk__line--user" />
        <span class="sk__line" />
        <span class="sk__line sk__line--short" />
      </div>
    </div>

    <EmptyState
      v-else-if="chat.items.length === 0"
      title="本地 Agent 工作台"
      hint="可以问我:本地知识库里的文档、需要联网查的最新资料、需要跑起来验证的代码。"
    >
      <ul class="examples">
        <li v-for="ex in EXAMPLES" :key="ex.text">
          <button
            type="button"
            class="examples__btn"
            :data-testid="`example-${ex.tag}`"
            @click="composer?.fill(ex.text)"
          >
            <span class="examples__text">{{ ex.text }}</span>
            <span class="examples__tag">{{ ex.tag }}</span>
          </button>
        </li>
      </ul>
    </EmptyState>

    <MessageList
      v-else
      :items="chat.items"
      :thread-id="chat.currentThreadId"
      :streaming="chat.isStreaming"
      @retry="onRetry"
      @copy="onCopy"
    />

    <Composer ref="composer" />
  </section>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.view__head {
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
  min-width: 0;
  padding: var(--sp-4) var(--sp-4) 0;
  width: min(var(--measure-text), 100%);
  margin: 0 auto;
}

.view__title {
  font-size: var(--fs-xl);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.view__tid {
  flex: none;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.view__loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

/* 历史回填骨架屏:比"正在加载…"一行字更接近最终版式,回填完成不跳版 */
.view__skeleton {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  width: min(var(--measure-text), 100%);
  margin: 0 auto;
  padding: var(--sp-5) var(--sp-4);
  overflow: hidden;
}

.sk {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.sk__line {
  height: 12px;
  border-radius: var(--r-sm);
  background: var(--bg-raised);
  animation: sk-pulse 1.4s ease-in-out infinite;
}

.sk__line--user {
  width: 44%;
  align-self: flex-end;
  height: 28px;
  border-radius: var(--r-lg) var(--r-lg) var(--r-sm) var(--r-lg);
}

.sk__line--short {
  width: 62%;
}

@keyframes sk-pulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .sk__line {
    animation: none;
  }
}

.examples {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  width: 520px;
  max-width: 100%;
  margin: var(--sp-3) 0 0;
  padding: 0;
  list-style: none;
}

.examples__btn {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  text-align: left;
  cursor: pointer;
}

.examples__btn:hover {
  border-color: var(--border-strong);
  background: var(--bg-hover);
}

.examples__text {
  color: var(--text-primary);
  font-size: var(--fs-md);
}

.examples__tag {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}
</style>