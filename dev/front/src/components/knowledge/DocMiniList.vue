<script setup lang="ts">
// 上下文栏的文档列表:与知识库页共用一份数据源,点击把主区对应行滚入视野并高亮。
import { onActivated, onMounted } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useDocsFeed } from '@/composables/useDocsFeed'
import { fmtDateTime, shortDocId } from '@/utils/knowledge'

const { docs, loading, error, load, focusDoc } = useDocsFeed()

onMounted(() => {
  void load()
})

// 视图被 KeepAlive 缓存:切回本页时补一次刷新(别处上传后回来能看到)
onActivated(() => {
  void load()
})
</script>

<template>
  <div class="mini" data-testid="panel-docs">
    <p v-if="error" class="mini__error" data-testid="panel-docs-error">
      <span class="mini__error-text">{{ error }}</span>
      <AppButton @click="load()">重试</AppButton>
    </p>

    <p v-if="loading && docs.length === 0" class="mini__loading">
      <Spinner />
      <span>加载文档列表…</span>
    </p>

    <p v-else-if="docs.length === 0" class="mini__empty">知识库还是空的,在右侧面板上传文档。</p>

    <ul v-else class="mini__list">
      <li v-for="doc in docs" :key="doc.doc_id">
        <button
          type="button"
          class="mini__item"
          :title="doc.filename"
          :data-testid="`panel-doc-${doc.doc_id}`"
          @click="focusDoc(doc.doc_id)"
        >
          <span class="mini__name">{{ doc.filename }}</span>
          <span class="mini__meta">
            <span class="mini__mono">{{ shortDocId(doc.doc_id) }}</span>
            <span>{{ doc.chunks }} 切片</span>
            <span>{{ fmtDateTime(doc.created_at) }}</span>
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

.mini__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: var(--fs-md);
}

.mini__item:hover .mini__name {
  color: var(--text-primary);
}

.mini__meta {
  display: flex;
  gap: var(--sp-2);
  overflow: hidden;
  color: var(--text-muted);
  font-size: var(--fs-xs);
  white-space: nowrap;
}

.mini__mono {
  font-family: var(--font-mono);
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