<script setup lang="ts">
// 本轮用量角标:一行 12px 灰字,不做卡片/进度条/颜色(UI-DESIGN §3.2)。
// usage 事件是进程累计值,这里显示的是与轮首快照的差分(坑 8),累计值放 tooltip。
import { computed } from 'vue'

import type { TurnUsage, UsageEvent } from '@/types/chat'

const props = defineProps<{ usage: TurnUsage; cumulative?: UsageEvent }>()

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

const text = computed(
  () =>
    `本轮 ${props.usage.calls} 次调用 · 入 ${fmtK(props.usage.inputTokens)} / 出 ${fmtK(props.usage.outputTokens)} tok`,
)

const cumulativeText = computed(() => {
  const c = props.cumulative
  if (c === undefined) return ''
  return `进程累计(calls ${c.calls})入 ${fmtK(c.input_tokens)} / 出 ${fmtK(c.output_tokens)} tok`
})
</script>

<template>
  <p class="usage" :title="cumulativeText" data-testid="usage-badge">{{ text }}</p>
</template>

<style scoped>
.usage {
  margin-top: var(--sp-2);
  color: var(--text-muted);
  font-size: var(--fs-sm);
}
</style>