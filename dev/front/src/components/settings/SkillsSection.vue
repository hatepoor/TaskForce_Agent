<script setup lang="ts">
// Skills 节:只读列表(UI-DESIGN §4.4)。
// 后端每次现扫目录,但智能体侧 _skills_meta() 有 lru_cache——新增技能目录后本页立刻可见、
// 路由仍用旧缓存,故顶部固定一行"变更需重启后端生效"。
import { onMounted, ref } from 'vue'

import { errText } from '@/api/http'
import { listSkills } from '@/api/skills'
import AppButton from '@/components/common/AppButton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Spinner from '@/components/common/Spinner.vue'
import { useUiStore } from '@/stores/ui'
import type { SkillMeta } from '@/types/skills'

import SkillCard from './SkillCard.vue'

const ui = useUiStore()

const skills = ref<SkillMeta[]>([])
const loading = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await listSkills()
    skills.value = res.skills ?? []
    error.value = ''
  } catch (e) {
    error.value = errText(e)
    ui.toast(error.value, 'error')
  } finally {
    loading.value = false
  }
}

async function copyDir(dir: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(dir)
    ui.toast('已复制技能目录')
  } catch {
    ui.toast('复制失败,请手动选中复制', 'error')
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="section" data-testid="skills-section">
    <header class="section__head">
      <h2 class="section__title">Skills</h2>
      <span class="section__meta">{{ skills.length }} 个</span>
      <Spinner v-if="loading" />
      <AppButton data-testid="skills-refresh" :disabled="loading" @click="load">刷新</AppButton>
    </header>

    <p class="section__notice" data-testid="skills-notice">
      技能由 skills/ 目录下的 SKILL.md 定义;编辑文件后需<b>重启后端</b>才能在路由中生效。
    </p>

    <p v-if="error !== ''" class="section__error" data-testid="skills-error">{{ error }}</p>

    <p v-if="loading && skills.length === 0" class="section__loading">正在读取技能目录…</p>

    <!-- 拉取失败时只给错误条,不并排显示"还没有技能"(自相矛盾) -->
    <EmptyState
      v-else-if="skills.length === 0 && error === ''"
      data-testid="skills-empty"
      title="还没有技能"
      hint="在 skills/ 下新建技能目录(内含带 frontmatter 的 SKILL.md),重启后端后生效。"
    />

    <div v-else class="list">
      <SkillCard v-for="s in skills" :key="s.name" :skill="s" @copy="copyDir" />
    </div>
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

.section__notice {
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-input);
  border-left: 2px solid var(--border-strong);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.section__notice b {
  color: var(--text-primary);
  font-weight: 600;
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

.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
</style>