<script setup lang="ts">
// 左索引栏(v2):品牌 + 主导航 + 当前路由的上下文列表 + 底部后端状态。
// v1 的「图标轨 + 上下文栏」两段合并为一段,上下文内容紧随导航,减少一列割裂。
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import ThreadList from '@/components/chat/ThreadList.vue'
import StatusDot from '@/components/common/StatusDot.vue'
import DocMiniList from '@/components/knowledge/DocMiniList.vue'
import MemoryMiniList from '@/components/memory/MemoryMiniList.vue'
import SettingsNav from '@/components/settings/SettingsNav.vue'
import { healthTooltip, isOkValue, overallState } from '@/components/settings/healthModel'
import { useHealthPoll } from '@/composables/useHealthPoll'

const emit = defineEmits<{ navigate: [] }>()

const route = useRoute()
const { data } = useHealthPoll()

const health = computed(() => ({
  state: overallState(data.value),
  tip: healthTooltip(data.value),
}))

/** 三项自检(status/db/sandbox)中正常项计数;未取到数据时不显示,绝不写死 */
const healthCount = computed(() => {
  const h = data.value
  if (h === null) return ''
  const ok = [h.status, h.db, h.sandbox].filter(isOkValue).length
  return `${ok}/3`
})

type PanelKind = 'chat' | 'knowledge' | 'memory' | 'settings'

const kind = computed<PanelKind>(() => {
  const path = route.path
  if (path.startsWith('/knowledge')) return 'knowledge'
  if (path.startsWith('/memory')) return 'memory'
  if (path.startsWith('/settings')) return 'settings'
  return 'chat'
})

const CTX_TITLE: Record<PanelKind, string> = {
  chat: '最近会话',
  knowledge: '文档列表',
  memory: '记忆条目',
  settings: '设置分节',
}

const ctxTitle = computed(() => CTX_TITLE[kind.value])
const healthLabel = computed(() => {
  switch (health.value.state) {
    case 'ok':
      return '后端在线'
    case 'warn':
      return '部分异常'
    case 'err':
      return '后端异常'
    default:
      return '状态未知'
  }
})

function go(): void {
  emit('navigate')
}

/** 当前路由是否属于该入口(带参路由如 /chat/:threadId 也命中) */
function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>

<template>
  <nav class="rail" aria-label="主导航">
    <div class="rail__brand">
      <span class="rail__bar" aria-hidden="true" />
      <span class="rail__names">
        <span class="rail__name">TaskForce</span>
        <span class="rail__sub">投资调研工作台</span>
      </span>
    </div>

    <div class="rail__nav">
      <RouterLink
        to="/chat"
        class="rail__link"
        :class="{ 'rail__link--active': isActive('/chat') }"
        aria-label="对话"
        @click="go"
      >
        <svg class="rail__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M21 14.6a2 2 0 0 1-2 2H8.2L4 20V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path d="M8.5 9h7M8.5 12.5h4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        </svg>
        <span>对话</span>
      </RouterLink>

      <RouterLink
        to="/knowledge"
        class="rail__link"
        :class="{ 'rail__link--active': isActive('/knowledge') }"
        aria-label="知识库"
        @click="go"
      >
        <svg class="rail__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M13.5 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8.5z"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linejoin="round"
          />
          <path
            d="M13.5 3v5.5H19M8.5 13h7M8.5 16.5h4.5"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linecap="round"
          />
        </svg>
        <span>知识库</span>
      </RouterLink>

      <RouterLink
        to="/memory"
        class="rail__link"
        :class="{ 'rail__link--active': isActive('/memory') }"
        aria-label="长期记忆"
        @click="go"
      >
        <svg class="rail__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M19 21l-7-5-7 5V5.5A1.5 1.5 0 0 1 6.5 4h11A1.5 1.5 0 0 1 19 5.5z"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linejoin="round"
          />
          <path d="M9.5 9h5M9.5 12h3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        </svg>
        <span>长期记忆</span>
      </RouterLink>

      <RouterLink
        to="/settings"
        class="rail__link"
        :class="{ 'rail__link--active': isActive('/settings') }"
        aria-label="设置"
        @click="go"
      >
        <svg class="rail__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 7h7M4 17h5M17 7h3M15 17h5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          <circle cx="13.5" cy="7" r="2.6" stroke="currentColor" stroke-width="1.7" />
          <circle cx="11" cy="17" r="2.6" stroke="currentColor" stroke-width="1.7" />
        </svg>
        <span>设置</span>
      </RouterLink>
    </div>

    <div class="rail__ctx">
      <p class="rail__ctx-head">{{ ctxTitle }}</p>
      <div class="rail__ctx-scroll">
        <ThreadList v-if="kind === 'chat'" />
        <DocMiniList v-else-if="kind === 'knowledge'" />
        <MemoryMiniList v-else-if="kind === 'memory'" />
        <SettingsNav v-else />
      </div>
    </div>

    <div
      class="rail__foot"
      :title="health.tip"
      tabindex="0"
      :aria-label="`后端状态:${health.tip}`"
      data-testid="rail-health"
    >
      <p class="rail__health">
        <StatusDot :state="health.state" />
        <span>{{ healthLabel }}</span>
        <span v-if="healthCount !== ''" class="rail__state">{{ healthCount }}</span>
      </p>
    </div>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  height: 100%;
  min-height: 0;
  padding: var(--sp-5) var(--sp-4) var(--sp-4);
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  overflow: hidden;
}

/* ── 品牌 ───────────────────────────────────────────── */
.rail__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
  height: 46px;
}

.rail__bar {
  flex: none;
  width: 3px;
  height: 24px;
  border-radius: 1px;
  background: var(--accent);
}

.rail__names {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.rail__name {
  font-family: var(--font-serif);
  font-size: 21px;
  font-weight: var(--fw-strong);
  line-height: 28px;
  letter-spacing: 0.01em;
  color: var(--text-primary);
}

.rail__sub {
  font-size: 10px;
  line-height: 14px;
  letter-spacing: 0.14em;
  color: var(--text-muted);
}

/* ── 导航 ───────────────────────────────────────────── */
.rail__nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: none;
}

.rail__link {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 38px;
  padding: 0 10px;
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: 13.5px;
  user-select: none;
  transition:
    background var(--t-fast),
    color var(--t-fast);
}

.rail__link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.rail__link--active {
  background: var(--bg-active);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.rail__icon {
  flex: none;
  width: 16px;
  height: 16px;
}

/* ── 上下文列表 ─────────────────────────────────────── */
.rail__ctx {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-height: 0;
}

.rail__ctx-head {
  flex: none;
  font-size: 10px;
  font-weight: var(--fw-medium);
  letter-spacing: 0.14em;
  color: var(--text-muted);
}

.rail__ctx-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-right: -6px;
  padding-right: 6px;
}

/* ── 底部状态 ───────────────────────────────────────── */
.rail__foot {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}

.rail__health {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  font-weight: var(--fw-medium);
  color: var(--text-secondary);
}

.rail__state {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: var(--fw-normal);
  color: var(--text-muted);
}
</style>
