<script setup lang="ts">
// 单个 MCP 服务器行:name + transport 徽标 + 命令行/URL 摘要 + 测试/删除(UI-DESIGN §4.2)。
// 测试状态(在途 / 结果 / 请求层错误)就地自持,父组件不感知;
// 前端 30s 超时在 api/mcp.ts 里用 AbortSignal.timeout 消化,这里只管按钮禁用与文案。
import { computed, ref } from 'vue'

import { errText } from '@/api/http'
import { testServer } from '@/api/mcp'
import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useUiStore } from '@/stores/ui'
import type { MCPServerConfig, MCPTestResult } from '@/types/mcp'

import McpTestResult from './McpTestResult.vue'
import { TEST_TIMEOUT_TEXT, isTimeoutError, summarizeConfig, testOutcome } from './mcpModel'

const props = defineProps<{ name: string; config: MCPServerConfig }>()
const emit = defineEmits<{ delete: [name: string] }>()

const ui = useUiStore()

const view = computed(() => summarizeConfig(props.config))

const testing = ref(false)
const tested = ref(false)
const result = ref<MCPTestResult | null>(null)
const requestError = ref('')

/** 行内状态:未测试 → 测试中… → 已连通 · N 个工具 / 未连通 */
const status = computed(() => {
  if (testing.value) return '测试中…'
  if (requestError.value !== '') return '测试失败'
  if (result.value !== null) return testOutcome(result.value).badge
  return tested.value ? '未连通' : '未测试'
})

const showResult = computed(() => testing.value || result.value !== null || requestError.value !== '')

async function onTest(): Promise<void> {
  if (testing.value) return
  testing.value = true
  result.value = null
  requestError.value = ''
  try {
    result.value = await testServer(props.name)
  } catch (e) {
    // 请求层失败(超时 / 404 / 500)才是错误:就地展示 + toast;ok:false 不走这里
    const text = isTimeoutError(e) ? TEST_TIMEOUT_TEXT : errText(e)
    requestError.value = text
    ui.toast(text, 'error')
  } finally {
    testing.value = false
    tested.value = true
  }
}
</script>

<template>
  <article class="row" data-testid="mcp-row" :data-server="name">
    <header class="row__head">
      <h3 class="row__name">{{ name }}</h3>
      <span class="row__badge" :data-testid="`mcp-badge-${name}`">{{ view.badge }}</span>
      <span class="row__status">{{ status }}</span>
      <Spinner v-if="testing" />
    </header>

    <p class="row__summary" :title="view.summary">{{ view.summary }}</p>

    <div class="row__actions">
      <AppButton
        data-testid="mcp-test"
        :data-server="name"
        :disabled="testing"
        @click="onTest"
      >
        {{ result !== null || tested ? '重新测试' : '测试' }}
      </AppButton>
      <AppButton data-testid="mcp-delete" :data-server="name" variant="danger" @click="emit('delete', name)">
        删除
      </AppButton>
    </div>

    <McpTestResult v-if="showResult" :result="result" :error="requestError" />
  </article>
</template>

<style scoped>
.row {
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
}

.row__head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.row__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  font-weight: 600;
}

/* 徽标:transport 原文,不加颜色(全站只有一个强调色) */
.row__badge {
  flex: none;
  padding: 1px var(--sp-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  line-height: var(--lh-base);
}

.row__status {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.row__summary {
  margin-top: var(--sp-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}

.row__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
</style>