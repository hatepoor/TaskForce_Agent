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

const emit = defineEmits<{ select: [threadId: string]; remove: [threadId: string] }>()

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
    <button
      type="button"
      class="session__del"
      title="删除会话"
      aria-label="删除会话"
      :data-testid="`session-delete-${threadId}`"
      @click.stop="emit('remove', threadId)"
    >
      ×
    </button>
  </li>
</template>

<style scoped>
.session {
  position: relative;
  list-style: none;
}

/* 主按钮右侧预留删除钮空间,避免短 id 与 × 重叠 */
.session__btn {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  width: 100%;
  padding: 8px 22px 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  text-align: left;
  cursor: pointer;
  transition:
    background var(--t-fast),
    border-color var(--t-fast);
}

.session__btn:hover {
  background: var(--bg-hover);
}

/* 当前会话:纸面卡片 + 发丝描边,比整行染色更克制 */
.session__btn--active {
  background: var(--bg-raised);
  border-color: var(--border-strong);
}

/* 圆点只在当前会话显形:其余行留白对齐,避免一列灰点变成噪点 */
.session__dot {
  flex: none;
  width: 5px;
  height: 5px;
  margin: 7px 0 0 2px;
  border-radius: var(--r-full);
  background: transparent;
}

.session__btn--active .session__dot {
  background: var(--accent);
}

.session__body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.session__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  line-height: 18px;
  color: var(--text-secondary);
}

.session__btn:hover .session__title {
  color: var(--text-primary);
}

.session__btn--active .session__title {
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.session__meta {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  min-width: 0;
  font-size: 10px;
  color: var(--text-muted);
}

.session__time {
  flex: none;
  font-size: 10px;
  color: var(--text-muted);
}

.session__id {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity var(--t-fast);
}

.session__btn:hover .session__id,
.session__btn:focus-visible .session__id,
.session__btn--active .session__id {
  opacity: 1;
}

/* 删除钮:悬停/聚焦该行才显形;@click.stop 防止触发切换 */
.session__del {
  position: absolute;
  top: 50%;
  right: var(--sp-1);
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-muted);
  font-size: var(--fs-md);
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition:
    opacity var(--t-fast),
    background var(--t-fast),
    color var(--t-fast);
}

.session:hover .session__del,
.session__del:focus-visible {
  opacity: 1;
}

.session__del:hover {
  background: var(--bg-hover);
  color: var(--danger);
}
</style>