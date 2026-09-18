<script setup lang="ts">
// 文档列表表格:加载 / 空态 / 错误重试三态 + 表头(UI-DESIGN §3.4 / §4.1)。
// 数据由 KnowledgeView 持有(上传成功后要刷新、删除后要移除行),这里只渲染。
import AppButton from '@/components/common/AppButton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Spinner from '@/components/common/Spinner.vue'
import type { KDoc } from '@/types/knowledge'

import DocRow from './DocRow.vue'

defineProps<{
  docs: KDoc[]
  loading: boolean
  /** 非空则显示错误条(列表可能仍是旧的,不挡着看) */
  error: string
  /** 刚上传成功的 doc_id(2s 高亮) */
  highlightId: string
  /** 处于「已复制」内联反馈期的 doc_id */
  copiedId: string
}>()

const emit = defineEmits<{
  copyId: [docId: string]
  remove: [doc: KDoc]
  retry: []
}>()
</script>

<template>
  <div class="docs" data-testid="doc-table">
    <p v-if="error" class="docs__error" data-testid="docs-error">
      <span class="docs__error-text">{{ error }}</span>
      <AppButton data-testid="docs-retry" @click="emit('retry')">重试</AppButton>
    </p>

    <p v-if="loading && docs.length === 0" class="docs__loading" data-testid="docs-loading">
      <Spinner />
      <span>加载文档列表…</span>
    </p>

    <EmptyState
      v-else-if="docs.length === 0 && !error"
      title="知识库里还没有文档"
      hint="把文件拖到上方上传区,或点「选择文件」。支持 pdf / docx / md / txt,单文件不超过 20MB。"
    />

    <table v-else-if="docs.length > 0" class="docs__table">
      <colgroup>
        <col />
        <col class="docs__col-id" />
        <col class="docs__col-time" />
        <col class="docs__col-num" />
        <col class="docs__col-ops" />
      </colgroup>
      <thead>
        <tr>
          <th scope="col">文件名</th>
          <th scope="col">文档 ID</th>
          <th scope="col">入库时间</th>
          <th scope="col" class="docs__num">切片</th>
          <th scope="col" class="docs__ops-head">操作</th>
        </tr>
      </thead>
      <tbody>
        <DocRow
          v-for="doc in docs"
          :key="doc.doc_id"
          :doc="doc"
          :highlight="doc.doc_id === highlightId"
          :copied="doc.doc_id === copiedId"
          @copy-id="emit('copyId', $event)"
          @remove="emit('remove', $event)"
        />
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.docs {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.docs__error {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--danger);
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
}

.docs__error-text {
  flex: 1;
  min-width: 0;
  color: var(--danger);
  overflow-wrap: anywhere;
}

.docs__loading {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3);
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.docs__table {
  width: 100%;
  border-collapse: collapse;
  /* 固定列宽:文件名省略号与数字右对齐才稳(UI-DESIGN §5.1) */
  table-layout: fixed;
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
}

.docs__table th {
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-strong);
  color: var(--text-muted);
  font-size: var(--fs-xs);
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
}

.docs__num,
.docs__ops-head {
  text-align: right;
}

.docs__col-id {
  width: 120px;
}

.docs__col-time {
  width: 104px;
}

.docs__col-num {
  width: 64px;
}

.docs__col-ops {
  width: 152px;
}
</style>