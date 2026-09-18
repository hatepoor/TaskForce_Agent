<script setup lang="ts">
// 单张指标卡:标签 + 状态灯 + 原文本 + 一行说明(UI-DESIGN §4.4)。
// 值可能是 db 的整段异常文本,故用可换行 + 超高滚动的块,不做截断。
import StatusDot from '@/components/common/StatusDot.vue'

import type { DotState, HealthKey } from './healthModel'

defineProps<{
  /** 字段名:用于生成稳定的 data-testid(health-card-status / -db / -sandbox) */
  name: HealthKey
  label: string
  state: DotState
  value: string
  detail: string
}>()
</script>

<template>
  <article class="card" :data-testid="`health-card-${name}`">
    <p class="card__label">{{ label }}</p>

    <p class="card__value">
      <StatusDot :state="state" />
      <span class="card__text">{{ value }}</span>
    </p>

    <p class="card__detail">{{ detail }}</p>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-width: 0;
  padding: var(--sp-4);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
}

.card__label {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.card__value {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  min-width: 0;
}

.card__text {
  min-width: 0;
  max-height: 72px;
  overflow-y: auto;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  line-height: var(--lh-tight);
  /* 异常文本里常有换行/超长 URL:原样换行展示,不截断 */
  white-space: pre-wrap;
  word-break: break-word;
}

.card__detail {
  color: var(--text-muted);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}
</style>