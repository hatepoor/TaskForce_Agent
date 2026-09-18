<script setup lang="ts">
// 一张模型配置卡(展示型:parent 持草稿,这里只渲染 + 冒泡改动)。
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'
import type { ModelConfigValues, ModelField } from '@/types/models'

import type { ModelFieldSpec } from './modelsModel'

const props = withDefaults(
  defineProps<{
    groupKey: string
    title: string
    hint: string
    fields: readonly ModelFieldSpec[]
    values: ModelConfigValues
    /** 由设置页覆盖的字段(重启后接管) */
    overridden: readonly ModelField[]
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  change: [field: ModelField, value: string]
  reset: []
}>()

function overriddenIn(fields: readonly ModelFieldSpec[]): number {
  return fields.filter((f) => props.overridden.includes(f.field)).length
}
</script>

<template>
  <section class="card" :data-testid="`model-card-${groupKey}`">
    <header class="card__head">
      <h3 class="card__title">{{ title }}</h3>
      <span v-if="overriddenIn(fields) > 0" class="card__badge" data-testid="model-card-override-badge">
        设置页覆盖 {{ overriddenIn(fields) }} 项
      </span>
      <AppButton :data-testid="`model-reset-${groupKey}`" :disabled="disabled" @click="emit('reset')">
        恢复 .env 默认
      </AppButton>
    </header>
    <p class="card__hint">{{ hint }}</p>

    <label v-for="f in fields" :key="f.field" class="row">
      <span class="row__label">
        {{ f.label }}
        <span v-if="overridden.includes(f.field)" class="row__mark" :data-testid="`model-overridden-${f.field}`">
          · 已覆盖
        </span>
      </span>
      <AppInput
        :model-value="values[f.field]"
        :type="f.secret === true ? 'password' : 'text'"
        :placeholder="f.placeholder"
        :disabled="disabled"
        :data-testid="`model-input-${f.field}`"
        @update:model-value="(v: string) => emit('change', f.field, v)"
      />
    </label>
  </section>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
}

.card__head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.card__title {
  flex: 1;
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.card__badge {
  padding: 0 var(--sp-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: var(--fs-xs);
}

.card__hint {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}

.row {
  display: grid;
  grid-template-columns: 180px 1fr;
  align-items: center;
  gap: var(--sp-3);
}

.row__label {
  color: var(--text-secondary);
  font-size: var(--fs-md);
  font-family: var(--font-mono);
}

.row__mark {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}
</style>