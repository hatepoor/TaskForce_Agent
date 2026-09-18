<script setup lang="ts">
// 单个 skill 卡:name(等宽)+ description + dir 单行省略 + 复制(UI-DESIGN §4.4)。
// 纯只读,不提供任何写操作。
import AppButton from '@/components/common/AppButton.vue'

import type { SkillMeta } from '@/types/skills'

defineProps<{ skill: SkillMeta }>()
const emit = defineEmits<{ copy: [dir: string] }>()
</script>

<template>
  <article class="card" data-testid="skill-card" :data-skill="skill.name">
    <header class="card__head">
      <h3 class="card__name">{{ skill.name }}</h3>
      <AppButton data-testid="skill-copy" @click="emit('copy', skill.dir)">复制目录</AppButton>
    </header>

    <p v-if="skill.description !== ''" class="card__desc">{{ skill.description }}</p>
    <p v-else class="card__desc card__desc--empty">(该技能没有写 description)</p>

    <p class="card__dir" :title="skill.dir">{{ skill.dir }}</p>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
}

.card__head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.card__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  font-weight: 600;
}

.card__desc {
  color: var(--text-secondary);
  font-size: var(--fs-md);
  line-height: var(--lh-base);
}

.card__desc--empty {
  color: var(--text-muted);
}

/* dir 是服务端本地绝对路径:单行省略,完整值放 title */
.card__dir {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}
</style>