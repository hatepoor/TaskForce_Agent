<script setup lang="ts">
// MCP 节:服务器列表 + 新增抽屉 + 测试/删除(UI-DESIGN §4.2)。
// 本组件是 MCP 资源的唯一状态持有者:列表进页拉、离页弃,不建 store;测试状态在行内自持。
// 两个二次确认:删除(DeleteMcpDialog)、同名保存覆盖(ConfirmDialog)——后端同名是静默覆盖。
import { computed, onMounted, ref } from 'vue'

import { errText } from '@/api/http'
import { createServer, listServers, removeServer } from '@/api/mcp'
import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useUiStore } from '@/stores/ui'
import type { MCPServerConfig } from '@/types/mcp'

import ConfirmDialog from './ConfirmDialog.vue'
import DeleteMcpDialog from './DeleteMcpDialog.vue'
import McpServerForm from './McpServerForm.vue'
import McpServerList from './McpServerList.vue'
import { isDuplicateName, overwriteMessage, serverEntries } from './mcpModel'

const ui = useUiStore()

const servers = ref<Record<string, MCPServerConfig>>({})
const loading = ref(false)
const error = ref('')

const entries = computed(() => serverEntries(servers.value))
const names = computed(() => entries.value.map((e) => e.name))

// ── 新增抽屉 ────────────────────────────────────────────────
const formOpen = ref(false)
const submitting = ref(false)
const formError = ref('')
/** 待覆盖确认的提交(非空 = 覆盖确认弹窗打开中) */
const pending = ref<{ name: string; config: MCPServerConfig } | null>(null)

// ── 删除确认 ────────────────────────────────────────────────
const deleteTarget = ref('')
const deleting = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await listServers()
    servers.value = res.servers ?? {}
    error.value = ''
  } catch (e) {
    error.value = errText(e)
    ui.toast(error.value, 'error')
  } finally {
    loading.value = false
  }
}

function onAdd(): void {
  formError.value = ''
  formOpen.value = true
}

/** 表单提交:同名先二次确认(后端静默覆盖,不确认就是丢配置) */
function onSubmit(payload: { name: string; config: MCPServerConfig }): void {
  if (isDuplicateName(payload.name, names.value)) {
    pending.value = payload
    return
  }
  void create(payload)
}

async function create(payload: { name: string; config: MCPServerConfig }): Promise<void> {
  submitting.value = true
  try {
    await createServer(payload.name, payload.config)
    ui.toast(`已保存 ${payload.name}`)
    formOpen.value = false
    formError.value = ''
    await load()
  } catch (e) {
    // 422:后端 detail 显示在表单顶部错误条,抽屉不关、已填数据不丢
    formError.value = errText(e)
    ui.toast(formError.value, 'error')
  } finally {
    submitting.value = false
    pending.value = null
  }
}

async function onDeleteConfirm(): Promise<void> {
  const name = deleteTarget.value
  if (name === '') return
  deleting.value = true
  try {
    await removeServer(name)
    ui.toast(`已删除 ${name}`)
  } catch (e) {
    // 404(已被别处删掉)与 500 都按"可能已不存在"处理:提示 + 刷新列表
    ui.toast(errText(e), 'error')
  } finally {
    deleting.value = false
    deleteTarget.value = ''
    await load()
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="section" data-testid="mcp-section">
    <header class="section__head">
      <h2 class="section__title">MCP 服务器</h2>
      <span class="section__meta">{{ entries.length }} 个</span>
      <Spinner v-if="loading" />
      <AppButton data-testid="mcp-refresh" :disabled="loading" @click="load">刷新</AppButton>
      <AppButton variant="primary" data-testid="mcp-add" @click="onAdd">+ 添加</AppButton>
    </header>

    <p v-if="error !== ''" class="section__error" data-testid="mcp-error">{{ error }}</p>

    <p v-if="loading && entries.length === 0" class="section__loading">正在读取 MCP 配置…</p>
    <!-- 拉取失败时只给错误条:此时空列表不代表"没有服务器" -->
    <McpServerList v-else-if="error === '' || entries.length > 0" :entries="entries" @delete="deleteTarget = $event" />

    <p class="section__hint">
      配置存于 mcp_config.json;新增 / 删除从下一轮会话装配开始生效。测试为逐服务器隔离探测(后端 10s、前端 30s 超时)。
    </p>

    <McpServerForm
      :open="formOpen"
      :submitting="submitting || pending !== null"
      :error="formError"
      :existing-names="names"
      @close="formOpen = false"
      @submit="onSubmit"
    />

    <ConfirmDialog
      :open="pending !== null"
      data-testid="mcp-overwrite-confirm"
      title="覆盖同名服务器"
      :message="pending === null ? '' : overwriteMessage(pending.name)"
      confirm-text="覆盖保存"
      :busy="submitting"
      @confirm="pending !== null && create(pending)"
      @cancel="pending = null"
    />

    <DeleteMcpDialog
      :open="deleteTarget !== ''"
      :name="deleteTarget"
      :busy="deleting"
      @confirm="onDeleteConfirm"
      @cancel="deleteTarget = ''"
    />
  </section>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.section__head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.section__title {
  font-size: var(--fs-lg);
  font-weight: 600;
}

.section__meta {
  flex: 1;
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.section__error {
  padding: var(--sp-2) var(--sp-3);
  background: var(--danger-soft);
  border-left: 2px solid var(--danger);
  border-radius: var(--r-sm);
  color: var(--danger);
  font-size: var(--fs-sm);
}

.section__loading {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.section__hint {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  line-height: var(--lh-base);
}
</style>