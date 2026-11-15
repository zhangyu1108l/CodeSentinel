import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import TrendChart from '@/components/insights/TrendChart.vue'
import type {
  StatisticsGranularity,
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

function mountChart(
  points: StatisticsTrendPoint[],
  hasData = points.length > 0,
  granularity: StatisticsGranularity = 'DAY',
) {
  return mount(TrendChart, {
    props: { points, hasData, granularity },
  })
}

describe('TrendChart', () => {
  it('renders both series, accessible labels, and a data table', async () => {
    const points = [
      point('2026-11-01', { reviewCount: 1, findingCount: 45, highSeverityFindingCount: 18 }),
      point('2026-11-02', { reviewCount: 0, findingCount: 0 }),
      point('2026-11-03', { reviewCount: 2, findingCount: 3, highSeverityFindingCount: 1 }),
    ]
    const wrapper = mountChart(points)

    await flushPromises()

    const svg = wrapper.get('.trend-svg')
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toContain('Daily review and finding trend')
    expect(svg.attributes('aria-label')).toContain('2026-11-01')
    expect(svg.attributes('aria-label')).toContain('2026-11-03')
    expect(wrapper.findAll('.trend-line--review')).toHaveLength(1)
    expect(wrapper.findAll('.trend-line--finding')).toHaveLength(1)
    expect(wrapper.findAll('.trend-point--review circle')).toHaveLength(3)
    expect(wrapper.findAll('.trend-point--finding circle')).toHaveLength(3)
    expect(wrapper.findAll('.trend-axis-label--x')).toHaveLength(3)
    expect(wrapper.text()).toContain('Data table')
    expect(wrapper.text()).toContain('2026-11-01')
    expect(wrapper.text()).toContain('45')
  })

  it('shows the weekly note and weekly accessible label', async () => {
    const wrapper = mountChart(
      [
        point('2026-10-12', { bucketEnd: '2026-10-18', reviewCount: 1 }),
        point('2026-10-19', { bucketEnd: '2026-10-25', reviewCount: 2 }),
      ],
      true,
      'WEEK',
    )

    expect(wrapper.text()).toContain('Weekly buckets follow ISO-8601 weeks')
    expect(wrapper.get('.trend-svg').attributes('aria-label')).toContain(
      'Weekly review and finding trend',
    )
  })

  it('renders an empty state instead of a chart when there is no data', () => {
    const wrapper = mountChart([], false)

    expect(wrapper.find('.trend-svg').exists()).toBe(false)
    expect(wrapper.text()).toContain('No review reports in the selected range.')
    expect(wrapper.find('.trend-empty').exists()).toBe(true)
  })

  it('renders a single point without line paths', async () => {
    const wrapper = mountChart([
      point('2026-11-01', { reviewCount: 6, findingCount: 48 }),
    ])

    await flushPromises()

    expect(wrapper.findAll('.trend-line')).toHaveLength(0)
    expect(wrapper.findAll('.trend-area')).toHaveLength(0)
    const circles = wrapper.findAll('.trend-point circle')
    expect(circles).toHaveLength(2)
    expect(circles[0]?.attributes('r')).toBe('5')
  })

  it('uses compact geometry and at most four x-ticks on narrow screens', async () => {
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

    const points = Array.from({ length: 30 }, (_, index) =>
      point(`2026-10-${String(index + 1).padStart(2, '0')}`),
    )
    const wrapper = mountChart(points)

    await flushPromises()

    expect(wrapper.get('.trend-svg').attributes('viewBox')).toBe('0 0 360 230')
    expect(wrapper.findAll('.trend-axis-label--x').length).toBeLessThanOrEqual(4)
    expect(wrapper.findAll('.trend-axis-label--x')).toHaveLength(4)
  })
})
