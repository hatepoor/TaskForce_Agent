<script setup lang="ts">
// 新增 MCP 服务器表单(右侧抽屉,UI-DESIGN §4.2)。
// 三条硬约束:
// 1. **切换 transport 不丢草稿**:stdio / http 各一份子草稿,切回原类型内容还在;
// 2. **提交只带当前类型字段 + transport**(buildConfig 负责,缺 transport 后端 422);
// 3. 422 / 校验错误显示在表单顶部错误条,抽屉不关闭、数据不丢。
import { computed, nextTick, reactive, ref, watch } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'
import type { MCPServerConfig } from '@/types/mcp'

import type { McpFormDraft, Transport } from './mcpModel'
import { buildConfig, emptyDraft, emptyRow, isDuplicateName, validateDraft } from './mcpModel'

const props = defineProps<{
  open: boolean
  /** 请求在途(含重名确认等待):禁用两个按钮 */
  submitting: boolean
  /** 顶层错误条文案(后端 422 detail 等) */
  error: string
  /** 已存在的服务器名,用于重名提示(二次确认由父组件弹) */
  existingNames: string[]
}>()

const emit = defineEmits<{
  close: []
  submit: [payload: { name: string; config: MCPServerConfig }]
}>()

const draft = reactive<McpFormDraft>(emptyDraft())
/** 本地校验错误:与 props.error(后端错误)取先出现的那个展示 */
const localError = ref('')

const nameEl = ref<InstanceType<typeof AppInput> | null>(null)

const duplicate = computed(() => isDuplicateName(draft.name, props.existingNames))
const errorText = computed(() => (localError.value !== '' ? localError.value : props.error))

const TRANSPORTS: Array<{ value: Transport; label: string }> = [
  { value: 'stdio', label: 'Stdio' },
  { value: 'http', label: 'Http' },
]

// 每次打开重置草稿;关闭时不清(下次打开再重置),避免"取消后重开看到上次的残留"
watch(
  () => props.open,
  (open) => {
    if (!open) return
    Object.assign(draft, emptyDraft())
    localError.value = ''
    void nextTick(() => {
      const el = nameEl.value?.$el as HTMLInputElement | undefined
      el?.focus()
    })
  },
)

function onSubmit(): void {
  const err = validateDraft(draft)
  localError.value = err
  if (err !== '') return
  emit('submit', { name: draft.name.trim(), config: buildConfig(draft) })
}

/** 抽屉内 Esc 关闭(不放 document 级监听:避免与上层确认弹窗的 Esc 抢事件) */
function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && !props.submitting) emit('close')
}
</script>

<template>
  <div v-if="open" class="scrim" @click.self="!submitting && emit('close')">
    <aside
      class="drawer"
      role="dialog"
      aria-modal="true"
      aria-label="新增 MCP 服务器"
      data-testid="mcp-form-drawer"
      @keydown="onKeydown"
    >
      <header class="drawer__head">
        <h2 class="drawer__title">新增 MCP 服务器</h2>
        <button
          type="button"
          class="drawer__close"
          aria-label="关闭"
          :disabled="submitting"
          data-testid="mcp-form-close"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <div class="drawer__body">
        <p v-if="errorText !== ''" class="form__error" data-testid="mcp-form-error">{{ errorText }}</p>

        <label class="field">
          <span class="field__label">名称</span>
          <AppInput
            ref="nameEl"
            v-model="draft.name"
            data-testid="mcp-form-name"
            placeholder="github-mcp"
            :disabled="submitting"
          />
          <span class="field__hint">须为小写字母 / 数字 / 下划线 / 连字符</span>
        </label>

        <p v-if="duplicate" class="form__warn" data-testid="mcp-form-overwrite-hint">
          已存在同名服务器,保存将覆盖它的全部配置。
        </p>

        <div class="field">
          <span class="field__label">传输方式</span>
          <div class="seg" role="group" aria-label="传输方式">
            <button
              v-for="t in TRANSPORTS"
              :key="t.value"
              type="button"
              class="seg__btn"
              :class="{ 'seg__btn--on': draft.transport === t.value }"
              :aria-pressed="draft.transport === t.value"
              :data-testid="`mcp-form-transport-${t.value}`"
              :disabled="submitting"
              @click="draft.transport = t.value"
            >
              {{ t.label }}
            </button>
          </div>
        </div>

        <!-- Stdio:字段随 transport 整体替换,两份草稿互不影响 -->
        <template v-if="draft.transport === 'stdio'">
          <label class="field">
            <span class="field__label">命令</span>
            <AppInput
              v-model="draft.stdio.command"
              data-testid="mcp-form-command"
              placeholder="npx"
              :disabled="submitting"
            />
          </label>

          <label class="field">
            <span class="field__label">参数</span>
            <textarea
              v-model="draft.stdio.argsText"
              class="field__area"
              rows="2"
              placeholder="-y @modelcontextprotocol/server-filesystem ./"
              :disabled="submitting"
              data-testid="mcp-form-args"
            />
            <span class="field__hint">按空白切分,换行/空格都行</span>
          </label>

          <div class="field">
            <span class="field__label">环境变量(可选)</span>
            <div v-for="(row, i) in draft.stdio.env" :key="i" class="kv">
              <AppInput
                v-model="row.key"
                class="kv__key"
                data-testid="mcp-form-env-key"
                placeholder="KEY"
                :disabled="submitting"
              />
              <AppInput
                v-model="row.value"
                class="kv__val"
                data-testid="mcp-form-env-value"
                placeholder="value"
                :disabled="submitting"
              />
              <button
                type="button"
                class="kv__del"
                aria-label="删除该变量"
                :disabled="submitting"
                data-testid="mcp-form-env-del"
                @click="draft.stdio.env.splice(i, 1)"
              >
                ×
              </button>
            </div>
            <AppButton
              data-testid="mcp-form-env-add"
              :disabled="submitting"
              @click="draft.stdio.env.push(emptyRow())"
            >
              + 添加变量
            </AppButton>
          </div>
        </template>

        <!-- Http -->
        <template v-else>
          <label class="field">
            <span class="field__label">URL</span>
            <AppInput
              v-model="draft.http.url"
              data-testid="mcp-form-url"
              placeholder="https://mcp.context7.com/mcp"
              :disabled="submitting"
            />
            <span class="field__hint">须带 http:// 或 https:// 协议头</span>
          </label>

          <div class="field">
            <span class="field__label">请求头(可选)</span>
            <div v-for="(row, i) in draft.http.headers" :key="i" class="kv">
              <AppInput
                v-model="row.key"
                class="kv__key"
                data-testid="mcp-form-header-key"
                placeholder="Authorization"
                :disabled="submitting"
              />
              <AppInput
                v-model="row.value"
                class="kv__val"
                data-testid="mcp-form-header-value"
                placeholder="Bearer sk-…"
                :disabled="submitting"
              />
              <button
                type="button"
                class="kv__del"
                aria-label="删除该请求头"
                :disabled="submitting"
                data-testid="mcp-form-header-del"
                @click="draft.http.headers.splice(i, 1)"
              >
                ×
              </button>
            </div>
            <AppButton
              data-testid="mcp-form-header-add"
              :disabled="submitting"
              @click="draft.http.headers.push(emptyRow())"
            >
              + 添加请求头
            </AppButton>
          </div>
        </template>
      </div>

      <footer class="drawer__foot">
        <AppButton data-testid="mcp-form-cancel" :disabled="submitting" @click="emit('close')">
          取消
        </AppButton>
        <AppButton
          variant="primary"
          data-testid="mcp-form-submit"
          :disabled="submitting"
          @click="onSubmit"
        >
          {{ submitting ? '保存中…' : '保存' }}
        </AppButton>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.scrim {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  justify-content: flex-end;
  background: rgba(0, 0, 0, 0.35);
}

.drawer {
  display: flex;
  flex-direction: column;
  width: min(var(--layout-drawer), 100%);
  height: 100%;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-strong);
  box-shadow: var(--shadow-pop);
}

.drawer__head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-subtle);
}

.drawer__title {
  flex: 1;
  font-size: var(--fs-lg);
  font-weight: 600;
}

.drawer__close {
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  color: var(--text-muted);
  font-size: var(--fs-lg);
  line-height: 1;
  cursor: pointer;
}

.drawer__close:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.drawer__body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  flex: 1;
  min-height: 0;
  padding: var(--sp-4);
  overflow-y: auto;
}

.drawer__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border-subtle);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.field__label {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.field__hint {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}

/* 多行参数框:与 AppInput 视觉同源(原生 textarea,AppInput 只管单行) */
.field__area {
  width: 100%;
  padding: var(--sp-2);
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  line-height: var(--lh-base);
  resize: vertical;
}

.field__area::placeholder {
  color: var(--text-muted);
}

.field__area:focus {
  border-color: var(--border-focus);
  outline: none;
}

.form__error {
  padding: var(--sp-2) var(--sp-3);
  background: var(--danger-soft);
  border-left: 2px solid var(--danger);
  border-radius: var(--r-sm);
  color: var(--danger);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
  word-break: break-word;
}

.form__warn {
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-input);
  border-left: 2px solid var(--warning);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.seg {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
}

.seg__btn {
  min-width: 72px;
  padding: 2px var(--sp-3);
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: var(--fs-md);
  cursor: pointer;
}

.seg__btn--on {
  background: var(--bg-raised);
  color: var(--text-primary);
}

.kv {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-1);
}

/* 子组件根元素带父级 scope,可直接限定宽度 */
.kv__key {
  flex: 0 0 40%;
}

.kv__val {
  flex: 1;
}

.kv__del {
  flex: none;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  color: var(--text-muted);
  cursor: pointer;
}

.kv__del:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--danger);
}
</style>