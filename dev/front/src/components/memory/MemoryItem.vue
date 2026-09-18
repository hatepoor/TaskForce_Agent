<script setup lang="ts">
// 单条长期记忆:正文全文 + source 徽标 + 相对时间 + 删除(UI-DESIGN §4.3)。
// 记忆已压缩过,正文不折叠;时间缺失时不渲染时间,不给"未知时间"占位。
import { computed } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import type { MemoryItem as MemoryRecord } from '@/types/memory'

import { fmtMemoryAbsolute, fmtMemoryTime, sourceMeta } from './memoryFormat'

const props = defineProps<{
  item: MemoryRecord
  /** 侧栏点击定位时的短暂高亮 */
  highlight?: boolean
}>()

const emit = defineEmits<{ delete: [item: MemoryRecord] }>()

const source = computed(() => sourceMeta(props.item.source))
const timeText = computed(() => fmtMemoryTime(props.item.created_at))
const timeTitle = computed(() => fmtMemoryAbsolute(props.item.created_at))
</script>

<template>
  <li class="mem" :class="{ 'mem--hl': highlight }" data-testid="memory-row" :data-memory-key="item.key">
    <p class="mem__content">{{ item.content || '(该条记忆没有正文)' }}</p>

    <div class="mem__foot">
      <span
        class="mem__badge"
        :class="`mem__badge--${source.kind}`"
        data-testid="memory-source"
        :title="source.hint"
      >
        {{ source.label }}
      </span>
      <span v-if="timeText" class="mem__time" data-testid="memory-time" :title="timeTitle">
        {{ timeText }}
      </span>

      <span class="mem__grow" />

      <AppButton variant="danger" data-testid="memory-delete" @click="emit('delete', item)">
        删除
      </AppButton>
    </div>
  </li>
</template>

<style scoped>
.mem {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  list-style: none;
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
}

/* 侧栏点击定位:短暂高亮,与知识库页"刚上传行"同一套反馈语言 */
.mem--hl {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.mem__content {
  font-size: var(--fs-lg);
  line-height: var(--lh-body);
  color: var(--text-primary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.mem__foot {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

/* 徽标:两值形状一致、颜色可区分,释义放 title */
.mem__badge {
  flex: none;
  padding: 0 var(--sp-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-full);
  font-size: var(--fs-xs);
  line-height: 16px;
  color: var(--text-muted);
  cursor: default;
}

.mem__badge--explicit {
  border-color: var(--accent);
  color: var(--accent);
}

.mem__badge--confirmed {
  border-color: var(--success);
  color: var(--success);
}

.mem__time {
  flex: none;
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.mem__grow {
  flex: 1;
  min-width: 0;
}
</style>