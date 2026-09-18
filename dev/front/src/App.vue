<script setup lang="ts">
// 根组件:应用外壳 + 全局浮层;不含业务逻辑(ARCHITECTURE §2)。
// 四段式外壳见 components/layout/AppShell.vue。
import AppShell from '@/components/layout/AppShell.vue'
import ToastHost from '@/components/layout/ToastHost.vue'
</script>

<template>
  <AppShell />
  <ToastHost />
</template>