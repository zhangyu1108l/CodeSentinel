<script setup lang="ts">
import {
  Close,
  Expand,
  Fold,
  Menu as MenuIcon,
  TopRight,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import BrandMark from '@/components/BrandMark.vue'
import SidebarNav from '@/components/SidebarNav.vue'
import { APP_VERSION, REPOSITORY_URL } from '@/config/app'

const route = useRoute()

const isMobile = ref(false)
const sidebarCollapsed = ref(false)
const mobileDrawerOpen = ref(false)

let mediaQuery: MediaQueryList | undefined

const pageTitle = computed(() => route.meta.title ?? 'Dashboard')

const toggleLabel = computed(() => {
  if (isMobile.value) {
    return 'Open navigation'
  }
  return sidebarCollapsed.value ? 'Expand navigation' : 'Collapse navigation'
})

const navigationExpanded = computed(() =>
  isMobile.value ? mobileDrawerOpen.value : !sidebarCollapsed.value,
)

const navigationControls = computed(() =>
  isMobile.value ? 'mobile-navigation-drawer' : 'app-sidebar',
)

function syncViewport() {
  if (!mediaQuery) {
    return
  }
  isMobile.value = mediaQuery.matches
  if (!isMobile.value) {
    mobileDrawerOpen.value = false
  }
}

function toggleSidebar() {
  if (isMobile.value) {
    mobileDrawerOpen.value = true
    return
  }
  sidebarCollapsed.value = !sidebarCollapsed.value
}

onMounted(() => {
  if (typeof window.matchMedia !== 'function') {
    return
  }
  mediaQuery = window.matchMedia('(max-width: 959px)')
  isMobile.value = mediaQuery.matches
  mediaQuery.addEventListener('change', syncViewport)
})

onBeforeUnmount(() => {
  mediaQuery?.removeEventListener('change', syncViewport)
})

watch(
  () => route.fullPath,
  () => {
    mobileDrawerOpen.value = false
  },
)
</script>

<template>
  <div class="app-shell">
    <aside
      id="app-sidebar"
      class="app-sidebar"
      :class="{ 'is-collapsed': sidebarCollapsed }"
    >
      <RouterLink class="brand-row" to="/" aria-label="CodeSentinel dashboard">
        <BrandMark :size="38" />
        <span v-if="!sidebarCollapsed" class="brand-copy">
          <strong>CodeSentinel</strong>
          <span>AI code review</span>
        </span>
      </RouterLink>

      <SidebarNav :collapsed="sidebarCollapsed" />

      <div class="sidebar-footer">
        <span class="sidebar-footer__dot" />
        <div v-if="!sidebarCollapsed" class="sidebar-footer__copy">
          <strong>Dashboard</strong>
          <span>Phase 11.1–11.3 delivered · v{{ APP_VERSION }}</span>
        </div>
      </div>
    </aside>

    <div class="app-column">
      <header class="app-header">
        <div class="header-left">
          <el-button
            text
            circle
            class="sidebar-toggle"
            :aria-label="toggleLabel"
            :aria-expanded="navigationExpanded"
            :aria-controls="navigationControls"
            @click="toggleSidebar"
          >
            <el-icon :size="19">
              <MenuIcon v-if="isMobile" />
              <Expand v-else-if="sidebarCollapsed" />
              <Fold v-else />
            </el-icon>
          </el-button>

          <span class="header-divider" aria-hidden="true" />

          <nav class="breadcrumb" aria-label="Breadcrumb">
            <span class="breadcrumb__root">Workspace</span>
            <span class="breadcrumb__sep">/</span>
            <span class="breadcrumb__current">{{ pageTitle }}</span>
          </nav>
        </div>

        <div class="header-right">
          <span class="phase-badge">Dashboard</span>
          <a
            class="header-link"
            :href="REPOSITORY_URL"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
            <el-icon :size="13"><TopRight /></el-icon>
          </a>
        </div>
      </header>

      <main class="app-main">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>

    <el-drawer
      v-model="mobileDrawerOpen"
      title="Navigation"
      direction="ltr"
      size="272px"
      :with-header="false"
      class="sidebar-drawer"
    >
      <div id="mobile-navigation-drawer" class="drawer-sidebar">
        <div class="drawer-topbar">
          <RouterLink
            class="brand-row"
            to="/"
            aria-label="CodeSentinel dashboard"
          >
            <BrandMark :size="38" />
            <span class="brand-copy">
              <strong>CodeSentinel</strong>
              <span>AI code review</span>
            </span>
          </RouterLink>

          <el-button
            text
            circle
            class="drawer-close"
            aria-label="Close navigation"
            @click="mobileDrawerOpen = false"
          >
            <el-icon :size="18"><Close /></el-icon>
          </el-button>
        </div>

        <SidebarNav />

        <div class="sidebar-footer">
          <span class="sidebar-footer__dot" />
          <div class="sidebar-footer__copy">
            <strong>Dashboard</strong>
            <span>Phase 11.1–11.3 delivered · v{{ APP_VERSION }}</span>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--cs-canvas);
}

.app-sidebar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  flex: 0 0 256px;
  flex-direction: column;
  width: 256px;
  height: 100vh;
  padding: 22px 0 18px;
  overflow: hidden;
  color: #e2e8f0;
  background:
    radial-gradient(circle at 20% 0%, rgb(79 70 229 / 22%), transparent 34%),
    linear-gradient(180deg, #0b1220 0%, #0b1324 58%, #080e1a 100%);
  border-right: 1px solid rgb(148 163 184 / 10%);
  transition: flex-basis 180ms ease, width 180ms ease;
}

.app-sidebar.is-collapsed {
  flex-basis: 76px;
  width: 76px;
}

.brand-row {
  display: flex;
  gap: 12px;
  align-items: center;
  min-height: 38px;
  margin: 0 18px 26px;
}

.app-sidebar.is-collapsed .brand-row {
  justify-content: center;
  margin-right: 10px;
  margin-left: 10px;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.25;
}

.brand-copy strong {
  color: #f8fafc;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.015em;
}

.brand-copy span {
  margin-top: 3px;
  color: #64748b;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.sidebar-footer {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 16px 18px 0;
  padding-top: 16px;
  border-top: 1px solid rgb(148 163 184 / 10%);
}

.app-sidebar.is-collapsed .sidebar-footer {
  justify-content: center;
  margin-right: 10px;
  margin-left: 10px;
}

.sidebar-footer__dot {
  flex: none;
  width: 7px;
  height: 7px;
  background: #34d399;
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(52 211 153 / 12%);
}

.sidebar-footer__copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.sidebar-footer__copy strong {
  color: #cbd5e1;
  font-size: 11.5px;
  font-weight: 600;
}

.sidebar-footer__copy span {
  margin-top: 2px;
  overflow: hidden;
  color: #64748b;
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-column {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 26px;
  background: rgb(255 255 255 / 86%);
  border-bottom: 1px solid var(--cs-border);
  backdrop-filter: blur(14px);
}

.header-left,
.header-right {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.sidebar-toggle {
  color: #475569;
}

.header-divider {
  width: 1px;
  height: 18px;
  background: var(--cs-border);
}

.breadcrumb {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
  font-size: 12.5px;
  white-space: nowrap;
}

.breadcrumb__root {
  color: var(--cs-muted);
}

.breadcrumb__sep {
  color: #cbd5e1;
}

.breadcrumb__current {
  overflow: hidden;
  color: #1e293b;
  font-weight: 600;
  text-overflow: ellipsis;
}

.phase-badge {
  padding: 4px 9px;
  color: #4338ca;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: #eef2ff;
  border: 1px solid #e0e7ff;
  border-radius: 999px;
}

.header-link {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  color: #475569;
  font-size: 12.5px;
  font-weight: 550;
  transition: color 140ms ease;
}

.header-link:hover {
  color: var(--cs-accent);
}

.app-main {
  flex: 1;
  min-width: 0;
  background:
    radial-gradient(circle at 100% 0%, rgb(99 102 241 / 5%), transparent 28%),
    var(--cs-canvas);
}

.drawer-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 22px 0 18px;
  color: #e2e8f0;
  background:
    radial-gradient(circle at 20% 0%, rgb(79 70 229 / 24%), transparent 34%),
    linear-gradient(180deg, #0b1220 0%, #0b1324 58%, #080e1a 100%);
}

.drawer-topbar {
  display: flex;
  align-items: center;
}

.drawer-topbar .brand-row {
  flex: 1;
  min-width: 0;
  margin-bottom: 26px;
}

.drawer-close {
  flex: none;
  margin: 0 14px 26px 0;
  color: #94a3b8;
}

.drawer-close:hover {
  color: #f8fafc;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 140ms ease, transform 140ms ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.page-leave-to {
  opacity: 0;
}

@media (max-width: 959px) {
  .app-sidebar {
    display: none;
  }

  .app-header {
    padding: 0 18px;
  }
}

@media (max-width: 640px) {
  .app-header {
    padding: 0 12px;
  }

  .breadcrumb__root,
  .breadcrumb__sep,
  .phase-badge {
    display: none;
  }

  .header-right {
    gap: 8px;
  }

  .header-link {
    font-size: 12px;
  }
}
</style>
