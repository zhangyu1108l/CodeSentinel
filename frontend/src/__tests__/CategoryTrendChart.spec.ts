import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CategoryTrendChart from '@/components/insights/CategoryTrendChart.vue'
import type {
  StatisticsGranularity,
  StatisticsTrend,
  StatisticsTrendPoint,
} from '@/types/statistics'

function point(
  bucketStart: string,
  overrides: Partial<StatisticsTrendPoint> = {},
): StatisticsTrendPoint {
  return {
    bucketStart,
    bucketEnd: bucketStart,
    reviewCount: 0,
    findingCount: 0,
    highSeverityFindingCount: 0,
    bugCount: 0,
    securityCount: 0,
    performanceCount: 0,
    qualityCount: 0,
    unknownCategoryCount: 0,
    ...overrides,
  }
}

function trend(
  points: StatisticsTrendPoint[],
  overrides: Partial<StatisticsTrend> = {},
): StatisticsTrend {
  return {
    granularity: 'DAY',
    hasData: points.length > 0,
    points,
    ...overrides,
  }
}

function mountChart(
  data: StatisticsTrend,
  granularity: StatisticsGranularity = data.granularity,
) {
  return mount(CategoryTrendChart, {
    props: { trend: data, granularity },
  })
}

function mockNarrowViewport() {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: query === '(max-width: 640px)',
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>(() => false),
      }) as unknown as MediaQueryList,
  )
}

function tableRowValues(wrapper: ReturnType<typeof mountChart>, index: number) {
  return wrapper
    .get('[data-testid="category-trend-table"]')
    .findAll('tbody tr')
    [index]?.findAll('td')
    .map((cell) => cell.text()) ?? []
}

describe('CategoryTrendChart', () => {
  it('renders five series, five legend items, and accessible chart labels', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01', {
          bugCount: 1,
          securityCount: 2,
          performanceCount: 3,
          qualityCount: 4,
          unknownCategoryCount: 5,
        }),
        point('2026-11-02', {
          bugCount: 2,
          securityCount: 1,
          performanceCount: 0,
          qualityCount: 3,
          unknownCategoryCount: 0,
        }),
      ]),
    )

    await flushPromises()

    const svg = wrapper.get('.category-trend-svg')
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toContain(
      'Daily findings by category trend',
    )
    expect(svg.attributes('aria-label')).toContain('2026-11-01')
    expect(svg.attributes('aria-label')).toContain('2026-11-02')
    expect(wrapper.findAll('.category-trend-line')).toHaveLength(5)
    expect(wrapper.findAll('.category-trend-legend__item')).toHaveLength(5)
    expect(wrapper.findAll('.category-trend-points')).toHaveLength(5)
    expect(wrapper.findAll('.category-trend-points circle')).toHaveLength(10)
  })

  it('maps each category to its own trend field', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01', {
          bugCount: 11,
          securityCount: 22,
          performanceCount: 33,
          qualityCount: 44,
          unknownCategoryCount: 55,
          findingCount: 165,
        }),
      ]),
    )

    await flushPromises()

    expect(tableRowValues(wrapper, 0)).toEqual([
      '11',
      '22',
      '33',
      '44',
      '55',
      '165',
    ])
  })

  it('renders the complete legend with text labels', () => {
    const wrapper = mountChart(trend([point('2026-11-01')]))

    expect(wrapper.get('.category-trend-legend').attributes('aria-label')).toBe(
      'Category trend legend',
    )
    const text = wrapper.get('.category-trend-legend').text()
    for (const label of [
      'Bug',
      'Security',
      'Performance',
      'Quality',
      'Unknown',
    ]) {
      expect(text).toContain(label)
    }
  })

  it('uses daily labels without the weekly note', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01'),
        point('2026-11-02'),
      ]),
    )

    await flushPromises()

    expect(
      wrapper.get('.category-trend-svg').attributes('aria-label'),
    ).toContain('Daily findings by category trend')
    expect(wrapper.text()).not.toContain('ISO-8601')
  })

  it('uses weekly labels and renders the ISO week note', async () => {
    const wrapper = mountChart(
      trend(
        [
          point('2026-10-12', { bucketEnd: '2026-10-18' }),
          point('2026-10-19', { bucketEnd: '2026-10-25' }),
        ],
        { granularity: 'WEEK' },
      ),
    )

    await flushPromises()

    expect(
      wrapper.get('.category-trend-svg').attributes('aria-label'),
    ).toContain('Weekly findings by category trend')
    expect(wrapper.text()).toContain('Weekly buckets follow ISO-8601 weeks')
  })

  it('keeps a zero-only category visible in the legend and table', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01', {
          bugCount: 3,
          securityCount: 0,
          performanceCount: 1,
          qualityCount: 0,
          unknownCategoryCount: 0,
        }),
      ]),
    )

    await flushPromises()

    expect(wrapper.text()).toContain('Security')
    expect(tableRowValues(wrapper, 0)?.[1]).toBe('0')
  })

  it('renders the chart and an explicit note when every category is zero', async () => {
    const wrapper = mountChart(
      trend([point('2026-11-01'), point('2026-11-02')]),
    )

    await flushPromises()

    expect(wrapper.find('.category-trend-svg').exists()).toBe(true)
    expect(wrapper.find('[data-testid="category-trend-empty"]').exists()).toBe(
      false,
    )
    expect(wrapper.get('[data-testid="category-trend-all-zero"]').text()).toBe(
      'All category counts are zero in the selected range.',
    )
    expect(wrapper.findAll('.category-trend-line')).toHaveLength(5)
    expect(tableRowValues(wrapper, 0)).toEqual(['0', '0', '0', '0', '0', '0'])
  })

  it('renders an empty state instead of a chart when there are no points', () => {
    const wrapper = mountChart(trend([]))

    expect(wrapper.find('.category-trend-svg').exists()).toBe(false)
    expect(wrapper.find('[data-testid="category-trend-empty"]').exists()).toBe(
      true,
    )
    expect(wrapper.text()).toContain('No review reports in the selected range.')
    expect(wrapper.find('[data-testid="category-trend-table"]').exists()).toBe(
      false,
    )
  })

  it('renders markers without line paths for a single point', async () => {
    const wrapper = mountChart(
      trend([point('2026-11-01', { bugCount: 2, securityCount: 1 })]),
    )

    await flushPromises()

    expect(wrapper.findAll('.category-trend-line')).toHaveLength(0)
    const circles = wrapper.findAll('.category-trend-points circle')
    expect(circles).toHaveLength(5)
    expect(circles[0]?.attributes('r')).toBe('5')
  })

  it('keeps UNKNOWN as an independent fifth series', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01', {
          bugCount: 1,
          securityCount: 1,
          performanceCount: 1,
          qualityCount: 1,
          unknownCategoryCount: 7,
        }),
        point('2026-11-02', {
          unknownCategoryCount: 2,
        }),
      ]),
    )

    await flushPromises()

    expect(wrapper.findAll('.category-trend-line')).toHaveLength(5)
    expect(wrapper.find('[data-series="UNKNOWN"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Unknown')
    expect(tableRowValues(wrapper, 0)?.[4]).toBe('7')
  })

  it('shows a contract warning and does not draw when a category field is missing', async () => {
    const incomplete = {
      ...point('2026-11-01', { bugCount: 4 }),
      bugCount: undefined,
    } as unknown as StatisticsTrendPoint
    const wrapper = mountChart(trend([incomplete]))

    await flushPromises()

    const warning = wrapper.get(
      '[data-testid="category-trend-contract-warning"]',
    )
    expect(warning.attributes('role')).toBe('alert')
    expect(warning.text()).toContain(
      'missing values are not treated as zero',
    )
    expect(warning.text()).toContain('Bug')
    expect(wrapper.find('.category-trend-svg').exists()).toBe(false)
    expect(tableRowValues(wrapper, 0)?.[0]).toBe('—')
  })

  it('does not treat non-finite category values as zero', async () => {
    const wrapper = mountChart(
      trend([point('2026-11-01', { bugCount: Number.NaN })]),
    )

    await flushPromises()

    expect(
      wrapper.find('[data-testid="category-trend-contract-warning"]').exists(),
    ).toBe(true)
    expect(wrapper.find('.category-trend-svg').exists()).toBe(false)
    expect(tableRowValues(wrapper, 0)?.[0]).toBe('—')
  })

  it('includes the bucket and count in marker titles', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01', { bugCount: 4 }),
        point('2026-11-02', { bugCount: 6 }),
      ]),
    )

    await flushPromises()

    const firstTitle = wrapper
      .findAll('.category-trend-points circle')[0]
      ?.get('title')
      .text()
    expect(firstTitle).toContain('2026-11-01')
    expect(firstTitle).toContain('4')
    expect(firstTitle).toContain('Bug findings')
  })

  it('omits dense markers above the threshold while keeping the table complete', async () => {
    const points = Array.from({ length: 40 }, (_, index) =>
      point(`2026-10-${String((index % 28) + 1).padStart(2, '0')}`, {
        bugCount: index,
      }),
    )
    const wrapper = mountChart(trend(points))

    await flushPromises()

    expect(wrapper.findAll('.category-trend-points circle')).toHaveLength(0)
    expect(wrapper.findAll('.category-trend-line')).toHaveLength(5)
    expect(
      wrapper
        .get('[data-testid="category-trend-table"]')
        .findAll('tbody tr'),
    ).toHaveLength(40)
  })

  it('uses the compact viewBox and at most four x-ticks on narrow screens', async () => {
    mockNarrowViewport()
    const points = Array.from({ length: 30 }, (_, index) =>
      point(`2026-10-${String((index % 28) + 1).padStart(2, '0')}`),
    )
    const wrapper = mountChart(trend(points))

    await flushPromises()

    expect(wrapper.get('.category-trend-svg').attributes('viewBox')).toBe(
      '0 0 360 230',
    )
    expect(wrapper.findAll('.category-trend-axis-label--x')).toHaveLength(4)
  })

  it('renders one table row per bucket with seven columns', async () => {
    const wrapper = mountChart(
      trend([
        point('2026-11-01', {
          bugCount: 1,
          securityCount: 2,
          performanceCount: 3,
          qualityCount: 4,
          unknownCategoryCount: 5,
          findingCount: 15,
        }),
        point('2026-11-02', {
          bugCount: 2,
          securityCount: 3,
          performanceCount: 4,
          qualityCount: 5,
          unknownCategoryCount: 6,
          findingCount: 20,
        }),
      ]),
    )

    await flushPromises()

    const table = wrapper.get('[data-testid="category-trend-table"]')
    expect(table.findAll('thead th')).toHaveLength(7)
    expect(table.findAll('tbody tr')).toHaveLength(2)
    expect(table.findAll('tbody tr')[1]?.text()).toContain('2026-11-02')
    expect(tableRowValues(wrapper, 1)).toEqual([
      '2',
      '3',
      '4',
      '5',
      '6',
      '20',
    ])
  })
})
