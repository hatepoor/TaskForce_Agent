<script setup lang="ts">
// 连通性测试结果(UI-DESIGN §4.2):就地展开的工具名列表,或"未连通"。
// `ok:false` 是**正常业务返回**(后端探测降级不抛),只给 danger 文字,不是红色系统报错、不弹 toast;
// 请求层失败(超时 / 404 / 500)才走 error 分支。
import { computed } from 'vue'

import type { MCPTestResult } from '@/types/mcp'

import { testOutcome } from './mcpModel'

const props = defineProps<{
  /** 业务结果;null = 还没测过 */
  result: MCPTestResult | null
  /** 请求层失败文案(`''` = 无) */
  error: string
}>()

const outcome = computed(() => (props.result === null ? null : testOutcome(props.result)))
</script>

<template>
  <div class="result" data-testid="mcp-test-result">
    <p v-if="error !== ''" class="result__line result__line--fail">测试失败:{{ error }}</p>

    <template v-else-if="outcome !== null">
      <p v-if="!outcome.ok" class="result__line result__line--fail">{{ outcome.detail }}</p>

      <template v-else>
        <p v-if="outcome.detail !== ''" class="result__line">{{ outcome.detail }}</p>
        <p v-else class="result__line result__line--tools">
          工具:{{ outcome.labels.join(' · ')
          }}<template v-if="outcome.more > 0"> … 共 {{ outcome.labels.length + outcome.more }} 个</template>
        </p>
      </template>
    </template>
  </div>
</template>

<style scoped>
.result {
  margin-top: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-input);
  border-radius: var(--r-sm);
}

.result:empty {
  display: none;
}

.result__line {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
  word-break: break-word;
}

.result__line--fail {
  color: var(--danger);
}

.result__line--tools {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}
</style>