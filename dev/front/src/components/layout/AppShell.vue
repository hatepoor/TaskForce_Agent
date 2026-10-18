<script setup lang="ts">
// 两段式应用外壳(v2):单列索引栏 + 弹性主区。
// 索引栏吸收原来的「图标轨 + 上下文栏」两段职责,窄屏(<1080px)改为抽屉,
// 由主区顶部细条唤出、点遮罩收回。
import { onBeforeUnmount, onMounted, ref } from 'vue'

import NavRail from './NavRail.vue'

const NARROW_QUERY = '(max-width: 1080px)'

const narrow = ref(false)
const drawerOpen = ref(false)

let mq: MediaQueryList | null = null

function onMediaChange(e: MediaQueryListEvent): void {
  narrow.value = e.matches
  if (!e.matches) drawerOpen.value = false
}

onMounted(() => {
  mq = window.matchMedia(NARROW_QUERY)
  narrow.value = mq.matches
  mq.addEventListener('change', onMediaChange)
})

onBeforeUnmount(() => {
  mq?.removeEventListener('change', onMediaChange)
})
</script>

<template>
  <div class="shell" :class="{ 'shell--drawer': narrow && drawerOpen }">
    <NavRail class="shell__rail" @navigate="drawerOpen = false" />

    <!-- 窄屏抽屉遮罩:点击收回 -->
    <div
      v-if="narrow && drawerOpen"
      class="shell__scrim"
      aria-hidden="true"
      @click="drawerOpen = false"
    />

    <main class="shell__main">
      <!-- 窄屏顶部细条:索引栏收起时的唯一入口,不遮挡内容 -->
      <header v-if="narrow" class="shell__bar">
        <button
          type="button"
          class="shell__menu"
          title="打开导航"
          aria-label="打开导航"
          data-testid="rail-open"
          @click="drawerOpen = true"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
        </button>
        <span class="shell__bar-brand">TaskForce</span>
      </header>

      <div class="shell__content">
        <!-- 主区:四视图懒加载 + KeepAlive(切视图不卸载,保住对话状态) -->
        <router-view v-slot="{ Component }">
          <KeepAlive>
            <component :is="Component" />
          </KeepAlive>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--layout-rail) minmax(0, 1fr);
  height: 100%;
  background: var(--bg-base);
}

.shell__rail {
  min-width: 0;
  height: 100%;
}

.shell__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-base);
}

.shell__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

/* 窄屏顶部细条:只在抽屉形态出现 */
.shell__bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
  height: 44px;
  padding: 0 var(--sp-3);
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-subtle);
}

.shell__menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  cursor: pointer;
}

.shell__menu:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.shell__menu svg {
  width: 18px;
  height: 18px;
}

.shell__bar-brand {
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: var(--fw-strong);
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.shell__scrim {
  position: fixed;
  inset: 0;
  z-index: var(--z-scrim);
  background: rgba(28, 26, 22, 0.36);
}

/* 窄屏:索引栏改为左侧抽屉,主区占满 */
@media (max-width: 1080px) {
  .shell {
    grid-template-columns: minmax(0, 1fr);
  }

  .shell__rail {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: var(--z-drawer);
    width: min(var(--layout-rail), 84vw);
    transform: translateX(-100%);
    transition: transform var(--t-base);
    box-shadow: var(--shadow-pop);
  }

  .shell--drawer .shell__rail {
    transform: none;
  }
}
</style>
