<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type {
  StatisticsTrendPoint,
  StatisticsGranularity,
} from '@/types/statistics'
import {
  formatDateOnly,
  formatMetricNumber,
  formatTrendBucketLabel,
} from '@/utils/statistics-format'
import {
  buildAreaPath,
  buildLinePath,
  buildTrendGeometry,
} from '@/utils/trend-geometry'

const props = defineProps<{
  points: StatisticsTrendPoint[]
  hasData: boolean
  granularity: StatisticsGranularity
}>()

const compact = ref(false)
let mediaQuery: MediaQueryList | undefined

function syncViewport() {
  if (mediaQuery) {
    compact.value = mediaQuery.matches
  }
}

onMounted(() => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return
  }
  mediaQuery = window.matchMedia('(max-width: 640px)')
  compact.value = mediaQuery.matches
  mediaQuery.addEventListener('change', syncViewport)
})

onBeforeUnmount(() => {
  mediaQuery?.removeEventListener('change', syncViewport)
})

const hasPoints = computed(
  () => props.hasData && props.points.length > 0,
)

const geometry = computed(() =>
  buildTrendGeometry(
    props.points.map((point) => point.reviewCount),
    props.points.map((point) => point.findingCount),
    compact.value
      ? {
          width: 360,
          height: 230,
          paddingLeft: 34,
          paddingRight: 12,
          paddingTop: 16,
          paddingBottom: 32,
          maxXTicks: 4,
        }
      : {},
  ),
)

const reviewPath = computed(() => buildLinePath(geometry.value.reviewPoints))
const findingPath = computed(() => buildLinePath(geometry.value.findingPoints))
const reviewArea = computed(() =>
  buildAreaPath(geometry.value.reviewPoints, geometry.value.baselineY),
)
const findingArea = computed(() =>
  buildAreaPath(geometry.value.findingPoints, geometry.value.baselineY),
)

const chartLabel = computed(() => {
  const first = props.points[0]
  const last = props.points[props.points.length - 1]
  if (!first || !last) {
    return 'Review and finding trend'
  }
  const cadence = props.granularity === 'WEEK' ? 'Weekly' : 'Daily'
  return `${cadence} review and finding trend from ${formatDateOnly(
    first.bucketStart,
  )} to ${formatDateOnly(last.bucketEnd)}`
})

function bucketTitle(index: number): string {
  const point = props.points[index]
  if (!point) {
    return ''
  }
  return point.bucketStart === point.bucketEnd
    ? formatDateOnly(point.bucketStart)
    : `${formatDateOnly(point.bucketStart)} – ${formatDateOnly(point.bucketEnd)}`
}
</script>

<template>
  <div class="trend-chart">
    <el-empty
      v-if="!hasPoints"
      class="trend-empty"
      description="No review reports in the selected range."
    />

    <template v-else>
      <div class="trend-legend" aria-hidden="true">
        <span class="trend-legend__item">
          <span class="trend-swatch trend-swatch--review" />
          Review reports
        </span>
        <span class="trend-legend__item">
          <span class="trend-swatch trend-swatch--finding" />
          Findings
        </span>
      </div>

      <svg
        class="trend-svg"
        :viewBox="`0 0 ${geometry.width} ${geometry.height}`"
        role="img"
        :aria-label="chartLabel"
        preserveAspectRatio="xMidYMid meet"
      >
        <title>{{ chartLabel }}</title>
        <desc>
          Two line series. Review reports count every stored report in each
          bucket; findings only count reports whose stored finding rows match
          their declared finding count.
        </desc>

        <line
          v-for="tick in geometry.yTicks"
          :key="`grid-${tick.value}`"
          class="trend-grid"
          :x1="geometry.plotLeft"
          :x2="geometry.plotRight"
          :y1="tick.y"
          :y2="tick.y"
        />

        <text
          v-for="tick in geometry.yTicks"
          :key="`y-${tick.value}`"
          class="trend-axis-label trend-axis-label--y"
          :x="geometry.plotLeft - 8"
          :y="tick.y + 4"
          text-anchor="end"
        >
          {{ formatMetricNumber(Math.round(tick.value)) }}
        </text>

        <path
          v-if="points.length > 1"
          class="trend-area trend-area--finding"
          :d="findingArea"
        />
        <path
          v-if="points.length > 1"
          class="trend-area trend-area--review"
          :d="reviewArea"
        />

        <path
          v-if="points.length > 1"
          class="trend-line trend-line--finding"
          :d="findingPath"
        />
        <path
          v-if="points.length > 1"
          class="trend-line trend-line--review"
          :d="reviewPath"
        />

        <g
          v-for="point in geometry.reviewPoints"
          :key="`review-${point.index}`"
          class="trend-point trend-point--review"
        >
          <circle
            :cx="point.x"
            :cy="point.y"
            :r="points.length === 1 ? 5 : 2.6"
          >
            <title>
              {{ bucketTitle(point.index) }}: {{ points[point.index]?.reviewCount ?? 0 }} review reports
            </title>
          </circle>
        </g>

        <g
          v-for="point in geometry.findingPoints"
          :key="`finding-${point.index}`"
          class="trend-point trend-point--finding"
        >
          <circle
            :cx="point.x"
            :cy="point.y"
            :r="points.length === 1 ? 5 : 2.6"
          >
            <title>
              {{ bucketTitle(point.index) }}: {{ points[point.index]?.findingCount ?? 0 }} findings
            </title>
          </circle>
        </g>

        <text
          v-for="tick in geometry.xTicks"
          :key="`x-${tick.index}`"
          class="trend-axis-label trend-axis-label--x"
          :x="tick.x"
          :y="geometry.baselineY + 20"
          text-anchor="middle"
        >
          {{ formatTrendBucketLabel(points[tick.index]?.bucketStart ?? '') }}
        </text>
      </svg>

      <p v-if="granularity === 'WEEK'" class="trend-note">
        Weekly buckets follow ISO-8601 weeks (Monday to Sunday). The first and
        last buckets may extend beyond the selected range.
      </p>

      <details class="trend-table">
        <summary>Data table</summary>
        <div class="trend-table__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Bucket</th>
                <th scope="col">Reviews</th>
                <th scope="col">Findings</th>
                <th scope="col">High + Critical</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(point, index) in points" :key="point.bucketStart">
                <th scope="row">{{ bucketTitle(index) }}</th>
                <td>{{ formatMetricNumber(point.reviewCount) }}</td>
                <td>{{ formatMetricNumber(point.findingCount) }}</td>
                <td>{{ formatMetricNumber(point.highSeverityFindingCount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </template>
  </div>
</template>

<style scoped>
.trend-chart {
  min-width: 0;
}

.trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-bottom: 8px;
}

.trend-legend__item {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  color: #64748b;
  font-size: 11.5px;
  font-weight: 550;
}

.trend-swatch {
  width: 16px;
  height: 3px;
  border-radius: 999px;
}

.trend-swatch--review {
  background: #4f46e5;
}

.trend-swatch--finding {
  background: #d97706;
}

.trend-svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

.trend-grid {
  stroke: #eef2f7;
  stroke-width: 1;
}

.trend-axis-label {
  fill: #94a3b8;
  font-family: var(--cs-mono);
  font-size: 10px;
}

.trend-axis-label--x {
  font-size: 9.5px;
}

.trend-line {
  fill: none;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-line--review {
  stroke: #4f46e5;
}

.trend-line--finding {
  stroke: #d97706;
}

.trend-area {
  stroke: none;
}

.trend-area--review {
  fill: rgb(79 70 229 / 8%);
}

.trend-area--finding {
  fill: rgb(217 119 6 / 6%);
}

.trend-point circle {
  stroke: #fff;
  stroke-width: 1.2;
}

.trend-point--review circle {
  fill: #4f46e5;
}

.trend-point--finding circle {
  fill: #d97706;
}

.trend-note {
  margin: 8px 0 0;
  color: var(--cs-muted);
  font-size: 11px;
  line-height: 1.5;
}

.trend-table {
  margin-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.trend-table summary {
  padding-top: 12px;
  color: #4338ca;
  font-size: 11.5px;
  font-weight: 650;
  cursor: pointer;
}

.trend-table__scroll {
  margin-top: 10px;
  overflow-x: auto;
}

.trend-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.trend-table th,
.trend-table td {
  padding: 7px 10px;
  color: #475569;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid #f1f5f9;
}

.trend-table thead th {
  color: #64748b;
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: #f8fafc;
}

.trend-table tbody th {
  color: #334155;
  font-weight: 600;
}

.trend-empty {
  padding: 18px 0;
}

@media (max-width: 640px) {
  .trend-axis-label--x {
    font-size: 9px;
  }

  .trend-table table {
    font-size: 11px;
  }
}
</style>
