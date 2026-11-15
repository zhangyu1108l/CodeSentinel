<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type {
  StatisticsGranularity,
  StatisticsTrend,
  StatisticsTrendPoint,
} from '@/types/statistics'
import {
  CATEGORY_TREND_SERIES,
  type CategoryTrendSeries,
} from '@/utils/category-trend'
import {
  formatDateOnly,
  formatMetricNumber,
  formatTrendBucketLabel,
} from '@/utils/statistics-format'
import {
  buildLinePath,
  buildMultiSeriesGeometry,
} from '@/utils/trend-geometry'

const props = defineProps<{
  trend: StatisticsTrend
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

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

const activeGranularity = computed<StatisticsGranularity>(
  () => props.trend.granularity,
)

const granularityMismatch = computed(
  () => props.granularity !== activeGranularity.value,
)

const missingCategorySeries = computed(() =>
  props.trend.points.length === 0
    ? []
    : CATEGORY_TREND_SERIES.filter((series) =>
        props.trend.points.some(
          (point) => !isFiniteNumber(point[series.field]),
        ),
      ).map((series) => series.label),
)

const contractIncomplete = computed(
  () => granularityMismatch.value || missingCategorySeries.value.length > 0,
)

const hasPoints = computed(
  () => props.trend.hasData && props.trend.points.length > 0,
)

const hasBucketsWithoutData = computed(
  () => props.trend.hasData && props.trend.points.length === 0,
)

const emptyDescription = computed(() =>
  hasBucketsWithoutData.value
    ? 'The selected range contains reviews but no trend buckets were returned.'
    : 'No review reports in the selected range.',
)

const seriesValues = computed(() =>
  CATEGORY_TREND_SERIES.map((series) =>
    props.trend.points.map((point) => point[series.field]),
  ),
)

const geometry = computed(() =>
  buildMultiSeriesGeometry(
    contractIncomplete.value ? [] : seriesValues.value,
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

const seriesPaths = computed(() =>
  geometry.value.seriesPoints.map((points) => buildLinePath(points)),
)

const allCategoriesZero = computed(
  () =>
    hasPoints.value &&
    !contractIncomplete.value &&
    CATEGORY_TREND_SERIES.every((series) =>
      props.trend.points.every((point) => point[series.field] === 0),
    ),
)

const markerLimit = computed(() => (compact.value ? 10 : 31))
const showMarkers = computed(
  () =>
    hasPoints.value &&
    (props.trend.points.length === 1 ||
      props.trend.points.length <= markerLimit.value),
)

const granularityWord = computed(() =>
  activeGranularity.value === 'WEEK' ? 'Weekly' : 'Daily',
)

const chartLabel = computed(() => {
  const first = props.trend.points[0]
  const last = props.trend.points[props.trend.points.length - 1]
  if (!first || !last) {
    return `${granularityWord.value} findings by category trend`
  }
  return `${granularityWord.value} findings by category trend from ${formatDateOnly(
    first.bucketStart,
  )} to ${formatDateOnly(last.bucketEnd)}`
})

function bucketTitle(index: number): string {
  const point = props.trend.points[index]
  if (!point) {
    return ''
  }
  return point.bucketStart === point.bucketEnd
    ? formatDateOnly(point.bucketStart)
    : `${formatDateOnly(point.bucketStart)} – ${formatDateOnly(point.bucketEnd)}`
}

function markerTitle(series: CategoryTrendSeries, index: number): string {
  const point: StatisticsTrendPoint | undefined = props.trend.points[index]
  if (!point) {
    return ''
  }
  return `${bucketTitle(index)}: ${formatMetricNumber(
    point[series.field],
  )} ${series.label} findings`
}
</script>

<template>
  <div class="category-trend-chart" data-testid="category-trend-chart">
    <el-empty
      v-if="!hasPoints"
      class="category-trend-empty"
      :description="emptyDescription"
      data-testid="category-trend-empty"
    />

    <template v-else>
      <div
        v-if="contractIncomplete"
        class="category-trend-contract"
        role="alert"
        data-testid="category-trend-contract-warning"
      >
        <p v-if="granularityMismatch">
          The category trend snapshot does not match the selected granularity;
          the chart is hidden.
        </p>
        <p v-if="missingCategorySeries.length > 0">
          The category trend response is incomplete; missing values are not
          treated as zero.
        </p>
        <p v-if="missingCategorySeries.length > 0" class="category-trend-contract__detail">
          Missing fields: {{ missingCategorySeries.join(', ') }}.
        </p>
      </div>

      <template v-if="!contractIncomplete">
        <ul class="category-trend-legend" aria-label="Category trend legend">
          <li
            v-for="series in CATEGORY_TREND_SERIES"
            :key="series.key"
            class="category-trend-legend__item"
          >
            <svg
              class="category-trend-swatch"
              viewBox="0 0 26 8"
              aria-hidden="true"
              focusable="false"
            >
              <line
                x1="1"
                y1="4"
                x2="25"
                y2="4"
                :stroke="series.color"
                :stroke-dasharray="series.dasharray ?? undefined"
                stroke-width="2.2"
                stroke-linecap="round"
              />
              <circle cx="13" cy="4" r="2" :fill="series.color" />
            </svg>
            <span>{{ series.label }}</span>
          </li>
        </ul>

        <svg
          class="category-trend-svg"
          :viewBox="`0 0 ${geometry.width} ${geometry.height}`"
          role="img"
          :aria-label="chartLabel"
          preserveAspectRatio="xMidYMid meet"
        >
          <title>{{ chartLabel }}</title>
          <desc>
            Five line series: Bug, Security, Performance, Quality, and Unknown
            findings. Counts come from finding-consistent reports. Use the data
            table for exact values.
          </desc>

          <line
            v-for="tick in geometry.yTicks"
            :key="`grid-${tick.value}`"
            class="category-trend-grid"
            :x1="geometry.plotLeft"
            :x2="geometry.plotRight"
            :y1="tick.y"
            :y2="tick.y"
          />

          <text
            v-for="tick in geometry.yTicks"
            :key="`y-${tick.value}`"
            class="category-trend-axis-label category-trend-axis-label--y"
            :x="geometry.plotLeft - 8"
            :y="tick.y + 4"
            text-anchor="end"
          >
            {{ formatMetricNumber(Math.round(tick.value)) }}
          </text>

          <template v-if="trend.points.length > 1">
            <path
              v-for="(series, seriesIndex) in CATEGORY_TREND_SERIES"
              :key="`line-${series.key}`"
              class="category-trend-line"
              :data-series="series.key"
              :d="seriesPaths[seriesIndex] ?? ''"
              :stroke="series.color"
              :stroke-dasharray="series.dasharray ?? undefined"
            />
          </template>

          <template v-if="showMarkers">
            <g
              v-for="(series, seriesIndex) in CATEGORY_TREND_SERIES"
              :key="`markers-${series.key}`"
              class="category-trend-points"
              :data-series="series.key"
            >
              <circle
                v-for="point in geometry.seriesPoints[seriesIndex] ?? []"
                :key="`${series.key}-${point.index}`"
                :cx="point.x"
                :cy="point.y"
                :r="trend.points.length === 1 ? 5 : 2.6"
                :fill="series.color"
              >
                <title>{{ markerTitle(series, point.index) }}</title>
              </circle>
            </g>
          </template>

          <text
            v-for="tick in geometry.xTicks"
            :key="`x-${tick.index}`"
            class="category-trend-axis-label category-trend-axis-label--x"
            :x="tick.x"
            :y="geometry.baselineY + 20"
            text-anchor="middle"
          >
            {{ formatTrendBucketLabel(trend.points[tick.index]?.bucketStart ?? '') }}
          </text>
        </svg>

        <p v-if="activeGranularity === 'WEEK'" class="category-trend-note">
          Weekly buckets follow ISO-8601 weeks (Monday to Sunday). The first and
          last buckets may extend beyond the selected range.
        </p>

        <p
          v-if="allCategoriesZero"
          class="category-trend-note category-trend-note--zero"
          data-testid="category-trend-all-zero"
        >
          All category counts are zero in the selected range.
        </p>
      </template>

      <details class="category-trend-table" data-testid="category-trend-table">
        <summary>Data table</summary>
        <div class="category-trend-table__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Bucket</th>
                <th
                  v-for="series in CATEGORY_TREND_SERIES"
                  :key="`head-${series.key}`"
                  scope="col"
                >
                  {{ series.label }}
                </th>
                <th scope="col">Findings</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(point, index) in props.trend.points"
                :key="point.bucketStart"
              >
                <th scope="row">{{ bucketTitle(index) }}</th>
                <td
                  v-for="series in CATEGORY_TREND_SERIES"
                  :key="`${series.key}-value`"
                >
                  {{ formatMetricNumber(point[series.field]) }}
                </td>
                <td>{{ formatMetricNumber(point.findingCount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </template>
  </div>
</template>

<style scoped>
.category-trend-chart {
  min-width: 0;
}

.category-trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  padding: 0;
  margin: 0 0 10px;
  list-style: none;
}

.category-trend-legend__item {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  color: #64748b;
  font-size: 11.5px;
  font-weight: 550;
}

.category-trend-swatch {
  flex: none;
  width: 24px;
  height: 8px;
  overflow: visible;
}

.category-trend-svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

.category-trend-grid {
  stroke: #eef2f7;
  stroke-width: 1;
}

.category-trend-axis-label {
  fill: #94a3b8;
  font-family: var(--cs-mono);
  font-size: 10px;
}

.category-trend-axis-label--x {
  font-size: 9.5px;
}

.category-trend-line {
  fill: none;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.category-trend-points circle {
  stroke: #fff;
  stroke-width: 1.2;
}

.category-trend-note {
  margin: 8px 0 0;
  color: var(--cs-muted);
  font-size: 11px;
  line-height: 1.5;
}

.category-trend-note--zero {
  color: #92400e;
}

.category-trend-contract {
  padding: 12px 14px;
  color: #92400e;
  font-size: 12px;
  line-height: 1.6;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 9px;
}

.category-trend-contract p {
  margin: 0;
}

.category-trend-contract p + p {
  margin-top: 5px;
}

.category-trend-contract__detail {
  color: #b45309;
  font-size: 11.5px;
}

.category-trend-table {
  margin-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.category-trend-table summary {
  padding-top: 12px;
  color: #4338ca;
  font-size: 11.5px;
  font-weight: 650;
  cursor: pointer;
}

.category-trend-table__scroll {
  margin-top: 10px;
  overflow-x: auto;
}

.category-trend-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.category-trend-table th,
.category-trend-table td {
  padding: 7px 10px;
  color: #475569;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid #f1f5f9;
}

.category-trend-table thead th {
  color: #64748b;
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: #f8fafc;
}

.category-trend-table tbody th {
  color: #334155;
  font-weight: 600;
}

.category-trend-empty {
  padding: 18px 0;
}

@media (max-width: 640px) {
  .category-trend-axis-label--x {
    font-size: 9px;
  }

  .category-trend-table table {
    font-size: 11px;
  }
}
</style>
