<script setup lang="ts">
import { computed } from 'vue'

import type { StatisticsCount } from '@/types/statistics'
import {
  formatBucketLabel,
  formatMetricNumber,
  formatRatio,
} from '@/utils/statistics-format'

const props = withDefaults(
  defineProps<{
    items: StatisticsCount[]
    total?: number | null
    emptyLabel?: string
  }>(),
  {
    total: null,
    emptyLabel: 'No data in this scope.',
  },
)

const effectiveTotal = computed(() => {
  if (props.total !== null && props.total !== undefined) {
    return props.total
  }
  return props.items.reduce((sum, item) => sum + item.count, 0)
})

function widthFor(count: number): string {
  if (effectiveTotal.value <= 0) {
    return '0%'
  }
  const width = Math.min(100, (count / effectiveTotal.value) * 100)
  return `${width.toFixed(2)}%`
}

function ratioLabel(count: number): string {
  if (effectiveTotal.value <= 0) {
    return ''
  }
  return formatRatio(count / effectiveTotal.value)
}
</script>

<template>
  <div class="distribution-bars">
    <p v-if="props.items.length === 0 || effectiveTotal <= 0" class="distribution-empty">
      {{ props.emptyLabel }}
    </p>

    <ul v-else class="distribution-list">
      <li
        v-for="item in props.items"
        :key="item.key"
        class="distribution-row"
        :class="{ 'distribution-row--unknown': item.key.toUpperCase() === 'UNKNOWN' }"
        :data-bucket="item.key"
      >
        <div class="distribution-row__head">
          <span class="distribution-label" :title="item.key">
            {{ formatBucketLabel(item.key) }}
          </span>
          <span class="distribution-value">
            {{ formatMetricNumber(item.count) }}
            <template v-if="ratioLabel(item.count)">
              · {{ ratioLabel(item.count) }}
            </template>
          </span>
        </div>

        <div
          class="distribution-track"
          role="img"
          :aria-label="`${formatBucketLabel(item.key)}: ${item.count} of ${effectiveTotal}`"
        >
          <span
            class="distribution-fill"
            :style="{ width: widthFor(item.count) }"
          />
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.distribution-bars {
  min-height: 120px;
}

.distribution-empty {
  padding: 18px 0;
  margin: 0;
  color: var(--cs-muted);
  font-size: 12.5px;
}

.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.distribution-row__head {
  display: flex;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 5px;
}

.distribution-label {
  overflow: hidden;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.distribution-value {
  flex: none;
  color: #64748b;
  font-family: var(--cs-mono);
  font-size: 10.5px;
}

.distribution-track {
  height: 7px;
  overflow: hidden;
  background: #f1f5f9;
  border-radius: 999px;
}

.distribution-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  border-radius: inherit;
  transition: width 180ms ease;
}

.distribution-row--unknown .distribution-label {
  color: #64748b;
}

.distribution-row--unknown .distribution-fill {
  background: #cbd5e1;
}
</style>
