import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { getHealth, getReviewComments, getReviewDetail, getReviewFindings, getReviewHistory } from '@/api'
import App from '@/App.vue'
import { createAppRouter } from '@/router'
import type {
  ReviewCommentPage,
  ReviewDetailReport,
  ReviewFindingPage,
} from '@/types/api'

vi.mock('@/api', () => ({
  getHealth: vi.fn<typeof getHealth>(),
  getReviewComments: vi.fn<typeof getReviewComments>(),
  getReviewDetail: vi.fn<typeof getReviewDetail>(),
  getReviewFindings: vi.fn<typeof getReviewFindings>(),
  getReviewHistory: vi.fn<typeof getReviewHistory>(),
}))

const mockedGetHealth = vi.mocked(getHealth)
const mockedGetReviewHistory = vi.mocked(getReviewHistory)
const mockedGetReviewDetail = vi.mocked(getReviewDetail)
const mockedGetReviewFindings = vi.mocked(getReviewFindings)
const mockedGetReviewComments = vi.mocked(getReviewComments)

function emptyFindingPage(): ReviewFindingPage {
  return {
    items: [],
    page: 1,
    size: 20,
    totalItems: 0,
    totalPages: 0,
    hasNext: false,
  }
}

function emptyCommentPage(): ReviewCommentPage {
  return {
    items: [],
    page: 1,
    size: 20,
    totalItems: 0,
    totalPages: 0,
    hasNext: false,
  }
}

function reviewReport(taskId: number): ReviewDetailReport {
  return {
    taskId,
    owner: 'owner',
    repo: 'repo',
    prNumber: 42,
    commitSha: 'abc123',
    taskStatus: 'COMPLETED',
    aiStatus: 'DEGRADED',
    publishStatus: 'PARTIAL',
    findingCount: 0,
    publishedCommentCount: 0,
    summaryCommentId: null,
    publishedAt: null,
    createdAt: '2026-01-02T03:00:00',
    updatedAt: '2026-01-02T03:04:00',
  }
}

async function mountApp(path: string) {
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()

  const wrapper = mount(App, {
    global: {
      plugins: [router],
    },
  })

  await flushPromises()
  return wrapper
}

describe('App integration', () => {
  beforeEach(() => {
    mockedGetHealth.mockReset()
    mockedGetHealth.mockResolvedValue({
      status: 'UP',
      service: 'codesentinel',
    })
    mockedGetReviewHistory.mockReset()
    mockedGetReviewHistory.mockResolvedValue({
      items: [],
      page: 1,
      size: 20,
      totalItems: 0,
      totalPages: 0,
      hasNext: false,
    })
    mockedGetReviewDetail.mockReset()
    mockedGetReviewDetail.mockImplementation(
      async (taskId: number) => reviewReport(taskId),
    )
    mockedGetReviewFindings.mockReset()
    mockedGetReviewFindings.mockResolvedValue(emptyFindingPage())
    mockedGetReviewComments.mockReset()
    mockedGetReviewComments.mockResolvedValue(emptyCommentPage())
  })

  it('renders the dashboard inside the application shell', async () => {
    const wrapper = await mountApp('/')

    expect(wrapper.find('.app-sidebar').exists()).toBe(true)
    expect(wrapper.find('.app-header').exists()).toBe(true)
    expect(wrapper.find('h1').text()).toBe('Dashboard')
    expect(wrapper.text()).toContain('Operational')
  })

  it('renders the review history route with its empty state', async () => {
    const wrapper = await mountApp('/reviews')

    expect(wrapper.find('h1').text()).toBe('Review History')
    expect(wrapper.text()).toContain('No reviews match the current filters')
    expect(wrapper.get('.el-menu-item.is-active').text()).toContain(
      'Review History',
    )
  })

  it('keeps Review History highlighted on the review detail route', async () => {
    const wrapper = await mountApp('/reviews/7')

    expect(mockedGetReviewDetail).toHaveBeenCalledWith(
      7,
      expect.any(AbortSignal),
    )
    expect(wrapper.find('h1').text()).toBe('Review #7')
    expect(wrapper.get('.el-menu-item.is-active').text()).toContain(
      'Review History',
    )
  })

  it('renders the not-found route without highlighting a sidebar item', async () => {
    const wrapper = await mountApp('/missing-page')

    expect(wrapper.find('h1').text()).toBe('Page not found')
    expect(wrapper.findAll('.el-menu-item.is-active')).toHaveLength(0)
  })

  it('does not highlight Review History for a missing subpath', async () => {
    const wrapper = await mountApp('/reviews/missing-entry')

    expect(wrapper.find('h1').text()).toBe('Page not found')
    expect(wrapper.findAll('.el-menu-item.is-active')).toHaveLength(0)
  })
})
