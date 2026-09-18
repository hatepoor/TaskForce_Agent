<script setup lang="ts">
// 设置页:四节独立展示,节名走路由参数(/settings/:section),切换由上下文栏的节列表驱动。
// 各节组件自带标题与操作区,这里只做页面容器,不重复标题。
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import HealthSection from '@/components/settings/HealthSection.vue'
import McpSection from '@/components/settings/McpSection.vue'
import ModelsSection from '@/components/settings/ModelsSection.vue'
import SkillsSection from '@/components/settings/SkillsSection.vue'

type SectionId = 'mcp' | 'skills' | 'health' | 'models'

const SECTIONS: readonly SectionId[] = ['mcp', 'skills', 'health', 'models']

const route = useRoute()
const section = computed<SectionId>(() => {
  const raw = route.params.section
  return typeof raw === 'string' && (SECTIONS as readonly string[]).includes(raw)
    ? (raw as SectionId)
    : 'mcp'
})
</script>

<template>
  <section class="view" data-testid="settings-view" :data-section="section">
    <McpSection v-if="section === 'mcp'" />
    <SkillsSection v-else-if="section === 'skills'" />
    <HealthSection v-else-if="section === 'health'" />
    <ModelsSection v-else />
  </section>
</template>

<style scoped>
.view {
  width: min(var(--measure-page), 100%);
  margin: 0 auto;
  padding: var(--sp-5) var(--sp-4) var(--sp-6);
}
</style>