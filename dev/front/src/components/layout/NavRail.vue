<script setup lang="ts">
// 导航轨:品牌标记 + 4 个「图标 + 文字」入口 + 底部后端健康状态点。
// 状态点接真实轮询(与设置页共用同一份数据,见 composables/useHealthPoll.ts):
// 悬停显示 status/db/sandbox 明细,不再有"假数据"占位。
import { computed } from 'vue'

import StatusDot from '@/components/common/StatusDot.vue'
import { healthTooltip, overallState } from '@/components/settings/healthModel'
import { useHealthPoll } from '@/composables/useHealthPoll'

const { data } = useHealthPoll()
const health = computed(() => ({
  state: overallState(data.value),
  tip: healthTooltip(data.value),
}))
</script>

<template>
  <nav class="rail" aria-label="主导航">
    <div class="rail__brand" aria-hidden="true">
      <svg
        class="rail__brand-glyph"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
      >
        <circle cx="6.5" cy="12" r="2.2" />
        <circle cx="17.5" cy="6.5" r="2.2" />
        <circle cx="17.5" cy="17.5" r="2.2" />
        <path d="M8.4 10.9 L15.6 7.4" />
        <path d="M8.4 13.1 L15.6 16.6" />
      </svg>
    </div>

    <RouterLink to="/chat" class="rail__item" aria-label="对话">
      <svg
        class="rail__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
      <span class="rail__label">对话</span>
    </RouterLink>

    <RouterLink to="/knowledge" class="rail__item" aria-label="知识库">
      <svg
        class="rail__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M9 13h6M9 17h6" />
      </svg>
      <span class="rail__label">知识库</span>
    </RouterLink>

    <RouterLink to="/memory" class="rail__item" aria-label="长期记忆">
      <svg
        class="rail__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
      <span class="rail__label">记忆</span>
    </RouterLink>

    <RouterLink to="/settings" class="rail__item" aria-label="设置">
      <svg
        class="rail__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M20 7h-9" />
        <path d="M14 17H5" />
        <circle cx="17" cy="17" r="3" />
        <circle cx="7" cy="7" r="3" />
      </svg>
      <span class="rail__label">设置</span>
    </RouterLink>

    <div class="rail__spacer" />

    <div class="rail__health" tabindex="0" :aria-label="`后端状态:${health.tip}`" data-testid="rail-health">
      <StatusDot :state="health.state" />
      <span class="rail__label">后端</span>
      <span class="rail__tip">{{ health.tip }}</span>
    </div>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-1);
  padding: var(--sp-3) 0;
  height: 100%;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
}

/* 品牌标记:与 AI 头像同一套三点连线语义,给导航轨一个视觉起点 */
.rail__brand {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-bottom: var(--sp-3);
  border-radius: var(--r-md);
  background: var(--accent-soft);
  color: var(--accent);
}

.rail__brand-glyph {
  width: 18px;
  height: 18px;
}

.rail__item,
.rail__health {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  width: 48px;
  padding: var(--sp-2) 0;
  border-radius: var(--r-md);
  color: var(--text-secondary);
  /* 导航图标禁用文本选区(UI-DESIGN §6.3) */
  user-select: none;
}

.rail__item:hover,
.rail__health:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* 当前项:图标着 accent + 淡底(左侧 2px 竖条保留为"定位到导航轨左缘"的标记) */
.rail__item.router-link-active {
  background: var(--accent-soft);
  color: var(--accent);
}

.rail__item.router-link-active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  border-radius: var(--r-full);
  background: var(--accent);
}

.rail__icon {
  width: 20px;
  height: 20px;
}

.rail__label {
  font-size: 10px;
  line-height: 1;
  letter-spacing: 0.02em;
}

.rail__item.router-link-active .rail__label {
  color: var(--accent);
}

.rail__spacer {
  flex: 1;
}

/* 悬停/聚焦明细 tooltip(状态点本身只有颜色,明细在文案里) */
.rail__tip {
  position: absolute;
  left: calc(100% + var(--sp-2));
  bottom: 0;
  z-index: 30;
  max-width: 320px;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-sm);
  box-shadow: var(--shadow-pop-sm);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
  text-align: left;
  white-space: pre-line;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--t-fast);
}

.rail__health:hover .rail__tip,
.rail__health:focus-visible .rail__tip {
  opacity: 1;
}
</style>