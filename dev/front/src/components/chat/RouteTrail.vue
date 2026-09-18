<script setup lang="ts">
// 路由轨迹条:本轮所有 route 事件聚合成一条,默认一行摘要,可展开(UI-DESIGN §3.2)。
// 展开态即"派发清单"(agent / 任务 / 理由);异步派发架构下拿不到"已完成",不显示虚假进行中动效。
import { computed, ref } from 'vue'

import type { RoutePayload, TaskPayload } from '@/types/chat'

const props = defineProps<{ routes: RoutePayload[]; streaming: boolean }>()

const open = ref(false)

const AGENT_LABEL: Record<TaskPayload['agent'], string> = {
  retriever: 'retriever',
  research: 'research',
  executor: 'executor',
}

function stepLabel(route: RoutePayload): string {
  switch (route.next) {
    case 'dispatch':
      return `派发 ${route.tasks?.length ?? 0} 项`
    case 'answer':
      return '汇总作答'
    case 'ask':
      return '需要补充信息'
    case 'memory':
      return '记忆写入'
    default:
      return route.next
  }
}

const steps = computed(() =>
  props.routes.map((r) => ({ route: r, label: stepLabel(r), tasks: r.tasks ?? [] })),
)

const totalTasks = computed(() => steps.value.reduce((n, s) => n + s.tasks.length, 0))

const agents = computed(() => {
  const out: TaskPayload['agent'][] = []
  for (const s of steps.value) {
    for (const t of s.tasks) if (!out.includes(t.agent)) out.push(t.agent)
  }
  return out
})

const summary = computed(() => {
  const labels = steps.value.map((s) => s.label)
  if (labels.length === 0) return ''
  return agents.value.length > 0 ? `${labels[0]} · ${agents.value.join(' + ')}` : labels.join(' → ')
})
</script>

<template>
  <div class="trail" data-testid="route-trail">
    <button type="button" class="trail__head" :aria-expanded="open" @click="open = !open">
      <span class="trail__dot" :class="{ 'trail__dot--live': streaming }" />
      <span class="trail__summary">{{ summary }}</span>
      <span v-if="totalTasks > 0" class="trail__count">{{ totalTasks }} 项</span>
      <span class="trail__caret">{{ open ? '▾' : '▸' }}</span>
    </button>

    <ol v-if="open" class="trail__steps">
      <li v-for="(s, i) in steps" :key="i" class="trail__step">
        <p class="trail__step-head">{{ i + 1 }}. {{ s.label }}</p>
        <ul v-if="s.tasks.length > 0" class="trail__tasks">
          <li v-for="(t, j) in s.tasks" :key="j" class="trail__task">
            <span class="trail__agent" :class="`trail__agent--${t.agent}`">{{ AGENT_LABEL[t.agent] }}</span>
            <span class="trail__task-text">{{ t.task }}</span>
            <span class="trail__reason">理由:{{ t.reason }}</span>
          </li>
        </ul>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.trail {
  /* 与 AI 正文对齐(头像 28 + 间距 12):轨迹属于这一轮的 AI 侧,不贴边游离 */
  align-self: flex-start;
  max-width: calc(100% - 40px);
  margin-left: 40px;
  font-size: var(--fs-sm);
}

.trail__head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  max-width: 100%;
  padding: var(--sp-1) var(--sp-3);
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-full);
  color: var(--text-muted);
  text-align: left;
  cursor: pointer;
}

.trail__head:hover {
  border-color: var(--border-strong);
  color: var(--text-secondary);
}

.trail__dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: var(--r-full);
  background: var(--text-muted);
}

/* 全界面唯一的动画:流进行中圆点轻微呼吸 */
.trail__dot--live {
  background: var(--accent);
  animation: breathe 2s ease-in-out infinite;
}

@keyframes breathe {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.trail__summary {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trail__count {
  flex: none;
  color: var(--text-muted);
}

.trail__caret {
  flex: none;
}

.trail__steps {
  margin: var(--sp-1) 0 var(--sp-2);
  padding: 0 0 0 var(--sp-3);
  border-left: 1px solid var(--border-subtle);
  list-style: none;
}

.trail__step + .trail__step {
  margin-top: var(--sp-2);
}

.trail__step-head {
  color: var(--text-secondary);
}

.trail__tasks {
  margin: var(--sp-1) 0 0;
  padding: 0;
  list-style: none;
}

.trail__task {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--sp-2);
  padding: 2px 0;
}

.trail__agent {
  flex: none;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}

.trail__agent--retriever {
  color: var(--agent-retriever);
}

.trail__agent--research {
  color: var(--agent-research);
}

.trail__agent--executor {
  color: var(--agent-executor);
}

.trail__task-text {
  color: var(--text-secondary);
}

.trail__reason {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}
</style>