<script setup lang="ts">
// plan 计划确认卡(plan_0.1):计划快照 + 「取消」/「开始执行」(UI-DESIGN §3.3)。
// 快照是 Markdown 列表(标题 + 步骤项),走全站统一的 marked + DOMPurify 渲染;
// 默认焦点在「取消」——回车不误触派发;后端语义:resume='y' 执行,其他取消。
import { computed, nextTick, onMounted, ref } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import { useChatStream } from '@/composables/useChatStream'
import { useChatStore } from '@/stores/chat'
import type { InterruptItem } from '@/types/chat'
import { renderMarkdown } from '@/utils/markdown'
import { fmtClock } from '@/utils/time'

const props = defineProps<{ item: InterruptItem }>()
const chat = useChatStore()
const stream = useChatStream()

const root = ref<HTMLElement | null>(null)
const cancelBtn = ref<InstanceType<typeof AppButton> | null>(null)

const pendingState = computed(() => props.item.status === 'waiting' || props.item.status === 'submitting')
const planHtml = computed(() => renderMarkdown(props.item.text))

async function decide(approved: boolean): Promise<void> {
  if (props.item.status !== 'waiting' || chat.isStreaming) return
  chat.resolvePending({ status: 'submitting', approved })
  await stream.confirmPlan(approved ? 'y' : 'n')
}

onMounted(() => {
  if (props.item.status !== 'waiting') return
  root.value?.scrollIntoView({ block: 'nearest' })
  // 默认焦点落在「取消」:直接回车也不会派发任务
  void nextTick(() => {
    const el = cancelBtn.value?.$el
    if (el instanceof HTMLElement) el.focus()
  })
})
</script>

<template>
  <div ref="root" class="plan" data-testid="interrupt-plan">
    <template v-if="pendingState">
      <p class="plan__title">调研计划确认</p>
      <p class="plan__lead">智能体把需求拆成了以下步骤,确认后按依赖分批派发给子智能体执行:</p>
      <div class="plan__body" data-testid="plan-snapshot" v-html="planHtml" />

      <div class="plan__foot">
        <span class="plan__hint">执行期间可以继续对话,结果完成后自动汇总</span>
        <span class="plan__actions">
          <AppButton
            ref="cancelBtn"
            :disabled="item.status === 'submitting'"
            data-testid="plan-cancel"
            @click="decide(false)"
          >
            取消
          </AppButton>
          <AppButton
            variant="primary"
            :disabled="item.status === 'submitting'"
            data-testid="plan-approve"
            @click="decide(true)"
          >
            开始执行
          </AppButton>
        </span>
      </div>
    </template>

    <template v-else-if="item.status === 'resolved'">
      <p class="plan__done" data-testid="plan-resolved">
        <span class="plan__mark">{{ item.approved === true ? '✓' : '⊘' }}</span>
        <span class="plan__done-text">{{ item.approved === true ? '计划已确认,分批执行中' : '计划已取消' }}</span>
        <span class="plan__time">{{ fmtClock(item.at) }}</span>
      </p>
    </template>

    <template v-else>
      <p class="plan__failed" data-testid="interrupt-failed">
        <span class="plan__mark">!</span>
        <span>该计划确认已失效{{ item.error ? `:${item.error}` : '' }}</span>
      </p>
    </template>
  </div>
</template>

<style scoped>
.plan {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: 18px 20px;
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-md);
}

/* 卡片标头走黄铜小标签:与正文形成"公文纸"层级 */
.plan__title {
  color: var(--brass);
  font-size: 11px;
  font-weight: var(--fw-medium);
  letter-spacing: 0.12em;
}

.plan__lead {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.plan__body {
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border-subtle);
  font-size: 13.5px;
  line-height: var(--lh-body);
  overflow-wrap: anywhere;
}

.plan__body :deep(p) {
  margin: 0 0 var(--sp-2);
}

.plan__body :deep(ul),
.plan__body :deep(ol) {
  margin: 0;
  padding-left: var(--sp-5);
}

.plan__body :deep(li) {
  margin: 6px 0;
}

.plan__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
}

.plan__hint,
.plan__time {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}

.plan__actions {
  display: flex;
  gap: var(--sp-2);
}

.plan__done,
.plan__failed {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
}

.plan__done {
  color: var(--text-secondary);
}

/* 失败态用 danger:黄铜是本卡的标识色,不能兼作错误语义 */
.plan__failed {
  color: var(--danger);
}

.plan__done-text {
  flex: 1;
  min-width: 0;
}
</style>
