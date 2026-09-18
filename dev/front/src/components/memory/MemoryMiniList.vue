<script setup lang="ts">
// 上下文栏的记忆条目列表:与记忆页共用一份数据源,点击把主区对应条目滚入视野并高亮。
import { onActivated, onMounted } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import { sourceMeta } from '@/components/memory/memoryFormat'
import { useMemoriesFeed } from '@/composables/useMemoriesFeed'

const { items, loading, error, load, focusMemory } = useMemoriesFeed()

onMounted(() => {
  void load()
})

onActivated(() => {
  void load()
})
</script>

<template>
  <div class="mini" data-testid="panel-memories">
    <p v-if="error" class="mini__error" data-testid="panel-memories-error">
      <span class="mini__error-text">{{ error }}</span>
      <AppButton @click="load()">重试</AppButton>
    </p>

    <p v-if="loading && items.length === 0" class="mini__loading">
      <Spinner />
      <span>加载记忆…</span>
    </p>

    <p v-else-if="items.length === 0" class="mini__empty">还没有长期记忆,对话里说「记住…」即可写入。</p>

    <ul v-else class="mini__list">
      <li v-for="item in items" :key="item.key">
        <button
          type="button"
          class="mini__item"
          :title="item.content || item.key"
          :data-testid="`panel-memory-${item.key}`"
          @click="focusMemory(item.key)"
        >
          <span class="mini__text">{{ item.content || '(空内容)' }}</span>
          <span class="mini__meta" :class="`mini__meta--${sourceMeta(item.source).kind}`">
            {{ sourceMeta(item.source).label }}
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.mini {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-height: 0;
}

.mini__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.mini__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: var(--sp-2);
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  text-align: left;
  cursor: pointer;
}

.mini__item:hover {
  background: var(--bg-hover);
}

.mini__text {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
  /* 两行截断:侧栏窄,长记忆不出滚动条 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mini__item:hover .mini__text {
  color: var(--text-primary);
}

.mini__meta {
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.mini__meta--explicit {
  color: var(--accent);
}

.mini__empty,
.mini__loading {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2);
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.mini__error {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2);
  border: 1px solid var(--danger);
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
}

.mini__error-text {
  flex: 1;
  min-width: 0;
  color: var(--danger);
  overflow-wrap: anywhere;
}
</style>