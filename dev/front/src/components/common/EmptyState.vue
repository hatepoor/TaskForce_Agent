<script setup lang="ts">
// 空列表统一空态:一行标题 + 一行灰字说明 + 可选下一步动作(不放插画,UI-DESIGN §2.1)。
// compact:索引栏等窄容器用,标题降为正文级,避免侧栏被大标题撑爆。
withDefaults(defineProps<{ title?: string; hint?: string; compact?: boolean }>(), {
  title: '',
  hint: '',
  compact: false,
})
</script>

<template>
  <div class="empty" :class="{ 'empty--compact': compact }">
    <p v-if="title" class="empty__title">{{ title }}</p>
    <p v-if="hint" class="empty__hint">{{ hint }}</p>
    <div class="empty__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-6) var(--sp-4);
  text-align: center;
}

.empty__title {
  color: var(--text-primary);
  font-family: var(--font-serif);
  font-size: var(--fs-xxl);
  font-weight: var(--fw-strong);
  line-height: var(--lh-tight);
  letter-spacing: 0.01em;
}

.empty__hint {
  max-width: 520px;
  color: var(--text-muted);
  font-size: var(--fs-md);
  line-height: var(--lh-body);
}

.empty__action {
  margin-top: var(--sp-2);
}

/* 窄容器:标题降到正文级,留白收紧,整体左对齐 */
.empty--compact {
  align-items: flex-start;
  gap: 6px;
  padding: var(--sp-4) var(--sp-2);
  text-align: left;
}

.empty--compact .empty__title {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
  line-height: var(--lh-base);
}

.empty--compact .empty__hint {
  max-width: none;
  font-size: var(--fs-xs);
  line-height: var(--lh-base);
}
</style>