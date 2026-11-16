import {
  flushPromises,
  mount,
  RouterLinkStub,
  type VueWrapper,
} from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getStatisticsOverview, getStatisticsReviews } from '@/api'
import StatCard from '@/components/insights/StatCard.vue'
import type {
  StatisticsOverviewResponse,
  StatisticsReviewPage,
  StatisticsSummary,
  StatisticsTrend,
} from '@/types/statistics'
import { ApiError } from '@/utils/api-error'
import InsightsView from '@/views/InsightsView.vue'

vi.mock('@/api', () => ({
  getStatisticsOverview: vi.fn<typeof getStatisticsOverview>(),
  getStatisticsReviews: vi.fn<typeof getStatisticsReviews>(),
}))

const mockedOverview = vi.mocked(getStatisticsOverview)
const mockedReviews = vi.mocked(getStatisticsReviews)

const COMMIT_SHA = '1111111111111111111111111111111111111111'

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function defaultSummary(
  overrides: Partial<StatisticsSummary> = {},
): StatisticsSummary {
  return {
    reviewCount: 6,
    findingStatsReviewCount: 5,
    findingCount: 48,
    averageFindingsPerReview: 9.6,
    medianFindingsPerReview: 1,
    maxFindingsInReview: 45,
    reviewsWithFindings: 4,
    reviewsWithFindingsRatio: 0.8,
    highSeverityFindingCount: 19,
    highSeverityRatio: 0.3958333333333333,
    commentStatsReviewCount: 5,
    publishedInlineCommentCount: 25,
    reviewsWithInlineComments: 1,
    reviewsWithInlineCommentsRatio: 0.2,
    summaryCommentIdPresentCount: 3,
    categoryCounts: [
      { key: 'BUG', count: 12 },
      { key: 'SECURITY', count: 12 },
      { key: 'PERFORMANCE', count: 11 },
      { key: 'QUALITY', count: 12 },
      { key: 'UNKNOWN', count: 1 },
    ],
    severityCounts: [
      { key: 'CRITICAL', count: 10 },
      { key: 'HIGH', count: 9 },
      { key: 'MEDIUM', count: 9 },
      { key: 'LOW', count: 10 },
      { key: 'INFO', count: 9 },
      { key: 'UNKNOWN', count: 1 },
    ],
    publishStatusCounts: [
      { key: 'PUBLISHED', count: 3 },
      { key: 'PARTIAL', count: 2 },
      { key: 'FAILED', count: 1 },
      { key: 'PENDING', count: 0 },
      { key: 'UNKNOWN', count: 0 },
    ],
    aiStatusCounts: [
      { key: 'COMPLETED', count: 4 },
      { key: 'DEGRADED', count: 1 },
      { key: 'UNKNOWN', count: 1 },
    ],
    ...overrides,
  }
}

function defaultTrend(overrides: Partial<StatisticsTrend> = {}): StatisticsTrend {
  return {
    granularity: 'DAY',
    hasData: true,
    points: [
      {
        bucketStart: '2026-11-01',
        bucketEnd: '2026-11-01',
        reviewCount: 1,
        findingCount: 45,
        highSeverityFindingCount: 18,
        bugCount: 12,
        securityCount: 11,
        performanceCount: 11,
        qualityCount: 10,
        unknownCategoryCount: 1,
      },
      {
        bucketStart: '2026-11-02',
        bucketEnd: '2026-11-02',
        reviewCount: 0,
        findingCount: 0,
        highSeverityFindingCount: 0,
        bugCount: 0,
        securityCount: 0,
        performanceCount: 0,
        qualityCount: 0,
        unknownCategoryCount: 0,
      },
    ],
    ...overrides,
  }
}

function makeOverview(
  options: {
    summary?: Partial<StatisticsSummary>
    trend?: Partial<StatisticsTrend>
    dataQuality?: Partial<StatisticsOverviewResponse['dataQuality']>
  } = {},
): StatisticsOverviewResponse {
  const trend = defaultTrend(options.trend)

  return {
    range: {
      createdFrom: '2026-10-15T00:00:00',
      createdTo: '2026-11-13T23:59:59.999999',
      zoneId: 'Asia/Shanghai',
      granularity: trend.granularity,
    },
    generatedAt: '2026-11-13T22:37:56.4357881',
    summary: defaultSummary(options.summary),
    trend,
    dataQuality: {
      totalReportCount: 6,
      findingsConsistentReportCount: 5,
      commentsConsistentReportCount: 5,
      reportsExcludedFromFindingStats: 1,
      reportsExcludedFromCommentStats: 1,
      unknownCategoryFindingCount: 1,
      unknownSeverityFindingCount: 1,
      unknownAiStatusReportCount: 1,
      unknownPublishStatusReportCount: 1,
      ...options.dataQuality,
    },
  }
}

function makeWeekOverview(bugCount = 7): StatisticsOverviewResponse {
  return makeOverview({
    trend: {
      granularity: 'WEEK',
      hasData: true,
      points: [
        {
          bucketStart: '2026-10-12',
          bucketEnd: '2026-10-18',
          reviewCount: 1,
          findingCount: 18,
          highSeverityFindingCount: 0,
          bugCount,
          securityCount: 4,
          performanceCount: 3,
          qualityCount: 2,
          unknownCategoryCount: 1,
        },
      ],
    },
  })
}

function makeReviewPage(
  overrides: Partial<StatisticsReviewPage> = {},
): StatisticsReviewPage {
  const items = overrides.items ?? [
    {
      taskId: 1001,
      owner: 'acme',
      repo: 'sentinel-demo',
      prNumber: 42,
      commitSha: COMMIT_SHA,
      createdAt: '2026-11-01T10:00:00',
      taskStatus: 'COMPLETED',
      aiStatus: 'DEGRADED',
      publishStatus: 'PARTIAL',
      declaredFindingCount: 45,
      actualFindingCount: 45,
      findingsConsistent: true,
      declaredCommentCount: 25,
      actualCommentCount: 25,
      commentsConsistent: true,
      criticalCount: 9,
      highCount: 9,
      highSeverityFindingCount: 18,
      mediumCount: 9,
      lowCount: 9,
      infoCount: 9,
      unknownSeverityCount: 0,
      bugCount: 12,
      securityCount: 11,
      performanceCount: 11,
      qualityCount: 11,
      unknownCategoryCount: 0,
    },
    {
      taskId: 1006,
      owner: 'unknown-owner',
      repo: 'mystery-repo',
      prNumber: 7,
      commitSha: COMMIT_SHA,
      createdAt: '2026-11-02T10:00:00',
      taskStatus: 'COMPLETED',
      aiStatus: 'UNKNOWN',
      publishStatus: 'MYSTERY',
      declaredFindingCount: 1,
      actualFindingCount: 1,
      findingsConsistent: true,
      declaredCommentCount: 0,
      actualCommentCount: 0,
      commentsConsistent: true,
      criticalCount: 0,
      highCount: 0,
      highSeverityFindingCount: 0,
      mediumCount: 0,
      lowCount: 0,
      infoCount: 0,
      unknownSeverityCount: 1,
      bugCount: 0,
      securityCount: 0,
      performanceCount: 0,
      qualityCount: 0,
      unknownCategoryCount: 1,
    },
  ]

  return {
    items,
    page: 1,
    size: 20,
    totalItems: items.length,
    totalPages: items.length === 0 ? 0 : 1,
    hasNext: false,
    ...overrides,
  }
}

async function mountView() {
  const wrapper = mount(InsightsView, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().includes(label))
}

function categoryTableValues(
  wrapper: VueWrapper,
  rowIndex: number,
): string[] {
  return (
    wrapper
      .get('[data-testid="category-trend-table"]')
      .findAll('tbody tr')
      [rowIndex]?.findAll('td')
      .map((cell) => cell.text()) ?? []
  )
}

function cardValue(wrapper: VueWrapper, label: string): string {
  const card = wrapper
    .findAllComponents(StatCard)
    .find((candidate) => candidate.props('label') === label)
  if (!card) {
    throw new Error(`Stat card "${label}" not found`)
  }
  return card.get('.stat-card__value').text()
}

async function emitComponentUpdate(
  wrapper: VueWrapper,
  testId: string,
  componentName: string,
  value: unknown,
) {
  wrapper
    .get(`[data-testid="${testId}"]`)
    .findComponent({ name: componentName })
    .vm.$emit('update:modelValue', value)
  await flushPromises()
}

describe('InsightsView', () => {
  beforeEach(() => {
    mockedOverview.mockReset()
    mockedReviews.mockReset()
  })

  it('loads overview and review comparison data on mount and renders all metrics', async () => {
    mockedOverview.mockResolvedValue(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    expect(mockedOverview).toHaveBeenCalledOnce()
    expect(mockedOverview.mock.calls[0]?.[0]).toEqual({ granularity: 'DAY' })
    expect(mockedOverview.mock.calls[0]?.[1]).toBeInstanceOf(AbortSignal)

    expect(mockedReviews).toHaveBeenCalledOnce()
    expect(mockedReviews.mock.calls[0]?.[0]).toEqual({
      page: 1,
      size: 20,
      sort: 'createdAt',
      direction: 'desc',
    })
    expect(mockedReviews.mock.calls[0]?.[1]).toBeInstanceOf(AbortSignal)

    expect(wrapper.find('[data-testid="overview-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="reviews-loading"]').exists()).toBe(false)

    expect(cardValue(wrapper, 'Review count')).toBe('6')
    expect(cardValue(wrapper, 'Finding count')).toBe('48')
    expect(cardValue(wrapper, 'Average findings')).toBe('9.6')
    expect(cardValue(wrapper, 'Median findings')).toBe('1.0')
    expect(cardValue(wrapper, 'Max findings')).toBe('45')
    expect(cardValue(wrapper, 'High + Critical')).toBe('19')
    expect(cardValue(wrapper, 'Reviews with findings')).toBe('4')
    expect(cardValue(wrapper, 'Inline comments')).toBe('25')
    expect(cardValue(wrapper, 'Reviews with inline comments')).toBe('1')
    expect(cardValue(wrapper, 'Summary comment IDs')).toBe('3')

    const text = wrapper.text()
    expect(text).toContain('39.6% of 48 findings')
    expect(text).toContain('80% of 5 finding-consistent reviews')
    expect(text).toContain('20% of 5 comment-consistent reviews')
    expect(text).toContain('Asia/Shanghai')
    expect(text).toContain('2026-10-15 00:00:00 to 2026-11-13 23:59:59')
    expect(text).toContain('2026-11-13 22:37:56')

    expect(wrapper.find('[data-testid="data-quality-warning"]').exists()).toBe(true)
    expect(text).toContain('excluded from Finding totals')
    expect(text).toContain('excluded from inline-comment totals')

    expect(wrapper.get('[data-bucket="UNKNOWN"]').text()).toContain('Unknown')
    expect(text).toContain('Unknown (UNKNOWN)')
    expect(text).toContain('Unknown (MYSTERY)')
    expect(text).toContain('Severity: 1')

    expect(text).toContain('#1001')
    expect(text).toContain('#1006')
    expect(text).toContain('acme/sentinel-demo')
    expect(wrapper.find('[data-testid="insights-empty"]').exists()).toBe(false)

    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      true,
    )
    expect(wrapper.text()).toContain('Findings by category over time')
    expect(wrapper.findAll('.category-trend-legend__item')).toHaveLength(5)
    expect(wrapper.findAll('.trend-line--review')).toHaveLength(1)
    expect(wrapper.findAll('.trend-line--finding')).toHaveLength(1)
    expect(wrapper.findAll('.granularity-toggle')).toHaveLength(1)
  })

  it('uses category trend fields instead of summary totals', async () => {
    mockedOverview.mockResolvedValue(
      makeOverview({
        summary: {
          categoryCounts: [
            { key: 'BUG', count: 999 },
            { key: 'SECURITY', count: 999 },
            { key: 'PERFORMANCE', count: 999 },
            { key: 'QUALITY', count: 999 },
            { key: 'UNKNOWN', count: 999 },
          ],
        },
      }),
    )
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    expect(categoryTableValues(wrapper, 0)).toEqual([
      '12',
      '11',
      '11',
      '10',
      '1',
      '45',
    ])
  })

  it('shows loading states until both requests settle', async () => {
    const overview = deferred<StatisticsOverviewResponse>()
    const reviews = deferred<StatisticsReviewPage>()
    mockedOverview.mockReturnValueOnce(overview.promise)
    mockedReviews.mockReturnValueOnce(reviews.promise)

    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="overview-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reviews-loading"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Loading')

    overview.resolve(makeOverview())
    reviews.resolve(makeReviewPage())
    await flushPromises()

    expect(wrapper.find('[data-testid="overview-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="reviews-loading"]').exists()).toBe(false)
    expect(cardValue(wrapper, 'Review count')).toBe('6')
    expect(wrapper.text()).toContain('#1001')
  })

  it('renders empty results, placeholders for null metrics, and no fabricated 0%', async () => {
    mockedOverview.mockResolvedValue(
      makeOverview({
        summary: {
          reviewCount: 0,
          findingStatsReviewCount: 0,
          findingCount: 0,
          averageFindingsPerReview: null,
          medianFindingsPerReview: null,
          maxFindingsInReview: null,
          reviewsWithFindings: 0,
          reviewsWithFindingsRatio: null,
          highSeverityFindingCount: 0,
          highSeverityRatio: null,
          commentStatsReviewCount: 0,
          publishedInlineCommentCount: 0,
          reviewsWithInlineComments: 0,
          reviewsWithInlineCommentsRatio: null,
          summaryCommentIdPresentCount: 0,
          categoryCounts: [],
          severityCounts: [],
          publishStatusCounts: [],
          aiStatusCounts: [],
        },
        trend: { hasData: false, points: [] },
        dataQuality: {
          totalReportCount: 0,
          findingsConsistentReportCount: 0,
          commentsConsistentReportCount: 0,
          reportsExcludedFromFindingStats: 0,
          reportsExcludedFromCommentStats: 0,
          unknownCategoryFindingCount: 0,
          unknownSeverityFindingCount: 0,
          unknownAiStatusReportCount: 0,
          unknownPublishStatusReportCount: 0,
        },
      }),
    )
    mockedReviews.mockResolvedValue(
      makeReviewPage({
        items: [],
        totalItems: 0,
        totalPages: 0,
      }),
    )

    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="insights-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reviews-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-testid="category-trend-empty"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('.category-trend-svg').exists()).toBe(false)
    expect(wrapper.text()).toContain('No stored review reports in this range')
    expect(wrapper.text()).toContain('No review reports in the selected range.')
    expect(cardValue(wrapper, 'Average findings')).toBe('—')
    expect(cardValue(wrapper, 'Median findings')).toBe('—')
    expect(cardValue(wrapper, 'Max findings')).toBe('—')
    expect(wrapper.text()).toContain('No findings sample')
    expect(wrapper.text()).toContain('No finding-consistent reviews sample')
    expect(wrapper.text()).not.toContain('0% of 0')
    expect(wrapper.text()).not.toContain('NaN')
    expect(wrapper.find('[data-testid="data-quality-warning"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Complete')
  })

  it('keeps the review table visible when only the overview fails, then retries', async () => {
    mockedOverview.mockRejectedValueOnce(
      new ApiError('Statistics failed', { code: 'internal_error' }),
    )
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="overview-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Unable to load review statistics')
    expect(wrapper.text()).toContain('#1001')

    mockedOverview.mockResolvedValueOnce(makeOverview())

    const retry = wrapper.get('[data-testid="overview-error"] button')
    await retry.trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="overview-error"]').exists()).toBe(false)
    expect(cardValue(wrapper, 'Finding count')).toBe('48')
  })

  it('keeps the summary visible when only the comparison fails, then retries', async () => {
    mockedOverview.mockResolvedValue(makeOverview())
    mockedReviews.mockRejectedValueOnce(
      new ApiError('Comparison failed', { code: 'NETWORK' }),
    )

    const wrapper = await mountView()

    expect(cardValue(wrapper, 'Review count')).toBe('6')
    expect(wrapper.find('[data-testid="reviews-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Comparison failed')

    mockedReviews.mockResolvedValueOnce(makeReviewPage())

    const retry = wrapper.get('[data-testid="reviews-error"] button')
    await retry.trigger('click')
    await flushPromises()

    expect(mockedReviews).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="reviews-error"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('#1001')
  })

  it('applies every filter to both endpoints and resets to page one', async () => {
    mockedOverview.mockResolvedValue(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    await wrapper
      .get('[data-testid="insights-filter-owner"] input')
      .setValue('  acme ')
    await wrapper
      .get('[data-testid="insights-filter-repo"] input')
      .setValue('sentinel')
    await emitComponentUpdate(
      wrapper,
      'insights-filter-pr-number',
      'ElInputNumber',
      42,
    )
    await emitComponentUpdate(
      wrapper,
      'insights-filter-task-status',
      'ElSelect',
      'COMPLETED',
    )
    await emitComponentUpdate(
      wrapper,
      'insights-filter-ai-status',
      'ElSelect',
      'DEGRADED',
    )
    await emitComponentUpdate(
      wrapper,
      'insights-filter-publish-status',
      'ElSelect',
      'PARTIAL',
    )
    await emitComponentUpdate(
      wrapper,
      'insights-filter-created-range',
      'ElDatePicker',
      ['2026-01-01', '2026-02-01'],
    )

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedOverview).toHaveBeenLastCalledWith(
      {
        owner: 'acme',
        repo: 'sentinel',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        aiStatus: 'DEGRADED',
        publishStatus: 'PARTIAL',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59.999999',
        granularity: 'DAY',
      },
      expect.any(AbortSignal),
    )
    expect(mockedReviews).toHaveBeenLastCalledWith(
      {
        page: 1,
        size: 20,
        sort: 'createdAt',
        direction: 'desc',
        owner: 'acme',
        repo: 'sentinel',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        aiStatus: 'DEGRADED',
        publishStatus: 'PARTIAL',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59.999999',
      },
      expect.any(AbortSignal),
    )

    const clearButton = findButton(wrapper, 'Clear filters')
    expect(clearButton).toBeDefined()
    await clearButton?.trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenLastCalledWith(
      { granularity: 'DAY' },
      expect.any(AbortSignal),
    )
    expect(mockedReviews).toHaveBeenLastCalledWith(
      {
        page: 1,
        size: 20,
        sort: 'createdAt',
        direction: 'desc',
      },
      expect.any(AbortSignal),
    )
    expect(
      (
        wrapper.get('[data-testid="insights-filter-owner"] input')
          .element as HTMLInputElement
      ).value,
    ).toBe('')
  })

  it('refetches only the overview when granularity changes', async () => {
    mockedOverview.mockResolvedValue(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    const weekly = findButton(wrapper, 'Weekly')
    expect(weekly).toBeDefined()
    await weekly?.trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenCalledTimes(2)
    expect(mockedOverview).toHaveBeenLastCalledWith(
      { granularity: 'WEEK' },
      expect.any(AbortSignal),
    )
    expect(mockedReviews).toHaveBeenCalledOnce()
    expect(weekly?.attributes('aria-pressed')).toBe('true')

    const daily = findButton(wrapper, 'Daily')
    await daily?.trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenCalledTimes(3)
    expect(mockedOverview).toHaveBeenLastCalledWith(
      { granularity: 'DAY' },
      expect.any(AbortSignal),
    )
  })

  it('hides both trend charts while a new granularity is loading, then shows both with the new snapshot', async () => {
    mockedOverview.mockResolvedValueOnce(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()
    expect(wrapper.find('.trend-svg').exists()).toBe(true)
    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      true,
    )

    const weeklyResponse = deferred<StatisticsOverviewResponse>()
    mockedOverview.mockReturnValueOnce(weeklyResponse.promise)

    const weekly = findButton(wrapper, 'Weekly')
    await weekly?.trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenLastCalledWith(
      { granularity: 'WEEK' },
      expect.any(AbortSignal),
    )
    expect(
      wrapper.find('[data-testid="trend-granularity-loading"]').exists(),
    ).toBe(true)
    expect(wrapper.find('.trend-svg').exists()).toBe(false)
    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      false,
    )

    weeklyResponse.resolve(makeWeekOverview(19))
    await flushPromises()

    expect(
      wrapper.find('[data-testid="trend-granularity-loading"]').exists(),
    ).toBe(false)
    expect(wrapper.get('.trend-svg').attributes('aria-label')).toContain(
      'Weekly review and finding trend',
    )
    expect(
      wrapper.get('.category-trend-svg').attributes('aria-label'),
    ).toContain('Weekly findings by category trend')
    expect(wrapper.text()).toContain('Weekly buckets')
    expect(categoryTableValues(wrapper, 0)?.[0]).toBe('19')
    expect(mockedReviews).toHaveBeenCalledOnce()
  })

  it('hides both trend charts while switching back to daily', async () => {
    mockedOverview.mockResolvedValueOnce(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()
    const weekly = findButton(wrapper, 'Weekly')
    mockedOverview.mockResolvedValueOnce(makeWeekOverview())
    await weekly?.trigger('click')
    await flushPromises()

    expect(wrapper.get('.category-trend-svg').attributes('aria-label')).toContain(
      'Weekly findings by category trend',
    )

    const dailyResponse = deferred<StatisticsOverviewResponse>()
    mockedOverview.mockReturnValueOnce(dailyResponse.promise)

    const daily = findButton(wrapper, 'Daily')
    await daily?.trigger('click')
    await flushPromises()

    expect(
      wrapper.find('[data-testid="trend-granularity-loading"]').exists(),
    ).toBe(true)
    expect(wrapper.find('.trend-svg').exists()).toBe(false)
    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      false,
    )

    dailyResponse.resolve(makeOverview())
    await flushPromises()

    expect(wrapper.get('.trend-svg').attributes('aria-label')).toContain(
      'Daily review and finding trend',
    )
    expect(
      wrapper.get('.category-trend-svg').attributes('aria-label'),
    ).toContain('Daily findings by category trend')
  })

  it('hides stale charts when a granularity switch fails, then retries both through the overview', async () => {
    mockedOverview.mockResolvedValueOnce(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    const weeklyResponse = deferred<StatisticsOverviewResponse>()
    mockedOverview.mockReturnValueOnce(weeklyResponse.promise)

    const weekly = findButton(wrapper, 'Weekly')
    await weekly?.trigger('click')
    await flushPromises()

    weeklyResponse.reject(
      new ApiError('Weekly failed', { code: 'internal_error' }),
    )
    await flushPromises()

    const error = wrapper.get('[data-testid="trend-granularity-error"]')
    expect(error.attributes('role')).toBe('alert')
    expect(error.text()).toContain('last successful snapshot is daily')
    expect(wrapper.find('.trend-svg').exists()).toBe(false)
    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      false,
    )
    expect(
      wrapper.find('[data-testid="overview-refresh-error"]').exists(),
    ).toBe(false)
    expect(mockedReviews).toHaveBeenCalledOnce()

    mockedOverview.mockResolvedValueOnce(makeWeekOverview(23))
    await error.get('button').trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenCalledTimes(3)
    expect(mockedReviews).toHaveBeenCalledOnce()
    expect(
      wrapper.find('[data-testid="trend-granularity-error"]').exists(),
    ).toBe(false)
    expect(wrapper.get('.trend-svg').attributes('aria-label')).toContain(
      'Weekly review and finding trend',
    )
    expect(categoryTableValues(wrapper, 0)?.[0]).toBe('23')
  })

  it('keeps the last snapshot when a same-granularity refresh fails', async () => {
    mockedOverview.mockResolvedValueOnce(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    mockedOverview.mockRejectedValueOnce(
      new ApiError('Refresh failed', { code: 'NETWORK' }),
    )
    const refresh = findButton(wrapper, 'Refresh')
    await refresh?.trigger('click')
    await flushPromises()

    expect(mockedOverview).toHaveBeenCalledTimes(2)
    expect(mockedOverview).toHaveBeenLastCalledWith(
      { granularity: 'DAY' },
      expect.any(AbortSignal),
    )
    expect(
      wrapper.find('[data-testid="overview-refresh-error"]').exists(),
    ).toBe(true)
    expect(
      wrapper.find('[data-testid="trend-granularity-error"]').exists(),
    ).toBe(false)
    expect(wrapper.find('.trend-svg').exists()).toBe(true)
    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      true,
    )
    expect(categoryTableValues(wrapper, 0)?.[0]).toBe('12')
  })

  it('renders both charts when every category count is zero', async () => {
    mockedOverview.mockResolvedValue(
      makeOverview({
        trend: {
          granularity: 'DAY',
          hasData: true,
          points: [
            {
              bucketStart: '2026-11-01',
              bucketEnd: '2026-11-01',
              reviewCount: 1,
              findingCount: 0,
              highSeverityFindingCount: 0,
              bugCount: 0,
              securityCount: 0,
              performanceCount: 0,
              qualityCount: 0,
              unknownCategoryCount: 0,
            },
            {
              bucketStart: '2026-11-02',
              bucketEnd: '2026-11-02',
              reviewCount: 0,
              findingCount: 0,
              highSeverityFindingCount: 0,
              bugCount: 0,
              securityCount: 0,
              performanceCount: 0,
              qualityCount: 0,
              unknownCategoryCount: 0,
            },
          ],
        },
      }),
    )
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="category-trend-panel"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('.category-trend-svg').exists()).toBe(true)
    expect(
      wrapper.find('[data-testid="category-trend-all-zero"]').exists(),
    ).toBe(true)
    expect(wrapper.find('[data-testid="category-trend-empty"]').exists()).toBe(
      false,
    )
    expect(categoryTableValues(wrapper, 0)).toEqual([
      '0',
      '0',
      '0',
      '0',
      '0',
      '0',
    ])
  })

  it('aborts stale granularity requests and ignores their responses', async () => {
    mockedOverview.mockResolvedValueOnce(makeOverview())
    mockedReviews.mockResolvedValue(makeReviewPage())

    const wrapper = await mountView()

    const weeklyResponse = deferred<StatisticsOverviewResponse>()
    const dailyResponse = deferred<StatisticsOverviewResponse>()
    mockedOverview
      .mockReturnValueOnce(weeklyResponse.promise)
      .mockReturnValueOnce(dailyResponse.promise)

    const weekly = findButton(wrapper, 'Weekly')
    await weekly?.trigger('click')
    await flushPromises()

    const weeklySignal = mockedOverview.mock.calls[1]?.[1]
    expect(weeklySignal?.aborted).toBe(false)

    const daily = findButton(wrapper, 'Daily')
    await daily?.trigger('click')
    await flushPromises()

    expect(weeklySignal?.aborted).toBe(true)
    const dailySignal = mockedOverview.mock.calls[2]?.[1]
    expect(dailySignal?.aborted).toBe(false)

    weeklyResponse.resolve(makeWeekOverview(777))
    await flushPromises()

    expect(wrapper.text()).not.toContain('777')

    dailyResponse.resolve(
      makeOverview({
        trend: {
          granularity: 'DAY',
          hasData: true,
          points: [
            {
              bucketStart: '2026-11-05',
              bucketEnd: '2026-11-05',
              reviewCount: 1,
              findingCount: 18,
              highSeverityFindingCount: 0,
              bugCount: 222,
              securityCount: 4,
              performanceCount: 3,
              qualityCount: 2,
              unknownCategoryCount: 1,
            },
          ],
        },
      }),
    )
    await flushPromises()

    expect(categoryTableValues(wrapper, 0)?.[0]).toBe('222')
    expect(wrapper.text()).not.toContain('777')
    expect(wrapper.get('.trend-svg').attributes('aria-label')).toContain(
      'Daily review and finding trend',
    )
    expect(
      wrapper.get('.category-trend-svg').attributes('aria-label'),
    ).toContain('Daily findings by category trend')
  })

  it('refetches only the comparison for page, size, and sort changes', async () => {
    mockedOverview.mockResolvedValue(makeOverview())
    mockedReviews.mockResolvedValue(
      makeReviewPage({
        totalItems: 45,
        totalPages: 3,
        hasNext: true,
      }),
    )

    const wrapper = await mountView()
    const pagination = wrapper.getComponent({ name: 'ElPagination' })

    pagination.vm.$emit('current-change', 2)
    await flushPromises()

    expect(mockedReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2, size: 20 }),
      expect.any(AbortSignal),
    )

    const table = wrapper.getComponent({ name: 'ElTable' })
    table.vm.$emit('sort-change', {
      prop: 'actualFindingCount',
      order: 'ascending',
    })
    await flushPromises()

    expect(mockedReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 1,
        size: 20,
        sort: 'actualFindingCount',
        direction: 'asc',
      }),
      expect.any(AbortSignal),
    )

    pagination.vm.$emit('size-change', 50)
    await flushPromises()

    expect(mockedReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, size: 50 }),
      expect.any(AbortSignal),
    )
    expect(mockedOverview).toHaveBeenCalledOnce()
  })

  it('ignores stale overview and comparison responses after filters change', async () => {
    const firstOverview = deferred<StatisticsOverviewResponse>()
    const secondOverview = deferred<StatisticsOverviewResponse>()
    const firstReviews = deferred<StatisticsReviewPage>()
    const secondReviews = deferred<StatisticsReviewPage>()

    mockedOverview
      .mockReturnValueOnce(firstOverview.promise)
      .mockReturnValueOnce(secondOverview.promise)
    mockedReviews
      .mockReturnValueOnce(firstReviews.promise)
      .mockReturnValueOnce(secondReviews.promise)

    const wrapper = await mountView()

    await wrapper
      .get('[data-testid="insights-filter-owner"] input')
      .setValue('new-owner')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedOverview).toHaveBeenCalledTimes(2)
    expect(mockedReviews).toHaveBeenCalledTimes(2)
    expect(mockedOverview.mock.calls[0]?.[1]?.aborted).toBe(true)
    expect(mockedReviews.mock.calls[0]?.[1]?.aborted).toBe(true)

    secondOverview.resolve(
      makeOverview({ summary: { reviewCount: 9, findingCount: 90 } }),
    )
    secondReviews.resolve(
      makeReviewPage({
        items: [
          {
            ...makeReviewPage().items[0]!,
            taskId: 200,
            owner: 'new-owner',
          },
        ],
        totalItems: 1,
        totalPages: 1,
      }),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('9 reviews')
    expect(wrapper.text()).toContain('#200')
    expect(wrapper.text()).toContain('new-owner/sentinel-demo')

    firstOverview.resolve(
      makeOverview({ summary: { reviewCount: 1, findingCount: 1 } }),
    )
    firstReviews.resolve(
      makeReviewPage({
        items: [
          {
            ...makeReviewPage().items[0]!,
            taskId: 999,
            owner: 'old-owner',
          },
        ],
        totalItems: 1,
        totalPages: 1,
      }),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('9 reviews')
    expect(wrapper.text()).toContain('#200')
    expect(wrapper.text()).not.toContain('#999')
    expect(wrapper.text()).not.toContain('old-owner/sentinel-demo')
  })

  it('aborts both in-flight requests when the view unmounts', async () => {
    const overview = deferred<StatisticsOverviewResponse>()
    const reviews = deferred<StatisticsReviewPage>()
    mockedOverview.mockReturnValueOnce(overview.promise)
    mockedReviews.mockReturnValueOnce(reviews.promise)

    const wrapper = await mountView()

    const overviewSignal = mockedOverview.mock.calls[0]?.[1]
    const reviewsSignal = mockedReviews.mock.calls[0]?.[1]
    expect(overviewSignal?.aborted).toBe(false)
    expect(reviewsSignal?.aborted).toBe(false)

    wrapper.unmount()

    expect(overviewSignal?.aborted).toBe(true)
    expect(reviewsSignal?.aborted).toBe(true)
  })
})
