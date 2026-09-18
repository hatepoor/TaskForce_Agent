<script setup lang="ts">
// AI 头像:三点连线的小图标(agent/关系图语义),中性配色不抢强调色;
// 思考中时描边转强调色并轻微呼吸,给"模型正在干活"的持续反馈。
// 圆形底 + 稍粗的描边:在深色底上够得着"头像"的识别度,不像图裂了的小图标。
withDefaults(defineProps<{ thinking?: boolean }>(), { thinking: false })
</script>

<template>
  <span class="avatar" :class="{ 'avatar--thinking': thinking }" aria-hidden="true" data-testid="ai-avatar">
    <svg
      class="avatar__glyph"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
    >
      <circle cx="6.5" cy="12" r="2.2" />
      <circle cx="17.5" cy="6.5" r="2.2" />
      <circle cx="17.5" cy="17.5" r="2.2" />
      <path d="M8.4 10.9 L15.6 7.4" />
      <path d="M8.4 13.1 L15.6 16.6" />
    </svg>
  </span>
</template>

<style scoped>
.avatar {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--bg-hover);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-full);
  color: var(--text-primary);
}

.avatar__glyph {
  width: 15px;
  height: 15px;
}

.avatar--thinking {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  animation: avatar-pulse 1.6s ease-in-out infinite;
}

@keyframes avatar-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 var(--accent-soft);
  }
  50% {
    box-shadow: 0 0 0 4px var(--accent-soft);
  }
}

@media (prefers-reduced-motion: reduce) {
  .avatar--thinking {
    animation: none;
  }
}
</style>