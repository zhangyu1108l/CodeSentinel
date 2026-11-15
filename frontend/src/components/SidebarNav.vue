<script setup lang="ts">
import { Document, Odometer, TrendCharts } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = withDefaults(
  defineProps<{
    collapsed?: boolean
  }>(),
  {
    collapsed: false,
  },
)

const route = useRoute()

const activePath = computed(() => {
  if (route.name === 'dashboard') {
    return '/'
  }
  if (route.name === 'review-history' || route.name === 'review-detail') {
    return '/reviews'
  }
  if (route.name === 'insights') {
    return '/insights'
  }
  return ''
})
</script>

<template>
  <nav class="sidebar-nav" aria-label="Main navigation">
    <p v-if="!props.collapsed" class="nav-section-label">Workspace</p>

    <el-menu
      :default-active="activePath"
      :collapse="props.collapsed"
      :collapse-transition="false"
      :class="{ 'nav-menu--collapsed': props.collapsed }"
      router
      class="nav-menu"
    >
      <el-menu-item index="/">
        <el-icon><Odometer /></el-icon>
        <template #title>Dashboard</template>
      </el-menu-item>

      <el-menu-item index="/reviews">
        <el-icon><Document /></el-icon>
        <template #title>Review History</template>
      </el-menu-item>

      <el-menu-item index="/insights">
        <el-icon><TrendCharts /></el-icon>
        <template #title>Review Insights</template>
      </el-menu-item>
    </el-menu>

    <div v-if="!props.collapsed" class="nav-note">
      <span class="nav-note__label">Available</span>
      <span class="nav-note__text">Review history and insights are live</span>
    </div>
  </nav>
</template>

<style scoped>
.sidebar-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.nav-section-label {
  margin: 0 0 8px;
  padding: 0 22px;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.nav-menu {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #94a3b8;
  --el-menu-hover-bg-color: rgb(148 163 184 / 10%);
  --el-menu-active-color: #fff;

  border-right: none;
}

.nav-menu :deep(.el-menu-item) {
  height: 44px;
  margin: 4px 10px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 550;
}

.nav-menu :deep(.el-menu-item .el-icon) {
  color: #7c8ba5;
  font-size: 18px;
}

.nav-menu :deep(.el-menu-item:hover) {
  color: #e2e8f0;
}

.nav-menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: linear-gradient(100deg, rgb(79 70 229 / 95%), rgb(67 56 202 / 72%));
  box-shadow: 0 8px 18px rgb(15 23 42 / 32%);
}

.nav-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #fff;
}

.nav-menu--collapsed :deep(.el-menu-item) {
  margin: 4px 8px;
}

.nav-menu :deep(.el-menu--collapse) {
  width: 56px;
}

.nav-note {
  margin: auto 14px 0;
  padding: 14px;
  background: linear-gradient(145deg, rgb(30 41 59 / 85%), rgb(15 23 42 / 40%));
  border: 1px solid rgb(148 163 184 / 12%);
  border-radius: 12px;
}

.nav-note__label {
  display: block;
  margin-bottom: 4px;
  color: #818cf8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.nav-note__text {
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.5;
}
</style>
