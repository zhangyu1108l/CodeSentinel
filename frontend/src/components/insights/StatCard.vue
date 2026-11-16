<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string
    value: string
    hint?: string
    loading?: boolean
    tone?: 'default' | 'accent' | 'danger'
  }>(),
  {
    hint: '',
    loading: false,
    tone: 'default',
  },
)
</script>

<template>
  <article class="stat-card" :class="`stat-card--${props.tone}`">
    <span class="stat-card__label">{{ props.label }}</span>

    <el-skeleton v-if="props.loading" :rows="1" animated />

    <template v-else>
      <p class="stat-card__value">{{ props.value }}</p>
      <p v-if="props.hint" class="stat-card__hint">{{ props.hint }}</p>
    </template>
  </article>
</template>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  min-height: 108px;
  padding: 16px 18px;
  background: var(--cs-surface);
  border: 1px solid var(--cs-border);
  border-radius: 13px;
  box-shadow: var(--cs-shadow-sm);
}

.stat-card--accent {
  background:
    linear-gradient(145deg, rgb(238 242 255 / 78%), rgb(255 255 255 / 100%));
  border-color: #e0e7ff;
}

.stat-card--danger {
  background:
    linear-gradient(145deg, rgb(254 242 242 / 78%), rgb(255 255 255 / 100%));
  border-color: #fee2e2;
}

.stat-card__label {
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.stat-card__value {
  margin: 8px 0 0;
  color: #0f172a;
  font-size: 26px;
  font-weight: 660;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.stat-card--danger .stat-card__value {
  color: #b91c1c;
}

.stat-card__hint {
  margin: 6px 0 0;
  color: var(--cs-muted);
  font-size: 11.5px;
  line-height: 1.45;
}

.stat-card :deep(.el-skeleton) {
  margin-top: 10px;
}
</style>
