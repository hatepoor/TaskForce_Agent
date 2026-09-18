<script setup lang="ts">
// 四段式应用外壳:导航轨 + 上下文栏 + 弹性主区(第四段右侧抽屉由对话模块接入)。
// 上下文栏折叠态在本层管理;拖拽调宽(200–320px)留待会话列表落地后做。
import { ref } from 'vue'

import ContextPanel from './ContextPanel.vue'
import NavRail from './NavRail.vue'

const panelCollapsed = ref(false)
</script>

<template>
  <div class="shell" :class="{ 'shell--collapsed': panelCollapsed }">
    <NavRail class="shell__rail" />
    <ContextPanel v-show="!panelCollapsed" class="shell__panel" @collapse="panelCollapsed = true" />

    <main class="shell__main">
      <!-- 主区:四视图懒加载 + KeepAlive(切视图不卸载,保住对话状态,UI-DESIGN §1.2) -->
      <router-view v-slot="{ Component }">
        <KeepAlive>
          <component :is="Component" />
        </KeepAlive>
      </router-view>

      <!-- 折叠后用于恢复上下文栏 -->
      <button
        v-if="panelCollapsed"
        type="button"
        class="shell__restore"
        title="展开上下文栏"
        aria-label="展开上下文栏"
        @click="panelCollapsed = false"
      >
        »
      </button>
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--layout-rail) var(--layout-panel) minmax(520px, 1fr);
  height: 100%;
  /* 整体最小可用宽度;窄于此时出横向滚动,不做移动端(UI-DESIGN §1.1) */
  min-width: 1024px;
}

.shell--collapsed {
  grid-template-columns: var(--layout-rail) 0 minmax(520px, 1fr);
}

/* 显式列定位:防止 ContextPanel 被 v-show 移除后,主区被自动排进 0 宽的折叠列 */
.shell__rail {
  grid-column: 1;
}

.shell__panel {
  grid-column: 2;
}

.shell__main {
  grid-column: 3;
  position: relative;
  min-width: 0;
  overflow-y: auto;
  background: var(--bg-base);
}

.shell__restore {
  position: absolute;
  top: var(--sp-3);
  left: var(--sp-3);
  width: 24px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  cursor: pointer;
}

.shell__restore:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>