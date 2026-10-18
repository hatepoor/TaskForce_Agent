<script setup lang="ts">
// 记忆工具栏:条数统计 + 关键字本地过滤 + 刷新(UI-DESIGN §2.3/§4.3)。
// 过滤只改视图,不发请求 —— 后端 /memory 无搜索参数,不假装成搜索接口。
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'
import Spinner from '@/components/common/Spinner.vue'

const keyword = defineModel<string>({ default: '' })

defineProps<{
  /** 已渲染好的条数文案(countText 产物) */
  countText: string
  loading: boolean
}>()

const emit = defineEmits<{ refresh: [] }>()
</script>

<template>
  <div class="toolbar" data-testid="memory-toolbar">
    <span class="toolbar__count" data-testid="memory-count">{{ countText }}</span>
    <AppInput
      v-model="keyword"
      class="toolbar__filter"
      type="search"
      placeholder="过滤记忆…"
      data-testid="memory-filter"
    />
    <AppButton :disabled="loading" data-testid="memory-refresh" @click="emit('refresh')">
      <Spinner v-if="loading" :size="12" />
      刷新
    </AppButton>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.toolbar__count {
  flex: none;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.toolbar__filter {
  flex: 1;
  min-width: 0;
  max-width: 320px;
  margin-right: auto;
}

/* 窄屏:计数文案换行优先,过滤框仍可用 */
@media (max-width: 720px) {
  .toolbar {
    flex-wrap: wrap;
    gap: var(--sp-2);
  }

  .toolbar__filter {
    max-width: none;
    flex-basis: 100%;
    order: 3;
  }
}
</style>