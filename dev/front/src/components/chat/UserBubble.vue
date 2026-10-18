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
  padding: 11px var(--sp-4);
  /* 暖灰纸面:与 AI 正文的"无容器"形成轻对比,不抢强调色 */
  background: var(--bg-user);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  color: var(--text-primary);
  font-size: var(--fs-lg);
  line-height: var(--lh-body);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>