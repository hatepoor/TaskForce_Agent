<script setup lang="ts">
// 用户消息:右对齐气泡,限宽 76%,保留换行(UI-DESIGN §3.2)。
// 气泡给描边 + 略亮的底色,和 AI 正文拉开"谁在说话"的对比;右下角收一个小圆角作指向。
import type { UserItem } from '@/types/chat'

defineProps<{ item: UserItem }>()
</script>

<template>
  <div class="bubble" data-testid="user-bubble">{{ item.text }}</div>
</template>

<style scoped>
.bubble {
  align-self: flex-end;
  max-width: 76%;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-hover);
  border: 1px solid var(--border-subtle);
  /* 右下角收口:一条隐性的"发言指向",不引入箭头装饰 */
  border-radius: var(--r-lg) var(--r-lg) var(--r-sm) var(--r-lg);
  color: var(--text-primary);
  font-size: var(--fs-lg);
  line-height: var(--lh-base);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>