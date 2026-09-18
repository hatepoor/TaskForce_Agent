<script setup lang="ts">
// 错误条:三形态共用一套样式(UI-DESIGN §3.4)——请求失败给「重试」,
// 流中断(已有部分正文)给「重试 + 复制已生成内容」;abort 不进这里(走灰字提示)。
import AppButton from '@/components/common/AppButton.vue'

withDefaults(
  defineProps<{
    message: string
    status?: number
    canRetry?: boolean
    canCopy?: boolean
  }>(),
  { canRetry: false, canCopy: false },
)

const emit = defineEmits<{ retry: []; copy: [] }>()
</script>

<template>
  <div class="err" data-testid="error-notice">
    <p class="err__text">
      <span class="err__mark">!</span>
      <span>{{ status === undefined ? message : `连接失败:${status} · ${message}` }}</span>
    </p>
    <p v-if="canRetry || canCopy" class="err__actions">
      <AppButton v-if="canRetry" data-testid="error-retry" @click="emit('retry')">重试</AppButton>
      <AppButton v-if="canCopy" data-testid="error-copy" @click="emit('copy')">复制已生成内容</AppButton>
    </p>
  </div>
</template>

<style scoped>
.err {
  margin-top: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--danger);
  border-radius: var(--r-sm);
  background: transparent;
}

.err__text {
  display: flex;
  gap: var(--sp-2);
  color: var(--danger);
  font-size: var(--fs-sm);
  overflow-wrap: anywhere;
  /* 错误信息必须可选中(UI-DESIGN §6.3) */
  user-select: text;
}

.err__mark {
  flex: none;
  font-weight: 700;
}

.err__actions {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
</style>