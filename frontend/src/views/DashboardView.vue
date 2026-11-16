<script setup lang="ts">
import {
  ArrowRight,
  CircleCheck,
  DataLine,
  Document,
  Refresh,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { getHealth } from '@/api'
import { API_BASE_URL, APP_VERSION } from '@/config/app'
import type { HealthResponse } from '@/types/api'
import { getErrorMessage } from '@/utils/api-error'

type HealthState = 'loading' | 'online' | 'offline'

const healthState = ref<HealthState>('loading')
const health = ref<HealthResponse | null>(null)
const healthError = ref('')
const latencyMs = ref<number | null>(null)

let activeRequest: AbortController | null = null

const healthLabel = computed(() => {
  if (healthState.value === 'loading') {
    return 'Checking'
  }
  return healthState.value === 'online' ? 'Operational' : 'Unavailable'
})

const apiTarget = computed(() => {
  if (API_BASE_URL) {
    return API_BASE_URL
  }
  return import.meta.env.DEV ? 'Same origin (Vite dev proxy)' : 'Same origin'
})
const frontendMode = computed(() => import.meta.env.MODE)

const pipelineSteps = [
  {
    title: 'Webhook',
    description: 'Signed pull request events',
  },
  {
    title: 'Review task',
    description: 'Queued through Redis',
  },
  {
    title: 'AI analysis',
    description: 'Static analysis + multi-agent',
  },
  {
    title: 'Validation',
    description: 'Evidence-checked findings',
  },
  {
    title: 'GitHub feedback',
    description: 'Summary and inline comments',
  },
]

const roadmap = [
  {
    title: 'Custom rules',
    description: 'Project-specific review policies',
    phase: '12',
  },
]

async function loadHealth() {
  activeRequest?.abort()
  const request = new AbortController()
  activeRequest = request

  healthState.value = 'loading'
  healthError.value = ''
  latencyMs.value = null

  const startedAt = performance.now()

  try {
    const result = await getHealth(request.signal)
    if (request.signal.aborted) {
      return
    }

    health.value = result
    latencyMs.value = Math.max(1, Math.round(performance.now() - startedAt))

    if (result.status.toUpperCase() === 'UP') {
      healthState.value = 'online'
    } else {
      healthState.value = 'offline'
      healthError.value = `The API reported status "${result.status}".`
    }
  } catch (error) {
    if (request.signal.aborted) {
      return
    }
    healthState.value = 'offline'
    healthError.value = getErrorMessage(error)
  }
}

onMounted(loadHealth)

onBeforeUnmount(() => {
  activeRequest?.abort()
})
</script>

<template>
  <div class="page dashboard-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Workspace</p>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">
          Monitor the CodeSentinel review pipeline and the state of this
          workspace.
        </p>
      </div>

      <el-button
        :icon="Refresh"
        :loading="healthState === 'loading'"
        @click="loadHealth"
      >
        Refresh status
      </el-button>
    </header>

    <section class="metric-grid" aria-label="Workspace status">
      <article class="metric-card">
        <div class="metric-card__top">
          <span class="metric-label">Backend API</span>
          <span
            class="status-pill"
            :class="`status-pill--${healthState}`"
          >
            <span class="status-pill__dot" />
            {{ healthLabel }}
          </span>
        </div>

        <el-skeleton v-if="healthState === 'loading'" :rows="2" animated />

        <template v-else-if="healthState === 'online'">
          <p class="metric-value">{{ health?.status?.toUpperCase() }}</p>
          <p class="metric-caption">
            {{ health?.service }}
            <template v-if="latencyMs !== null"> · {{ latencyMs }} ms</template>
          </p>
        </template>

        <template v-else>
          <p class="metric-value metric-value--danger">Offline</p>
          <p class="metric-caption metric-caption--error">{{ healthError }}</p>
          <el-button size="small" :icon="Refresh" @click="loadHealth">
            Retry
          </el-button>
        </template>
      </article>

      <article class="metric-card">
        <div class="metric-card__top">
          <span class="metric-label">Review history</span>
          <span class="status-pill status-pill--online">Available</span>
        </div>
        <div class="metric-icon metric-icon--indigo">
          <el-icon :size="20"><Document /></el-icon>
        </div>
        <p class="metric-value metric-value--small">Review archive</p>
        <p class="metric-caption">
          Browse AI status and GitHub publication results.
        </p>
      </article>

      <article class="metric-card">
        <div class="metric-card__top">
          <span class="metric-label">Review pipeline</span>
          <span class="status-pill status-pill--online">MVP</span>
        </div>
        <div class="metric-icon metric-icon--teal">
          <el-icon :size="20"><DataLine /></el-icon>
        </div>
        <p class="metric-value metric-value--small">Phases 1–10 complete</p>
        <p class="metric-caption">
          From webhook intake to validated GitHub feedback.
        </p>
      </article>
    </section>

    <section class="panel pipeline-panel">
      <div class="panel-heading">
        <div>
          <h2 class="section-title">Review pipeline</h2>
          <p class="section-subtitle">
            The core review loop runs asynchronously end to end.
          </p>
        </div>
        <span class="soft-badge">MVP pipeline</span>
      </div>

      <ol class="pipeline-steps">
        <li
          v-for="(step, index) in pipelineSteps"
          :key="step.title"
          class="pipeline-step"
        >
          <div class="pipeline-step__top">
            <span class="pipeline-step__index">
              {{ String(index + 1).padStart(2, '0') }}
            </span>
            <el-icon class="pipeline-step__check" :size="17">
              <CircleCheck />
            </el-icon>
          </div>
          <strong>{{ step.title }}</strong>
          <span>{{ step.description }}</span>
        </li>
      </ol>
    </section>

    <div class="content-grid">
      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Next up</h2>
            <p class="section-subtitle">
              Planned work beyond the delivered dashboard scope.
            </p>
          </div>
        </div>

        <ul class="roadmap-list">
          <li v-for="item in roadmap" :key="item.title">
            <div class="roadmap-copy">
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
            </div>
            <span class="roadmap-phase">{{ item.phase }}</span>
            <el-icon class="roadmap-arrow" :size="14">
              <ArrowRight />
            </el-icon>
          </li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Environment</h2>
            <p class="section-subtitle">
              Runtime settings for this frontend build.
            </p>
          </div>
        </div>

        <dl class="meta-list">
          <div>
            <dt>API target</dt>
            <dd>{{ apiTarget }}</dd>
          </div>
          <div>
            <dt>Frontend mode</dt>
            <dd>{{ frontendMode }}</dd>
          </div>
          <div>
            <dt>Dashboard version</dt>
            <dd>v{{ APP_VERSION }}</dd>
          </div>
          <div>
            <dt>History API</dt>
            <dd>Local dashboard BFF</dd>
          </div>
        </dl>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  min-height: 168px;
  padding: 20px;
  background: var(--cs-surface);
  border: 1px solid var(--cs-border);
  border-radius: 14px;
  box-shadow: var(--cs-shadow-sm);
}

.metric-card__top {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.metric-label {
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.metric-value {
  margin: 0;
  color: #0f172a;
  font-size: 28px;
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.15;
}

.metric-value--small {
  margin-top: 12px;
  font-size: 18px;
}

.metric-value--danger {
  color: var(--cs-danger);
}

.metric-caption {
  margin: 8px 0 0;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.55;
}

.metric-caption--error {
  margin-bottom: 14px;
  color: #b91c1c;
}

.metric-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
}

.metric-icon--indigo {
  color: #4338ca;
  background: #eef2ff;
}

.metric-icon--teal {
  color: #0f766e;
  background: #ccfbf1;
}

.status-pill {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px 9px;
  color: #475569;
  font-size: 10.5px;
  font-weight: 650;
  white-space: nowrap;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
}

.status-pill__dot {
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
}

.status-pill--online {
  color: #15803d;
  background: #f0fdf4;
  border-color: #dcfce7;
}

.status-pill--offline {
  color: #b91c1c;
  background: #fef2f2;
  border-color: #fee2e2;
}

.status-pill--loading,
.status-pill--muted {
  color: #64748b;
}

.status-pill--loading .status-pill__dot {
  animation: status-pulse 1.2s ease-in-out infinite;
}

@keyframes status-pulse {
  0%,
  100% {
    opacity: 0.35;
  }

  50% {
    opacity: 1;
  }
}

.pipeline-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.pipeline-step {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 14px;
  background: linear-gradient(180deg, #fbfcfe 0%, #f8fafc 100%);
  border: 1px solid #edf1f7;
  border-radius: 11px;
}

.pipeline-step__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
}

.pipeline-step__index {
  color: #94a3b8;
  font-family: var(--cs-mono);
  font-size: 10px;
  font-weight: 600;
}

.pipeline-step__check {
  color: #10b981;
}

.pipeline-step strong {
  color: #1e293b;
  font-size: 12.5px;
  font-weight: 650;
}

.pipeline-step > span {
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.45;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 16px;
}

.roadmap-list {
  padding: 0;
  margin: 0;
  list-style: none;
}

.roadmap-list li {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 13px 0;
  border-top: 1px solid #f1f5f9;
}

.roadmap-list li:first-child {
  padding-top: 0;
  border-top: none;
}

.roadmap-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.roadmap-copy strong {
  color: #1e293b;
  font-size: 13px;
  font-weight: 600;
}

.roadmap-copy span {
  color: var(--cs-muted);
  font-size: 11.5px;
}

.roadmap-phase {
  flex: none;
  padding: 3px 7px;
  color: #475569;
  font-family: var(--cs-mono);
  font-size: 10px;
  font-weight: 600;
  background: #f1f5f9;
  border-radius: 5px;
}

.roadmap-arrow {
  flex: none;
  color: #cbd5e1;
}

.meta-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin: 0;
}

.meta-list > div {
  display: flex;
  gap: 16px;
  align-items: baseline;
  justify-content: space-between;
  padding: 11px 0;
  border-top: 1px solid #f1f5f9;
}

.meta-list > div:first-child {
  padding-top: 0;
  border-top: none;
}

.meta-list dt {
  flex: none;
  color: #94a3b8;
  font-size: 11.5px;
}

.meta-list dd {
  margin: 0;
  overflow: hidden;
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 11.5px;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1180px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric-card:first-child {
    grid-column: 1 / -1;
  }

  .pipeline-steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .content-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .metric-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .metric-card:first-child {
    grid-column: auto;
  }

  .pipeline-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .pipeline-steps {
    grid-template-columns: minmax(0, 1fr);
  }

  .meta-list > div {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .meta-list dd {
    white-space: normal;
    overflow-wrap: anywhere;
    text-align: left;
  }
}
</style>
