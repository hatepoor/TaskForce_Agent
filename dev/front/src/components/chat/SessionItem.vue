<script setup lang="ts">
// 单条会话:标题为主,时间与短 id 为辅(id 只在悬停/当前项显形,平时不占视觉)。
// 本地标题由首条用户输入生成(store),回填时补齐。
import { computed } from 'vue'

const props = defineProps<{
  threadId: string
  title: string
  active: boolean
  /** 相对时间文案;空串表示未知,不显示 */
  timeText: string
}>()

const emit = defineEmits<{ select: [threadId: string] }>()

const shortId = computed(() => props.threadId.replace(/^sess-/, '').slice(0, 8))
</script>

<template>
  <li class="session">
    <button
      type="button"
      class="session__btn"
      :class="{ 'session__btn--active': active }"
      :aria-current="active ? 'page' : undefined"
      :title="threadId"
      :data-testid="`session-${threadId}`"
      @click="emit('select', threadId)"
    >
      <span class="session__dot" />
      <span class="session__body">
        <span class="session__title">{{ title || '新会话' }}</span>
        <span class="session__meta">
          <span v-if="timeText" class="session__time">{{ timeText }}</span>
          <span class="session__id">{{ shortId }}</span>
        </span>
      </span>
    </button>
  </li>
</template>

<style scoped>
.session {
  list-style: none;
}

.session__btn {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  width: 100%;
  padding: var(--sp-2) var(--sp-2) var(--sp-2) var(--sp-1);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  text-align: left;
  cursor: pointer;
}

.session__btn:hover {
  background: var(--bg-hover);
}

.session__btn--active {
  background: var(--accent-soft);
  border-color: var(--border-strong);
}

/* 圆点只在当前会话显形:其余行留白对齐,避免一列灰点变成噪点 */
.session__dot {
  flex: none;
  width: 6px;
  height: 6px;
  margin: 6px 0 0 var(--sp-1);
  border-radius: var(--r-full);
  background: transparent;
}

.session__btn--active .session__dot {
  background: var(--accent);
}

.session__body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.session__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-md);
  color: var(--text-secondary);
}

.session__btn:hover .session__title {
  color: var(--text-primary);
}

.session__btn--active .session__title {
  color: var(--text-primary);
  font-weight: 500;
}

.session__meta {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  min-width: 0;
}

.session__time {
  flex: none;
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.session__id {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  opacity: 0;
  transition: opacity var(--t-fast);
}

.session__btn:hover .session__id,
.session__btn:focus-visible .session__id,
.session__btn--active .session__id {
  opacity: 1;
}
</style>