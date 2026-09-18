<script setup lang="ts">
// 长期记忆管理页(模块 10):列表(source 徽标)+ 本地过滤 + 删除确认。
// 数据契约见 API-CONTRACT §2.4;后端固定 limit=100,UI 不承诺"显示全部"。
import { computed, nextTick, onActivated, onMounted, ref, watch } from 'vue'

import { errText } from '@/api/http'
import { removeMemory } from '@/api/memory'
import AppButton from '@/components/common/AppButton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Spinner from '@/components/common/Spinner.vue'
import DeleteMemoryDialog from '@/components/memory/DeleteMemoryDialog.vue'
import MemoryList from '@/components/memory/MemoryList.vue'
import MemoryToolbar from '@/components/memory/MemoryToolbar.vue'
import {
  countText,
  filterMemories,
  limitHint,
  sortByCreatedAtDesc,
} from '@/components/memory/memoryFormat'
import { useMemoriesFeed } from '@/composables/useMemoriesFeed'
import { useUiStore } from '@/stores/ui'
import type { MemoryItem as MemoryRecord } from '@/types/memory'

const ui = useUiStore()

// 列表与上下文栏(侧栏)共用一份数据源:侧栏点击写 highlightId,这里滚动定位并高亮
const {
  items,
  loading,
  error: loadError,
  highlightId,
  load: reload,
  removeMemory: dropMemory,
} = useMemoriesFeed()

const keyword = ref('')
/** 待删除条目;非空即弹确认框 */
const pending = ref<MemoryRecord | null>(null)
const deleting = ref(false)
const deleteError = ref('')

// 排序在视图侧再做一次:不依赖服务端顺序,时间缺失的条目也能稳定落到末尾
const sorted = computed(() => sortByCreatedAtDesc(items.value))
const visible = computed(() => filterMemories(sorted.value, keyword.value))
const countLabel = computed(() => countText(items.value.length, visible.value.length))
const limit = computed(() => limitHint(items.value.length))
const filterHint = computed(
  () => `没有包含「${keyword.value.trim()}」的记忆,清除过滤可看全部 ${items.value.length} 条。`,
)

/** 拉列表:失败在页面侧提示(侧栏那份只显示错误条,不重复弹 toast) */
async function load(): Promise<void> {
  await reload()
  if (loadError.value !== '') ui.toast(loadError.value, 'error')
}

// 侧栏点击 → 把对应条目滚入视野(高亮样式由 highlightId 透传给 MemoryList)
watch(highlightId, (key) => {
  if (key === '') return
  void nextTick(() => {
    const rows = [...document.querySelectorAll<HTMLElement>('[data-memory-key]')]
    rows.find((row) => row.dataset.memoryKey === key)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
})

// 视图被 KeepAlive 缓存:首次走 onMounted,之后每次切回本页用 onActivated 拉最新
// (对话里刚确认写入的记忆,切过来就能看到,不必手动点刷新)
let activatedOnce = false

onMounted(() => {
  void load()
})

onActivated(() => {
  if (activatedOnce) void load()
  activatedOnce = true
})

function askDelete(item: MemoryRecord): void {
  pending.value = item
  deleteError.value = ''
}

function cancelDelete(): void {
  if (deleting.value) return
  pending.value = null
  deleteError.value = ''
}

async function confirmDelete(): Promise<void> {
  const target = pending.value
  if (target === null || deleting.value) return
  deleting.value = true
  deleteError.value = ''
  try {
    await removeMemory(target.key)
    dropMemory(target.key) // 本地摘除:侧栏列表同步少一条
    pending.value = null
    ui.toast('已删除该条记忆')
  } catch (e) {
    // 失败保留弹窗与原文,便于直接重试
    deleteError.value = errText(e)
    ui.toast(deleteError.value, 'error')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <section class="view" data-testid="memory-view">
    <div class="view__inner">
      <header class="view__head">
        <h1 class="view__title">长期记忆</h1>
        <p class="view__lead">智能体记住的关于你的事实与偏好;仅存于本机 pgvector。</p>
      </header>

      <MemoryToolbar v-model="keyword" :count-text="countLabel" :loading="loading" @refresh="load" />

      <p v-if="limit" class="view__limit" data-testid="memory-limit-hint">{{ limit }}</p>

      <div v-if="loading && items.length === 0" class="view__loading" data-testid="memory-loading">
        <Spinner :size="16" />
        <span>正在读取长期记忆…</span>
      </div>

      <EmptyState
        v-else-if="loadError && items.length === 0"
        title="读取记忆失败"
        :hint="loadError"
        data-testid="memory-error"
      >
        <AppButton data-testid="memory-retry" @click="load">重试</AppButton>
      </EmptyState>

      <EmptyState
        v-else-if="items.length === 0"
        title="还没有长期记忆"
        hint="对话中说出值得记住的信息,或直接说「记住…」。"
        data-testid="memory-empty"
      />

      <EmptyState
        v-else-if="visible.length === 0"
        title="没有匹配的记忆"
        :hint="filterHint"
        data-testid="memory-filter-empty"
      >
        <AppButton data-testid="memory-filter-clear" @click="keyword = ''">清空过滤</AppButton>
      </EmptyState>

      <MemoryList v-else :items="visible" :highlight-key="highlightId" @delete="askDelete" />
    </div>

    <DeleteMemoryDialog
      v-if="pending"
      :content="pending.content"
      :deleting="deleting"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </section>
</template>

<style scoped>
.view {
  height: 100%;
  min-height: 0;
  padding: var(--sp-4) var(--sp-4) var(--sp-5);
  overflow-y: auto;
}

.view__inner {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  width: min(var(--measure-page), 100%);
  margin: 0 auto;
}

.view__title {
  font-size: var(--fs-xl);
  font-weight: 600;
}

.view__lead {
  margin-top: var(--sp-1);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

.view__limit {
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.view__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: var(--sp-6) 0;
  font-size: var(--fs-sm);
  color: var(--text-muted);
}
</style>