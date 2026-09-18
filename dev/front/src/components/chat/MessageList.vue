<script setup lang="ts">
// 消息列表滚动容器:贴底策略六规则(UI-DESIGN §6.2)。
// 挂起卡/新轮次强制滚入;流式追加仅在贴底时跟随,用户上滚时不打断阅读。
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import type { ChatItem } from '@/types/chat'

import TurnBlock from './TurnBlock.vue'

const props = defineProps<{ items: ChatItem[]; threadId: string; streaming: boolean }>()
const emit = defineEmits<{ retry: []; copy: [text: string] }>()

const BOTTOM_THRESHOLD = 48

const el = ref<HTMLElement | null>(null)
const pinned = ref(true)
/** 不贴底就给回底入口:流中上滚看历史时提示有新内容,流结束后同样保留(UI-DESIGN §6.2 规则 4) */
const showPill = computed(() => !pinned.value)

/** 切换会话时按会话恢复滚动位置 */
const scrollMemo = new Map<string, number>()

const groups = computed(() => {
  const out: { key: string; items: ChatItem[] }[] = []
  for (const it of props.items) {
    const last = out[out.length - 1]
    if (it.kind === 'user' || last === undefined) out.push({ key: it.id, items: [it] })
    else last.items.push(it)
  }
  return out
})

const userCount = computed(() => props.items.filter((it) => it.kind === 'user').length)
const interruptCount = computed(() => props.items.filter((it) => it.kind === 'interrupt').length)
/** 正文增长也要跟随(长度不变,只有 text 在变) */
const textLength = computed(() =>
  props.items.reduce((n, it) => n + (it.kind === 'assistant' ? it.text.length : 0), 0),
)

function nearBottom(): boolean {
  const node = el.value
  if (node === null) return true
  return node.scrollHeight - node.scrollTop - node.clientHeight <= BOTTOM_THRESHOLD
}

function toBottom(): void {
  const node = el.value
  if (node === null) return
  node.scrollTop = node.scrollHeight
  pinned.value = true
  scrollMemo.set(props.threadId, node.scrollTop)
}

function onScroll(): void {
  const node = el.value
  if (node === null) return
  pinned.value = nearBottom()
  scrollMemo.set(props.threadId, node.scrollTop)
}

// 规则 1:新轮次(用户消息)无条件滚到底
watch(userCount, () => {
  pinned.value = true
  void nextTick(toBottom)
})

// 规则 2:流式追加仅当贴底才跟随;规则 4:不贴底就亮出回底胶囊
watch([textLength, () => props.items.length], () => {
  if (pinned.value) void nextTick(toBottom)
})

// 规则 5:挂起卡出现强制滚入视野一次
watch(interruptCount, () => {
  pinned.value = true
  void nextTick(toBottom)
})

// 规则 6:切换会话恢复上次位置,无记录则到底
watch(
  () => props.threadId,
  () => {
    void nextTick(() => {
      const node = el.value
      if (node === null) return
      const memo = scrollMemo.get(props.threadId)
      if (memo === undefined) {
        toBottom()
        return
      }
      node.scrollTop = memo
      pinned.value = nearBottom()
    })
  },
)

onMounted(() => {
  toBottom()
})
</script>

<template>
  <div class="list">
    <div ref="el" class="list__scroll" data-testid="message-list" @scroll.passive="onScroll">
      <ul class="list__inner">
        <li v-for="g in groups" :key="g.key" class="list__turn">
          <TurnBlock :items="g.items" @retry="emit('retry')" @copy="emit('copy', $event)" />
        </li>
      </ul>
    </div>

    <button
      v-if="showPill"
      type="button"
      class="list__pill"
      data-testid="scroll-to-bottom"
      @click="toBottom"
    >
      ↓ 新内容
    </button>
  </div>
</template>

<style scoped>
.list {
  position: relative;
  flex: 1;
  min-height: 0;
}

.list__scroll {
  height: 100%;
  overflow-y: auto;
}

.list__inner {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  width: min(var(--measure-text), 100%);
  margin: 0 auto;
  padding: var(--sp-5) var(--sp-4);
  list-style: none;
}

.list__turn {
  display: flex;
  flex-direction: column;
}

.list__pill {
  position: absolute;
  right: var(--sp-4);
  bottom: var(--sp-4);
  width: 88px;
  height: 32px;
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-full);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  cursor: pointer;
  box-shadow: var(--shadow-pop-sm);
}

.list__pill:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>