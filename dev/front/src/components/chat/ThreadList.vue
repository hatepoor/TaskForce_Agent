<script setup lang="ts">
// 上下文栏会话列表(模块 06):新建 / 切换 / 当前高亮 / 本地标题。
// 数据 = 后端 meta(B2,已按最近活跃排序)+ 本地新建但还没 checkpoint 的会话。
import { computed, onMounted } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useChatStore } from '@/stores/chat'
import { fmtRelative } from '@/utils/time'

import SessionItem from './SessionItem.vue'

const chat = useChatStore()

const rows = computed(() =>
  chat.sessionList.map((row) => ({
    ...row,
    timeText: row.lastActiveAt > 0 ? fmtRelative(row.lastActiveAt) : '',
  })),
)

onMounted(() => {
  void chat.loadThreads()
})
</script>

<template>
  <div class="threads" data-testid="thread-list">
    <AppButton variant="primary" class="threads__new" data-testid="new-thread" @click="chat.newThread()">
      + 新建会话
    </AppButton>

    <p v-if="chat.threadsError" class="threads__error" data-testid="threads-error">
      <span class="threads__error-text">{{ chat.threadsError }}</span>
      <AppButton @click="chat.loadThreads()">重试</AppButton>
    </p>

    <p v-if="chat.loadingThreads && rows.length === 0" class="threads__loading">
      <Spinner />
      <span>加载会话列表…</span>
    </p>

    <EmptyState
      v-else-if="rows.length === 0"
      title="还没有会话"
      hint="点「新建会话」开始,新会话首次发消息后才会写进后端列表。"
    />

    <ul v-else class="threads__list">
      <SessionItem
        v-for="row in rows"
        :key="row.threadId"
        :thread-id="row.threadId"
        :title="row.title"
        :active="row.threadId === chat.currentThreadId"
        :time-text="row.timeText"
        @select="chat.switchThread($event)"
      />
    </ul>
  </div>
</template>

<style scoped>
.threads {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-height: 0;
}

.threads__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
}

/* 新建会话 = 上下文栏的主操作:占满宽度、主色底,给列表一个视觉起点 */
.threads__new {
  width: 100%;
  height: 32px;
}

.threads__error {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2);
  border: 1px solid var(--danger);
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
}

.threads__error-text {
  flex: 1;
  min-width: 0;
  color: var(--danger);
  overflow-wrap: anywhere;
}

.threads__loading {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2);
  color: var(--text-muted);
  font-size: var(--fs-sm);
}
</style>