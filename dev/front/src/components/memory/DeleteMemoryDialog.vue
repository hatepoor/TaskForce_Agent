<script setup lang="ts">
// 删除确认弹窗:完整回显记忆原文 + 不可恢复提示,确认按钮 danger(UI-DESIGN §4.3)。
// 安全侧默认:焦点落在「取消」,Esc / 点遮罩均可取消;删除进行中两者都失效。
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'

const props = defineProps<{
  /** 待删除记忆的完整原文 */
  content: string
  /** 删除请求进行中:禁用两个按钮并屏蔽 Esc / 遮罩取消 */
  deleting: boolean
  /** 删除失败原因(空串表示无错误) */
  error: string
}>()

const emit = defineEmits<{ confirm: []; cancel: [] }>()

const cancelBtn = ref<InstanceType<typeof AppButton> | null>(null)

function requestCancel(): void {
  if (props.deleting) return
  emit('cancel')
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') requestCancel()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  void nextTick(() => {
    const el = cancelBtn.value?.$el
    if (el instanceof HTMLElement) el.focus()
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <!-- 遮罩点击 = 取消(危险操作不因误点而执行) -->
    <div class="mask" data-testid="memory-delete-mask" @click.self="requestCancel">
      <div
        class="dlg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="memory-delete-title"
        data-testid="memory-delete-dialog"
      >
        <p id="memory-delete-title" class="dlg__title">删除这条记忆?</p>

        <blockquote class="dlg__quote" data-testid="memory-delete-content">
          {{ content || '(该条记忆没有正文)' }}
        </blockquote>

        <p class="dlg__warn">删除后智能体不再记得这条信息,不可恢复。</p>
        <p v-if="error" class="dlg__error" data-testid="memory-delete-error">{{ error }}</p>

        <div class="dlg__foot">
          <AppButton ref="cancelBtn" :disabled="deleting" data-testid="memory-delete-cancel" @click="requestCancel">
            取消
          </AppButton>
          <AppButton
            variant="danger"
            :disabled="deleting"
            data-testid="memory-delete-confirm"
            @click="emit('confirm')"
          >
            <Spinner v-if="deleting" :size="12" />
            {{ deleting ? '删除中…' : '删除' }}
          </AppButton>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
  background: rgba(0, 0, 0, 0.45);
}

.dlg {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  width: 460px;
  max-width: calc(100% - var(--sp-6));
  padding: var(--sp-4);
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-pop);
}

.dlg__title {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.dlg__quote {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  max-height: 240px;
  overflow-y: auto;
  background: var(--bg-input);
  border-left: 2px solid var(--border-strong);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  font-size: var(--fs-md);
  line-height: var(--lh-body);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.dlg__warn {
  font-size: var(--fs-sm);
  color: var(--warning);
}

.dlg__error {
  font-size: var(--fs-sm);
  color: var(--danger);
}

.dlg__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
}
</style>