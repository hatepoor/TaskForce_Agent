<script setup lang="ts">
// 上下文栏会话列表(模块 06):新建 / 切换 / 当前高亮 / 本地标题 / 删除(确认弹窗)。
// 数据 = 后端 meta(B2,已按最近活跃排序)+ 本地新建但还没 checkpoint 的会话。
import { computed, onMounted, ref } from 'vue'

import { errText } from '@/api/http'
import AppButton from '@/components/common/AppButton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Spinner from '@/components/common/Spinner.vue'
import ConfirmDialog from '@/components/settings/ConfirmDialog.vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { fmtRelative } from '@/utils/time'

import SessionItem from './SessionItem.vue'

const chat = useChatStore()
const ui = useUiStore()

const rows = computed(() =>
  chat.sessionList.map((row) => ({
    ...row,
    timeText: row.lastActiveAt > 0 ? fmtRelative(row.lastActiveAt) : '',
  })),
)

// 删除确认:待删会话 id;空串 = 弹窗关闭。busy 期禁用双按钮防重复提交。
const confirmId = ref('')
const removing = ref(false)
const confirmTitle = computed(
  () => chat.sessionList.find((row) => row.threadId === confirmId.value)?.title || '新会话',
)

function askRemove(threadId: string): void {
  confirmId.value = threadId
}

async function onConfirmRemove(): Promise<void> {
  const id = confirmId.value
  if (id === '') return
  removing.value = true
  try {
    const res = await chat.removeThread(id)
    if (res === 'streaming') ui.toast('该会话正在执行任务,稍后再删除', 'error')
    else ui.toast('会话已删除')
  } catch (e) {
    ui.toast(`删除会话失败:${errText(e)}`, 'error')
  } finally {
    removing.value = false
    confirmId.value = ''
  }
}

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
      compact
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
        @remove="askRemove"
      />
    </ul>

    <ConfirmDialog
      :open="confirmId !== ''"
      title="删除会话"
      :message="`「${confirmTitle}」的历史消息与后台任务记录将被删除,不可恢复。`"
      confirm-text="删除"
      variant="danger"
      :busy="removing"
      data-testid="thread-delete-dialog"
      @confirm="onConfirmRemove"
      @cancel="confirmId = ''"
    />
  </div>
</template>

<style scoped>
.threads {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.threads__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
}

/* 新建会话 = 索引栏的主操作:墨黑实底,给列表一个明确起点 */
.threads__new {
  width: 100%;
  height: 34px;
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