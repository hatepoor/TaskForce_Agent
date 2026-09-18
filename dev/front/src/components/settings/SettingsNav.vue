<script setup lang="ts">
// 上下文栏的设置节列表:切节即切路由(每节独立页面,刷新/深链直达)。
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const SECTIONS = [
  { id: 'models', label: '模型', hint: '主模型与 Embedding' },
  { id: 'mcp', label: 'MCP 服务器', hint: '接入外部工具' },
  { id: 'skills', label: 'Skills', hint: '技能元数据' },
  { id: 'health', label: 'Health', hint: '后端自检' },
] as const

const route = useRoute()
const router = useRouter()

const active = computed(() => {
  const raw = route.params.section
  // 可选参数缺失时 vue-router 给的是空串(不是 undefined):空串按默认节处理
  return typeof raw === 'string' && raw !== '' ? raw : 'mcp'
})

function go(id: string): void {
  void router.push({ name: 'settings', params: { section: id } })
}
</script>

<template>
  <nav class="nav" aria-label="设置分节" data-testid="settings-nav">
    <button
      v-for="s in SECTIONS"
      :key="s.id"
      type="button"
      class="nav__item"
      :class="{ 'nav__item--on': active === s.id }"
      :aria-current="active === s.id ? 'page' : undefined"
      :data-testid="`settings-nav-${s.id}`"
      @click="go(s.id)"
    >
      <span class="nav__label">{{ s.label }}</span>
      <span class="nav__hint">{{ s.hint }}</span>
    </button>
  </nav>
</template>

<style scoped>
.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--sp-2);
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  text-align: left;
  cursor: pointer;
}

.nav__item:hover {
  background: var(--bg-hover);
}

.nav__item--on {
  background: var(--accent-soft);
}

.nav__label {
  color: var(--text-secondary);
  font-size: var(--fs-md);
}

.nav__item--on .nav__label {
  color: var(--text-primary);
}

.nav__hint {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}
</style>