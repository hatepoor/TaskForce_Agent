<script setup lang="ts">
// Health 节:三张指标卡 + 手动刷新(UI-DESIGN §2.4 / §4.4)。
// 数据源是 useHealthPoll(30s 轮询 / 不可见暂停);手动刷新失败弹 toast,后台轮询失败只就地展示。
import { computed } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useUiStore } from '@/stores/ui'
import { fmtClock } from '@/utils/time'

import HealthCard from './HealthCard.vue'
import { healthCards } from './healthModel'
import { useHealthPoll } from '@/composables/useHealthPoll'

const ui = useUiStore()
const { data, loading, error, updatedAt, refresh } = useHealthPoll()

const cards = computed(() => healthCards(data.value))
/** 首次加载(还没有任何数据)与"刷新中但有旧数据"要区分开 */
const firstLoading = computed(() => loading.value && data.value === null)
const checkedAt = computed(() => (updatedAt.value > 0 ? fmtClock(updatedAt.value) : ''))

async function onRefresh(): Promise<void> {
  const err = await refresh()
  if (err !== '') ui.toast(err, 'error')
}
</script>

<template>
  <section class="section" data-testid="health-section">
    <header class="section__head">
      <h2 class="section__title">Health</h2>
      <span v-if="checkedAt" class="section__meta" data-testid="health-checked-at">
        最近检测 {{ checkedAt }}
      </span>
      <Spinner v-if="loading" />
      <AppButton data-testid="health-refresh" :disabled="loading" @click="onRefresh">
        重新检测
      </AppButton>
    </header>

    <p v-if="error !== ''" class="section__error" data-testid="health-error">{{ error }}</p>

    <p v-if="firstLoading" class="section__loading" data-testid="health-loading">正在检测后端状态…</p>

    <div v-else-if="cards.length === 0" class="section__loading">
      还没有检测结果,点「重新检测」拉一次。
    </div>

    <div v-else class="cards">
      <HealthCard
        v-for="c in cards"
        :key="c.key"
        :name="c.key"
        :label="c.label"
        :state="c.state"
        :value="c.value"
        :detail="c.detail"
      />
    </div>

    <p class="section__hint">
      sandbox 值域不封闭,非 ok 一律按异常展示;db 的异常文本原样输出。每 30 秒自动检测一次(页面不可见时暂停)。
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

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--sp-3);
}

.section__hint {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  line-height: var(--lh-base);
}
</style>