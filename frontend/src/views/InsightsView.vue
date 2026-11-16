<script setup lang="ts">
import {
  Document,
  Refresh,
  WarningFilled,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import CategoryTrendChart from '@/components/insights/CategoryTrendChart.vue'
import DistributionBars from '@/components/insights/DistributionBars.vue'
import InsightsFilterBar from '@/components/insights/InsightsFilterBar.vue'
import ReviewComparisonTable from '@/components/insights/ReviewComparisonTable.vue'
import StatCard from '@/components/insights/StatCard.vue'
import TrendChart from '@/components/insights/TrendChart.vue'
import { useReviewStatistics } from '@/composables/useReviewStatistics'
import { useStatisticsOverview } from '@/composables/useStatisticsOverview'
import type {
  StatisticsFilters,
  StatisticsGranularity,
  StatisticsSort,
  StatisticsSortDirection,
} from '@/types/statistics'
import {
  formatDecimal,
  formatLocalDateTime,
  formatMetricNumber,
  formatRatio,
  formatStatisticsRange,
} from '@/utils/statistics-format'

const DEFAULT_PAGE_SIZE = 20

const appliedFilters = ref<StatisticsFilters>({})
const granularity = ref<StatisticsGranularity>('DAY')
const page = ref(1)
const size = ref(DEFAULT_PAGE_SIZE)
const sort = ref<StatisticsSort>('createdAt')
const direction = ref<StatisticsSortDirection>('desc')

const overviewState = useStatisticsOverview()
const reviewState = useReviewStatistics()

const overview = overviewState.data
const overviewLoading = overviewState.loading
const overviewError = overviewState.error

const reviews = reviewState.data
const reviewsLoading = reviewState.loading
const reviewsError = reviewState.error

const summary = computed(() => overview.value?.summary ?? null)
const dataQuality = computed(() => overview.value?.dataQuality ?? null)
const range = computed(() => overview.value?.range ?? null)

const loadedTrend = computed(() => overview.value?.trend ?? null)
const loadedGranularity = computed(
  () => loadedTrend.value?.granularity ?? null,
)
const loadedGranularityLabel = computed(() => {
  if (loadedGranularity.value === 'WEEK') {
    return 'Weekly'
  }
  if (loadedGranularity.value === 'DAY') {
    return 'Daily'
  }
  return '—'
})
const requestedGranularityLabel = computed(() =>
  granularity.value === 'WEEK' ? 'weekly' : 'daily',
)

const trendGranularityPending = computed(
  () =>
    !!overview.value &&
    overviewLoading.value &&
    loadedGranularity.value !== granularity.value,
)
const trendGranularityFailed = computed(
  () =>
    !!overview.value &&
    !!overviewError.value &&
    !overviewLoading.value &&
    loadedGranularity.value !== granularity.value,
)
const trendGranularityErrorMessage = computed(() => {
  const loaded = (loadedGranularityLabel.value || 'previous').toLowerCase()
  return `Unable to load the ${requestedGranularityLabel.value} trend. The charts are hidden because the last successful snapshot is ${loaded}. Retry to load the selected granularity. ${overviewError.value}`.trim()
})

const initialOverviewLoading = computed(
  () => overviewLoading.value && !overview.value,
)
const initialReviewsLoading = computed(
  () => reviewsLoading.value && !reviews.value,
)
const refreshingOverview = computed(
  () =>
    overviewLoading.value &&
    !!overview.value &&
    !trendGranularityPending.value,
)
const refreshingReviews = computed(
  () => reviewsLoading.value && !!reviews.value,
)

const isEmpty = computed(
  () => !!overview.value && summary.value?.reviewCount === 0,
)

const qualityMessages = computed<string[]>(() => {
  const quality = dataQuality.value
  if (!quality) {
    return []
  }

  const messages: string[] = []

  if (quality.reportsExcludedFromFindingStats > 0) {
    messages.push(
      `${formatMetricNumber(quality.reportsExcludedFromFindingStats)} ${
        quality.reportsExcludedFromFindingStats === 1 ? 'report has' : 'reports have'
      } Finding rows that do not match the declared count. ${
        quality.reportsExcludedFromFindingStats === 1 ? 'It is' : 'They are'
      } excluded from Finding totals, but still counted as reviews.`,
    )
  }

  if (quality.reportsExcludedFromCommentStats > 0) {
    messages.push(
      `${formatMetricNumber(quality.reportsExcludedFromCommentStats)} ${
        quality.reportsExcludedFromCommentStats === 1 ? 'report has' : 'reports have'
      } comment rows that do not match the declared count. ${
        quality.reportsExcludedFromCommentStats === 1 ? 'It is' : 'They are'
      } excluded from inline-comment totals.`,
    )
  }

  if (quality.unknownCategoryFindingCount > 0) {
    messages.push(
      `${formatMetricNumber(quality.unknownCategoryFindingCount)} stored ${
        quality.unknownCategoryFindingCount === 1 ? 'finding has' : 'findings have'
      } an unrecognized category. ${
        quality.unknownCategoryFindingCount === 1 ? 'It remains' : 'They remain'
      } visible in the UNKNOWN bucket.`,
    )
  }

  if (quality.unknownSeverityFindingCount > 0) {
    messages.push(
      `${formatMetricNumber(quality.unknownSeverityFindingCount)} stored ${
        quality.unknownSeverityFindingCount === 1 ? 'finding has' : 'findings have'
      } an unrecognized severity. ${
        quality.unknownSeverityFindingCount === 1 ? 'It remains' : 'They remain'
      } visible in the UNKNOWN bucket.`,
    )
  }

  if (quality.unknownAiStatusReportCount > 0) {
    messages.push(
      `${formatMetricNumber(quality.unknownAiStatusReportCount)} ${
        quality.unknownAiStatusReportCount === 1 ? 'report has' : 'reports have'
      } an unrecognized AI status. The raw value is preserved in the review table.`,
    )
  }

  if (quality.unknownPublishStatusReportCount > 0) {
    messages.push(
      `${formatMetricNumber(quality.unknownPublishStatusReportCount)} ${
        quality.unknownPublishStatusReportCount === 1 ? 'report has' : 'reports have'
      } an unrecognized publish status. The raw value is preserved in the review table.`,
    )
  }

  return messages
})

const hasQualityWarning = computed(() => qualityMessages.value.length > 0)

const totalReviewRows = computed(() => reviews.value?.totalItems ?? 0)

const rangeLabel = computed(() => {
  if (!range.value) {
    return 'Waiting for the first successful response'
  }
  return formatStatisticsRange(
    range.value.createdFrom,
    range.value.createdTo,
  )
})

const reviewCountValue = computed(() =>
  formatMetricNumber(summary.value?.reviewCount),
)
const findingCountValue = computed(() =>
  formatMetricNumber(summary.value?.findingCount),
)
const averageFindingsValue = computed(() =>
  formatDecimal(summary.value?.averageFindingsPerReview),
)
const medianFindingsValue = computed(() =>
  formatDecimal(summary.value?.medianFindingsPerReview),
)
const maxFindingsValue = computed(() =>
  formatMetricNumber(summary.value?.maxFindingsInReview),
)
const highSeverityValue = computed(() =>
  formatMetricNumber(summary.value?.highSeverityFindingCount),
)
const reviewsWithFindingsValue = computed(() =>
  formatMetricNumber(summary.value?.reviewsWithFindings),
)
const inlineCommentValue = computed(() =>
  formatMetricNumber(summary.value?.publishedInlineCommentCount),
)
const reviewsWithCommentsValue = computed(() =>
  formatMetricNumber(summary.value?.reviewsWithInlineComments),
)
const summaryCommentValue = computed(() =>
  formatMetricNumber(summary.value?.summaryCommentIdPresentCount),
)

const findingSampleHint = computed(() => {
  const current = summary.value
  if (!current) {
    return ''
  }
  if (current.findingStatsReviewCount === 0) {
    return 'No finding-consistent reports'
  }
  return `Across ${formatMetricNumber(
    current.findingStatsReviewCount,
  )} finding-consistent reports`
})

const commentSampleHint = computed(() => {
  const current = summary.value
  if (!current) {
    return ''
  }
  if (current.commentStatsReviewCount === 0) {
    return 'No comment-consistent reports'
  }
  return `Across ${formatMetricNumber(
    current.commentStatsReviewCount,
  )} comment-consistent reports`
})

function ratioHint(
  ratio: number | null | undefined,
  denominator: number | null | undefined,
  noun: string,
): string {
  if (!summary.value) {
    return ''
  }
  if (ratio === null || ratio === undefined) {
    return `No ${noun} sample`
  }
  return `${formatRatio(ratio)} of ${formatMetricNumber(denominator)} ${noun}`
}

function overviewQuery() {
  return {
    ...appliedFilters.value,
    granularity: granularity.value,
  }
}

function reviewsQuery() {
  return {
    page: page.value,
    size: size.value,
    sort: sort.value,
    direction: direction.value,
    ...appliedFilters.value,
  }
}

async function loadOverview(): Promise<void> {
  await overviewState.load(overviewQuery())
}

async function loadReviews(): Promise<void> {
  await reviewState.load(reviewsQuery())
}

async function loadAll(): Promise<void> {
  await Promise.allSettled([loadOverview(), loadReviews()])
}

function handleApply(filters: StatisticsFilters): void {
  appliedFilters.value = filters
  page.value = 1
  void loadAll()
}

function handleReset(): void {
  appliedFilters.value = {}
  page.value = 1
  void loadAll()
}

function handleGranularityChange(next: StatisticsGranularity): void {
  if (next === granularity.value) {
    return
  }
  granularity.value = next
  void loadOverview()
}

function handlePageChange(nextPage: number): void {
  if (nextPage === page.value) {
    return
  }
  page.value = nextPage
  void loadReviews()
}

function handleSizeChange(nextSize: number): void {
  if (nextSize === size.value) {
    return
  }
  size.value = nextSize
  page.value = 1
  void loadReviews()
}

function handleSortChange(payload: {
  sort: StatisticsSort
  direction: StatisticsSortDirection
}): void {
  sort.value = payload.sort
  direction.value = payload.direction
  page.value = 1
  void loadReviews()
}

onMounted(() => {
  void loadAll()
})

onBeforeUnmount(() => {
  overviewState.abort()
  reviewState.abort()
})
</script>

<template>
  <div class="page insights-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Insights</p>
        <h1 class="page-title">Review Insights</h1>
        <p class="page-subtitle">
          Activity, severity, and delivery signals from stored review reports.
          Counts describe review history, not a code-quality score.
        </p>
      </div>

      <div class="heading-actions">
        <span
          class="status-pill"
          :class="{ 'status-pill--loading': overviewLoading || reviewsLoading }"
        >
          <span class="status-pill__dot" />
          {{
            overviewLoading || reviewsLoading
              ? 'Loading'
              : `${formatMetricNumber(summary?.reviewCount ?? 0)} ${
                  summary?.reviewCount === 1 ? 'review' : 'reviews'
                }`
          }}
        </span>

        <el-button
          :icon="Refresh"
          :loading="overviewLoading || reviewsLoading"
          @click="loadAll"
        >
          Refresh
        </el-button>
      </div>
    </header>

    <div class="range-strip" data-testid="insights-range">
      <span class="range-strip__item">
        <span class="range-strip__label">Range</span>
        {{ rangeLabel }}
      </span>
      <span v-if="range" class="range-strip__item">
        <span class="range-strip__label">Time basis</span>
        Application local time ({{ range.zoneId }})
      </span>
      <span v-if="overview" class="range-strip__item">
        <span class="range-strip__label">Generated</span>
        {{ formatLocalDateTime(overview.generatedAt) }}
      </span>
    </div>

    <InsightsFilterBar :zone-id="range?.zoneId ?? ''" @apply="handleApply" @reset="handleReset" />

    <section
      v-if="hasQualityWarning"
      class="quality-alert"
      role="alert"
      data-testid="data-quality-warning"
    >
      <span class="quality-alert__icon">
        <el-icon :size="19"><WarningFilled /></el-icon>
      </span>
      <div class="quality-alert__copy">
        <h2 class="section-title">Some stored data is incomplete or unknown</h2>
        <ul class="quality-alert__list">
          <li v-for="message in qualityMessages" :key="message">
            {{ message }}
          </li>
        </ul>
      </div>
    </section>

    <section
      v-if="overviewError && !overview"
      class="panel state-panel state-panel--error"
      role="alert"
      data-testid="overview-error"
    >
      <span class="state-icon state-icon--danger">
        <el-icon :size="22"><WarningFilled /></el-icon>
      </span>
      <div class="state-copy">
        <h2 class="section-title">Unable to load review statistics</h2>
        <p>{{ overviewError }}</p>
      </div>
      <el-button type="primary" :icon="Refresh" @click="loadAll">
        Retry
      </el-button>
    </section>

    <template v-if="overview || !overviewError">
      <div
        v-if="overviewError && overview && !trendGranularityFailed"
        class="inline-warning"
        role="alert"
        data-testid="overview-refresh-error"
      >
        <el-icon><WarningFilled /></el-icon>
        <span>
          The latest statistics refresh failed. Showing the last successful
          response. {{ overviewError }}
        </span>
        <el-button text type="primary" @click="loadAll">Retry</el-button>
      </div>

      <section
        class="summary-section"
        aria-label="Review statistics summary"
        :aria-busy="overviewLoading"
      >
        <div v-if="initialOverviewLoading" class="summary-loading" data-testid="overview-loading">
          <div v-for="index in 10" :key="index" class="summary-skeleton panel">
            <el-skeleton :rows="2" animated />
          </div>
        </div>

        <div v-else class="summary-grid">
          <StatCard label="Review count" :value="reviewCountValue" hint="Stored review reports in scope" :loading="initialOverviewLoading" />

          <StatCard
            label="Finding count"
            :value="findingCountValue"
            :hint="findingSampleHint"
            tone="accent"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Average findings"
            :value="averageFindingsValue"
            hint="Per finding-consistent review"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Median findings"
            :value="medianFindingsValue"
            hint="Finding-consistent reviews, including zero-finding reports"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Max findings"
            :value="maxFindingsValue"
            hint="Largest finding-consistent review"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="High + Critical"
            :value="highSeverityValue"
            :hint="ratioHint(summary?.highSeverityRatio, summary?.findingCount, 'findings')"
            tone="danger"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Reviews with findings"
            :value="reviewsWithFindingsValue"
            :hint="ratioHint(summary?.reviewsWithFindingsRatio, summary?.findingStatsReviewCount, 'finding-consistent reviews')"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Inline comments"
            :value="inlineCommentValue"
            :hint="commentSampleHint"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Reviews with inline comments"
            :value="reviewsWithCommentsValue"
            :hint="ratioHint(summary?.reviewsWithInlineCommentsRatio, summary?.commentStatsReviewCount, 'comment-consistent reviews')"
            :loading="initialOverviewLoading"
          />

          <StatCard
            label="Summary comment IDs"
            :value="summaryCommentValue"
            hint="Presence of a summary comment ID; separate from inline comments"
            :loading="initialOverviewLoading"
          />
        </div>

        <div v-if="refreshingOverview" class="updating-note" role="status">
          <span class="status-pill__dot" />
          Updating statistics…
        </div>

        <div v-if="isEmpty" class="empty-banner" data-testid="insights-empty">
          <span class="empty-banner__icon">
            <el-icon :size="22"><Document /></el-icon>
          </span>
          <div>
            <h2 class="section-title">No stored review reports in this range</h2>
            <p>
              Insights only include reviews that have already been written to
              structured history. Adjust the filters or wait for a new review
              result; no historical data is inferred or backfilled.
            </p>
          </div>
        </div>

        <p class="scope-note">
          <strong>Scope:</strong> Review-level metrics include every stored
          report in the range. Finding metrics exclude reports whose stored
          Finding rows do not match the declared count. Inline-comment metrics
          exclude reports whose stored comment rows do not match; summary
          comment IDs are counted separately and are not inline comments.
        </p>
      </section>

      <div v-if="overview" class="insights-grid">
        <section class="panel distribution-panel" aria-label="Finding category distribution">
          <div class="panel-heading">
            <div>
              <h2 class="section-title">Findings by category</h2>
              <p class="section-subtitle">
                Finding-consistent reports only. Unknown values are preserved.
              </p>
            </div>
            <span class="soft-badge">
              {{ formatMetricNumber(summary?.findingCount) }} findings
            </span>
          </div>
          <DistributionBars
            :items="summary?.categoryCounts ?? []"
            :total="summary?.findingCount ?? null"
            empty-label="No findings in finding-consistent reports."
          />
        </section>

        <section class="panel distribution-panel" aria-label="Finding severity distribution">
          <div class="panel-heading">
            <div>
              <h2 class="section-title">Findings by severity</h2>
              <p class="section-subtitle">
                CRITICAL and HIGH are also summarized as “High + Critical”.
              </p>
            </div>
            <span class="soft-badge">
              {{ formatRatio(summary?.highSeverityRatio) }} high + critical
            </span>
          </div>
          <DistributionBars
            :items="summary?.severityCounts ?? []"
            :total="summary?.findingCount ?? null"
            empty-label="No findings in finding-consistent reports."
          />
        </section>

        <section class="panel distribution-panel" aria-label="Publish status distribution">
          <div class="panel-heading">
            <div>
              <h2 class="section-title">GitHub publish status</h2>
              <p class="section-subtitle">
                One bucket per report. The fixed UNKNOWN bucket keeps values
                outside the known statuses visible.
              </p>
            </div>
          </div>
          <DistributionBars
            :items="summary?.publishStatusCounts ?? []"
            :total="summary?.reviewCount ?? null"
            empty-label="No stored reports in this range."
          />
        </section>

        <section class="panel distribution-panel" aria-label="AI status distribution">
          <div class="panel-heading">
            <div>
              <h2 class="section-title">AI delivery status</h2>
              <p class="section-subtitle">
                DEGRADED reports are included; excluding them would undercount
                stored findings.
              </p>
            </div>
          </div>
          <DistributionBars
            :items="summary?.aiStatusCounts ?? []"
            :total="summary?.reviewCount ?? null"
            empty-label="No stored reports in this range."
          />
        </section>
      </div>

      <section
        v-if="overview"
        class="panel trend-panel"
        aria-label="Review and finding trend"
        :aria-busy="trendGranularityPending"
      >
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Review and finding trend</h2>
            <p class="section-subtitle">
              Review counts include every report; finding counts only include
              finding-consistent reports.
            </p>
          </div>

          <div class="granularity-toggle" role="group" aria-label="Trend granularity">
            <button
              type="button"
              class="granularity-toggle__button"
              :class="{ 'is-active': granularity === 'DAY' }"
              :aria-pressed="granularity === 'DAY'"
              @click="handleGranularityChange('DAY')"
            >
              Daily
            </button>
            <button
              type="button"
              class="granularity-toggle__button"
              :class="{ 'is-active': granularity === 'WEEK' }"
              :aria-pressed="granularity === 'WEEK'"
              @click="handleGranularityChange('WEEK')"
            >
              Weekly
            </button>
          </div>
        </div>

        <div
          v-if="trendGranularityPending"
          class="trend-granularity-state"
          role="status"
          aria-live="polite"
          data-testid="trend-granularity-loading"
        >
          <el-skeleton :rows="4" animated />
          <p class="trend-granularity-state__copy">
            Updating {{ requestedGranularityLabel }} trend…
          </p>
        </div>

        <div
          v-else-if="trendGranularityFailed"
          class="trend-granularity-state trend-granularity-state--error"
          role="alert"
          data-testid="trend-granularity-error"
        >
          <p class="trend-granularity-state__copy">
            {{ trendGranularityErrorMessage }}
          </p>
          <el-button type="primary" :icon="Refresh" @click="loadOverview">
            Retry
          </el-button>
        </div>

        <TrendChart
          v-else
          :points="overview.trend.points"
          :has-data="overview.trend.hasData"
          :granularity="overview.trend.granularity"
        />
      </section>

      <section
        v-if="overview && !trendGranularityPending && !trendGranularityFailed"
        class="panel trend-panel category-trend-panel"
        aria-label="Findings by category trend"
        data-testid="category-trend-panel"
      >
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Findings by category over time</h2>
            <p class="section-subtitle">
              One line per category from finding-consistent reports. Unknown
              values keep their own series. Uses the same Daily/Weekly
              selection as the review trend above.
            </p>
          </div>
          <span class="soft-badge">{{ loadedGranularityLabel }} buckets</span>
        </div>

        <CategoryTrendChart
          :trend="overview.trend"
          :granularity="overview.trend.granularity"
        />
      </section>
    </template>

      <section class="panel comparison-panel" aria-label="Review comparison table" :aria-busy="reviewsLoading">
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Per-review comparison</h2>
            <p class="section-subtitle">
              Declared versus actual stored counts. Rows with incomplete
              history cannot open the review detail page.
            </p>
          </div>
          <span class="soft-badge">
            {{ formatMetricNumber(totalReviewRows) }}
            {{ totalReviewRows === 1 ? 'review' : 'reviews' }}
          </span>
        </div>

        <div v-if="initialReviewsLoading" class="table-loading" role="status" data-testid="reviews-loading">
          <el-skeleton :rows="6" animated />
        </div>

        <div
          v-else-if="reviewsError && !reviews"
          class="state-panel state-panel--error"
          role="alert"
          data-testid="reviews-error"
        >
          <span class="state-icon state-icon--danger">
            <el-icon :size="22"><WarningFilled /></el-icon>
          </span>
          <div class="state-copy">
            <h2 class="section-title">Unable to load the review comparison</h2>
            <p>{{ reviewsError }}</p>
          </div>
          <el-button type="primary" :icon="Refresh" @click="loadReviews">
            Retry
          </el-button>
        </div>

        <template v-else>
          <div
            v-if="reviewsError && reviews"
            class="inline-warning"
            role="alert"
            data-testid="reviews-refresh-error"
          >
            <el-icon><WarningFilled /></el-icon>
            <span>
              The latest comparison refresh failed. Showing the last successful
              page. {{ reviewsError }}
            </span>
            <el-button text type="primary" @click="loadReviews">Retry</el-button>
          </div>

          <div v-if="refreshingReviews" class="updating-note" role="status">
            <span class="status-pill__dot" />
            Updating comparison…
          </div>

          <el-empty
            v-if="totalReviewRows === 0"
            description="No review reports match the current filters"
            data-testid="reviews-empty"
          >
            <p class="empty-copy">
              Review rows appear after a report has been stored. Incomplete
              history stays visible when it exists, so this is a true empty
              result for the selected scope.
            </p>
          </el-empty>

          <ReviewComparisonTable
            v-else
            :items="reviews?.items ?? []"
            :page="page"
            :size="size"
            :total-items="reviews?.totalItems ?? 0"
            :total-pages="reviews?.totalPages ?? 0"
            :sort="sort"
            :direction="direction"
            @page-change="handlePageChange"
            @size-change="handleSizeChange"
            @sort-change="handleSortChange"
          />
        </template>
      </section>

      <section v-if="dataQuality" class="panel quality-panel" aria-label="Statistics data quality">
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Data quality</h2>
            <p class="section-subtitle">
              Counters reported by the backend for the same snapshot. Exclusions
              are explicit; no missing values are inferred.
            </p>
          </div>
          <span
            class="soft-badge"
            :class="{ 'soft-badge--warning': hasQualityWarning }"
          >
            {{ hasQualityWarning ? 'Needs attention' : 'Complete' }}
          </span>
        </div>

        <dl class="quality-grid">
          <div class="quality-item">
            <dt>Total reports</dt>
            <dd>{{ formatMetricNumber(dataQuality.totalReportCount) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Finding-consistent reports</dt>
            <dd>{{ formatMetricNumber(dataQuality.findingsConsistentReportCount) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Comment-consistent reports</dt>
            <dd>{{ formatMetricNumber(dataQuality.commentsConsistentReportCount) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Excluded from Finding stats</dt>
            <dd>{{ formatMetricNumber(dataQuality.reportsExcludedFromFindingStats) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Excluded from comment stats</dt>
            <dd>{{ formatMetricNumber(dataQuality.reportsExcludedFromCommentStats) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Unknown category Findings</dt>
            <dd>{{ formatMetricNumber(dataQuality.unknownCategoryFindingCount) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Unknown severity Findings</dt>
            <dd>{{ formatMetricNumber(dataQuality.unknownSeverityFindingCount) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Unknown AI status reports</dt>
            <dd>{{ formatMetricNumber(dataQuality.unknownAiStatusReportCount) }}</dd>
          </div>
          <div class="quality-item">
            <dt>Unknown publish status reports</dt>
            <dd>{{ formatMetricNumber(dataQuality.unknownPublishStatusReportCount) }}</dd>
          </div>
        </dl>
      </section>
  </div>
</template>

<style scoped>
.insights-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.heading-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
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

.status-pill--loading .status-pill__dot,
.updating-note .status-pill__dot {
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

.range-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  padding: 10px 14px;
  color: #475569;
  font-size: 11.5px;
  background: #fff;
  border: 1px solid var(--cs-border);
  border-radius: 10px;
}

.range-strip__item {
  display: inline-flex;
  gap: 7px;
  align-items: baseline;
}

.range-strip__label {
  color: #94a3b8;
  font-size: 9.5px;
  font-weight: 750;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.quality-alert {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 18px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 13px;
}

.quality-alert__icon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: #b45309;
  background: #fef3c7;
  border-radius: 10px;
}

.quality-alert__copy {
  min-width: 0;
}

.quality-alert__list {
  padding-left: 18px;
  margin: 8px 0 0;
  color: #92400e;
  font-size: 12px;
  line-height: 1.6;
}

.quality-alert__list li + li {
  margin-top: 3px;
}

.state-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  padding: 24px 20px;
}

.state-icon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
}

.state-icon--danger {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fee2e2;
}

.state-copy {
  flex: 1;
  min-width: 220px;
}

.state-copy p {
  margin: 5px 0 0;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.inline-warning {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px 13px;
  color: #92400e;
  font-size: 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 9px;
}

.inline-warning .el-button {
  margin-left: auto;
}

.summary-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 12px;
}

.summary-loading {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 12px;
}

.summary-skeleton {
  min-height: 108px;
}

.updating-note {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  align-self: flex-start;
  padding: 6px 10px;
  color: #4338ca;
  font-size: 11.5px;
  background: #eef2ff;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
}

.empty-banner {
  display: flex;
  gap: 13px;
  align-items: flex-start;
  padding: 16px 18px;
  background: #fff;
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
}

.empty-banner__icon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  color: #6366f1;
  background: #eef2ff;
  border-radius: 10px;
}

.empty-banner p {
  margin: 5px 0 0;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.scope-note {
  margin: 0;
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.6;
}

.scope-note strong {
  color: #334155;
}

.insights-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.distribution-panel,
.trend-panel,
.comparison-panel,
.quality-panel {
  min-width: 0;
}

.trend-panel .panel-heading {
  align-items: center;
}

.trend-granularity-state {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
  padding: 8px 2px;
}

.trend-granularity-state__copy {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.trend-granularity-state--error {
  padding: 12px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 9px;
}

.trend-granularity-state--error .trend-granularity-state__copy {
  color: #92400e;
}

.granularity-toggle {
  display: inline-flex;
  flex: none;
  padding: 3px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 9px;
}

.granularity-toggle__button {
  padding: 5px 11px;
  color: #64748b;
  font-size: 11px;
  font-weight: 650;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 6px;
  transition: color 140ms ease, background 140ms ease;
}

.granularity-toggle__button:hover {
  color: #334155;
}

.granularity-toggle__button.is-active {
  color: #fff;
  background: #4f46e5;
  box-shadow: 0 2px 6px rgb(79 70 229 / 26%);
}

.table-loading {
  padding: 8px 2px;
}

.comparison-panel :deep(.el-button + .el-button) {
  margin-left: 0;
}

.empty-copy {
  max-width: 440px;
  margin: 0 auto;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 16px;
  padding: 0;
  margin: 0;
}

.quality-item {
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 9px;
}

.quality-item dt {
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.quality-item dd {
  margin: 5px 0 0;
  color: #0f172a;
  font-family: var(--cs-mono);
  font-size: 16px;
  font-weight: 650;
}

.soft-badge--warning {
  color: #92400e;
  background: #fffbeb;
  border-color: #fde68a;
}

@media (max-width: 900px) {
  .insights-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .heading-actions {
    width: 100%;
  }

  .range-strip {
    flex-direction: column;
    gap: 6px;
  }

  .trend-panel .panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .granularity-toggle {
    align-self: stretch;
  }

  .granularity-toggle__button {
    flex: 1;
  }

  .quality-alert {
    flex-direction: column;
  }

  .state-panel {
    align-items: flex-start;
  }

  .inline-warning .el-button {
    margin-left: 0;
  }
}
</style>
