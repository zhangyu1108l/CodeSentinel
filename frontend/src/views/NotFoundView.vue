<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goToDashboard() {
  void router.push('/')
}
</script>

<template>
  <div class="page not-found-page">
    <div class="not-found-card">
      <span class="not-found-code">404</span>
      <h1>Page not found</h1>
      <p>The page you are looking for does not exist or has moved.</p>
      <el-button type="primary" @click="goToDashboard">
        Back to dashboard
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.not-found-page {
  display: grid;
  min-height: calc(100vh - 64px);
  place-items: center;
}

.not-found-card {
  max-width: 420px;
  padding: 44px 36px;
  text-align: center;
  background: var(--cs-surface);
  border: 1px solid var(--cs-border);
  border-radius: 16px;
  box-shadow: var(--cs-shadow-sm);
}

.not-found-code {
  display: inline-block;
  margin-bottom: 12px;
  color: #c7d2fe;
  font-family: var(--cs-mono);
  font-size: 56px;
  font-weight: 700;
  letter-spacing: -0.06em;
  line-height: 1;
}

.not-found-card h1 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.02em;
}

.not-found-card p {
  margin: 0 0 22px;
  color: var(--cs-muted);
  font-size: 13px;
  line-height: 1.6;
}
</style>
