<script setup lang="ts">
// 模型节:设置页配置主模型 / Embedding 的 base_url、api_key、模型名(OpenAI 兼容协议)。
// 覆盖值落盘 .taskforce/model_config.json(后端),.env 仍是默认值来源;
// **保存后重启后端生效**——顶部横幅按后端的 restart_required 显式提示。
import { computed, onMounted, reactive, ref } from 'vue'

import { errText } from '@/api/http'
import { fetchModelConfig, saveModelConfig } from '@/api/models'
import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useUiStore } from '@/stores/ui'
import type { ModelConfigValues, ModelField } from '@/types/models'

import ModelCard from './ModelCard.vue'
import {
  MODEL_GROUPS,
  clearGroup,
  diffValues,
  emptyValues,
  sameValues,
  validateValues,
} from './modelsModel'

const ui = useUiStore()

const draft = reactive<ModelConfigValues>(emptyValues())
const loaded = reactive<ModelConfigValues>(emptyValues())
const overridden = ref<ModelField[]>([])
const restartRequired = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const dirty = computed(() => !sameValues(draft, loaded))
const localError = computed(() => validateValues(draft))
const canSave = computed(() => dirty.value && localError.value === '' && !saving.value)

function apply(res: { config: ModelConfigValues; overridden: ModelField[]; restart_required: boolean }): void {
  Object.assign(draft, res.config)
  Object.assign(loaded, res.config)
  overridden.value = res.overridden
  restartRequired.value = res.restart_required
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    apply(await fetchModelConfig())
  } catch (e) {
    error.value = errText(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function onField(field: ModelField, value: string): void {
  draft[field] = value
}

async function save(): Promise<void> {
  const patch = diffValues(draft, loaded)
  if (Object.keys(patch).length === 0) return
  saving.value = true
  error.value = ''
  try {
    const res = await saveModelConfig(patch)
    apply(res)
    ui.toast(res.restart_required ? '已保存,重启后端生效' : '已保存')
  } catch (e) {
    error.value = errText(e)
  } finally {
    saving.value = false
  }
}

function onSave(): void {
  if (!canSave.value) return
  void save()
}

/** 撤销未保存的改动:回到最近一次加载/保存的值。 */
function onRevert(): void {
  Object.assign(draft, loaded)
}

/** 该组三项清空并立即保存 = 清除覆盖,回落 .env 默认(只提交这三项)。 */
function onResetGroup(groupKey: string): void {
  Object.assign(draft, clearGroup(draft, groupKey))
  void save()
}
</script>

<template>
  <section class="section" data-testid="models-section">
    <header class="section__head">
      <h2 class="section__title">模型</h2>
      <span v-if="dirty" class="section__meta" data-testid="models-dirty">有未保存的改动</span>
      <Spinner v-if="loading || saving" />
      <AppButton v-if="dirty" data-testid="models-revert" :disabled="saving" @click="onRevert">
        撤销改动
      </AppButton>
      <AppButton variant="primary" data-testid="models-save" :disabled="!canSave" @click="onSave">
        保存
      </AppButton>
    </header>

    <p class="proto" data-testid="models-protocol-hint">
      采用 <strong>OpenAI 兼容协议</strong>:对话走 <code>POST /chat/completions</code>,向量走
      <code>POST /embeddings</code>。base_url 填服务根地址(多数平台以 <code>/v1</code> 结尾),
      密钥按各平台签发的值填;三项留空即回落 <code>.env</code> 默认。
    </p>

    <p v-if="restartRequired" class="banner" data-testid="models-restart-banner">
      已保存的改动<strong>尚未生效</strong>:重启后端后按新配置运行(前端无需操作)。
    </p>

    <p v-if="error !== ''" class="section__error" data-testid="models-error">{{ error }}</p>
    <p v-else-if="localError !== ''" class="section__error" data-testid="models-local-error">
      {{ localError }}
    </p>

    <p v-if="loading && !dirty" class="section__loading">正在读取模型配置…</p>

    <div class="cards">
      <ModelCard
        v-for="g in MODEL_GROUPS"
        :key="g.key"
        :group-key="g.key"
        :title="g.title"
        :hint="g.hint"
        :fields="g.fields"
        :values="draft"
        :overridden="overridden"
        :disabled="saving"
        @change="onField"
        @reset="onResetGroup(g.key)"
      />
    </div>

    <p v-if="!dirty" class="section__loading" data-testid="models-hint">
      改动保存到 <code>.taskforce/model_config.json</code>;密钥不回显原文,只显示掩码。
    </p>
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
  font-size: var(--fs-xl);
  font-weight: 600;
  color: var(--text-primary);
}

.section__meta {
  color: var(--text-muted);
  font-size: var(--fs-xs);
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

.proto {
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.proto code {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-primary);
}

.banner {
  padding: var(--sp-2) var(--sp-3);
  background: var(--accent-soft);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-sm);
  color: var(--text-primary);
  font-size: var(--fs-sm);
}

.cards {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
</style>