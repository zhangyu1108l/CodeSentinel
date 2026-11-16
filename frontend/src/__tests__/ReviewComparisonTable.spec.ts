import {
  flushPromises,
  mount,
  RouterLinkStub,
} from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ReviewComparisonTable from '@/components/insights/ReviewComparisonTable.vue'
import type {
  StatisticsReviewItem,
  StatisticsSort,
  StatisticsSortDirection,
} from '@/types/statistics'

const COMMIT_SHA = '1111111111111111111111111111111111111111'

function makeItem(
  overrides: Partial<StatisticsReviewItem> = {},
): StatisticsReviewItem {
  return {
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
    ...overrides,
  }
}

function mountTable(
  items: StatisticsReviewItem[],
  overrides: Partial<{
    page: number
    size: number
    totalItems: number
    totalPages: number
    sort: StatisticsSort
    direction: StatisticsSortDirection
  }> = {},
) {
  return mount(ReviewComparisonTable, {
    props: {
      items,
      page: 1,
      size: 20,
      totalItems: items.length,
      totalPages: 1,
      sort: 'createdAt',
      direction: 'desc',
      ...overrides,
    },
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  })
}

describe('ReviewComparisonTable', () => {
  it('renders counts, statuses, and a detail link for a complete row', async () => {
    const wrapper = mountTable([makeItem()])
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('#1001')
    expect(text).toContain('acme/sentinel-demo')
    expect(text).toContain('PR #42')
    expect(text).toContain('2026-11-01 10:00:00')
    expect(text).toContain('Completed')
    expect(text).toContain('Degraded')
    expect(text).toContain('Partial')
    expect(text).toContain('45 / 45')
    expect(text).toContain('18')
    expect(text).toContain('25 / 25')
    expect(text).toContain('Complete')

    const links = wrapper.findAllComponents(RouterLinkStub)
    expect(links).toHaveLength(1)
    expect(links[0]?.props('to')).toBe('/reviews/1001')
    expect(wrapper.get('.commit-sha').attributes('title')).toBe(COMMIT_SHA)
  })

  it('disables detail links and exposes incomplete data for inconsistent rows', async () => {
    const wrapper = mountTable([
      makeItem({
        taskId: 1003,
        declaredFindingCount: 3,
        actualFindingCount: 2,
        findingsConsistent: false,
      }),
      makeItem({
        taskId: 1005,
        declaredCommentCount: 2,
        actualCommentCount: 1,
        commentsConsistent: false,
      }),
    ])
    await flushPromises()

    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(0)
    expect(wrapper.findAll('.task-id--disabled')).toHaveLength(2)
    expect(wrapper.get('.task-id--disabled').attributes('title')).toContain(
      'incomplete stored history',
    )
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('Inconsistent')
    expect(wrapper.text()).toContain('Incomplete')
  })

  it('preserves unknown status values in the row labels', async () => {
    const wrapper = mountTable([
      makeItem({
        taskId: 1006,
        aiStatus: 'UNKNOWN',
        publishStatus: 'MYSTERY',
        taskStatus: 'PAUSED',
      }),
    ])
    await flushPromises()

    expect(wrapper.text()).toContain('Unknown (UNKNOWN)')
    expect(wrapper.text()).toContain('Unknown (MYSTERY)')
    expect(wrapper.text()).toContain('Unknown (PAUSED)')
    expect(wrapper.text()).not.toContain('null')
  })

  it('emits page changes and page-size changes', async () => {
    const wrapper = mountTable([makeItem()], {
      totalItems: 45,
      totalPages: 3,
    })
    await flushPromises()

    const pagination = wrapper.getComponent({ name: 'ElPagination' })
    pagination.vm.$emit('current-change', 2)
    pagination.vm.$emit('size-change', 50)
    await flushPromises()

    expect(wrapper.emitted('page-change')).toEqual([[2]])
    expect(wrapper.emitted('size-change')).toEqual([[50]])
  })

  it('emits whitelisted sort changes and resets a cleared sort', async () => {
    const wrapper = mountTable([makeItem()], {
      totalItems: 45,
      totalPages: 3,
    })
    await flushPromises()

    const table = wrapper.getComponent({ name: 'ElTable' })
    table.vm.$emit('sort-change', {
      prop: 'actualFindingCount',
      order: 'ascending',
    })
    table.vm.$emit('sort-change', {
      prop: 'highSeverityFindingCount',
      order: 'descending',
    })
    table.vm.$emit('sort-change', {
      prop: 'unknownColumn',
      order: 'ascending',
    })
    table.vm.$emit('sort-change', {
      prop: 'actualCommentCount',
      order: null,
    })
    await flushPromises()

    expect(wrapper.emitted('sort-change')).toEqual([
      [{ sort: 'actualFindingCount', direction: 'asc' }],
      [{ sort: 'highSeverityFindingCount', direction: 'desc' }],
      [{ sort: 'createdAt', direction: 'asc' }],
      [{ sort: 'createdAt', direction: 'desc' }],
    ])
  })

  it('does not render pagination when there are no items', async () => {
    const wrapper = mountTable([], { totalItems: 0, totalPages: 0 })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ElPagination' }).exists()).toBe(false)
  })
})
