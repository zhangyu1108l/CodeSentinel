import {
  flushPromises,
  mount,
  RouterLinkStub,
  type VueWrapper,
} from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getReviewHistory } from '@/api'
import type { ReviewHistoryItem, ReviewHistoryPage } from '@/types/api'
import { ApiError } from '@/utils/api-error'
import ReviewHistoryView from '@/views/ReviewHistoryView.vue'

vi.mock('@/api', () => ({
  getReviewHistory: vi.fn<typeof getReviewHistory>(),
}))

const mockedGetReviewHistory = vi.mocked(getReviewHistory)

const COMMIT_SHA = 'abc123def4567890abc123def4567890abc123de'

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

function makeItem(
  overrides: Partial<ReviewHistoryItem> = {},
): ReviewHistoryItem {
  return {
    taskId: 7,
    owner: 'owner',
    repo: 'repo',
    prNumber: 42,
    commitSha: COMMIT_SHA,
    taskStatus: 'COMPLETED',
    aiStatus: 'DEGRADED',
    publishStatus: 'PARTIAL',
    findingCount: 2,
    publishedCommentCount: 1,
    summaryCommentId: 900,
    publishedAt: '2026-01-02T03:04:05',
    createdAt: '2026-01-02T03:00:00',
    updatedAt: '2026-01-02T03:04:00',
    ...overrides,
  }
}

function makePage(
  items: ReviewHistoryItem[] = [],
  overrides: Partial<ReviewHistoryPage> = {},
): ReviewHistoryPage {
  const totalItems = items.length

  return {
    items,
    page: 1,
    size: 20,
    totalItems,
    totalPages: totalItems === 0 ? 0 : 1,
    hasNext: false,
    ...overrides,
  }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().includes(label))
}

async function mountView() {
  const wrapper = mount(ReviewHistoryView, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  })
  await flushPromises()
  return wrapper
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

describe('ReviewHistoryView', () => {
  beforeEach(() => {
    mockedGetReviewHistory.mockReset()
  })

  it('loads and renders every field from the review history response', async () => {
    mockedGetReviewHistory.mockResolvedValue(makePage([makeItem()]))

    const wrapper = await mountView()

    expect(mockedGetReviewHistory).toHaveBeenCalledOnce()
    expect(mockedGetReviewHistory.mock.calls[0]?.[0]).toEqual({
      page: 1,
      size: 20,
    })
    expect(mockedGetReviewHistory.mock.calls[0]?.[1]).toBeInstanceOf(
      AbortSignal,
    )

    expect(wrapper.find('.history-loading').exists()).toBe(false)
    expect(wrapper.find('.history-table').exists()).toBe(true)

    const text = wrapper.text()
    expect(text).toContain('#7')
    expect(text).toContain('owner/repo')
    expect(wrapper.get('.repo-name').attributes('title')).toBe('owner/repo')
    expect(wrapper.get('.commit-sha').attributes('title')).toBe(COMMIT_SHA)
    expect(text).toContain('PR #42')
    expect(text).toContain(COMMIT_SHA)
    expect(text).toContain('COMPLETED')
    expect(text).toContain('DEGRADED')
    expect(text).toContain('PARTIAL')
    expect(text).toContain('Summary #900')
    expect(text).toContain('2026-01-02 03:04:05')
    expect(text).toContain('2026-01-02 03:00:00')
    expect(text).toContain('2026-01-02 03:04:00')
    expect(text).toContain('1 review')
  })

  it('links every task id to the review detail route', async () => {
    mockedGetReviewHistory.mockResolvedValue(
      makePage([makeItem({ taskId: 7 }), makeItem({ taskId: 8 })]),
    )

    const wrapper = await mountView()

    const links = wrapper.findAllComponents(RouterLinkStub)
    expect(links).toHaveLength(2)
    expect(links[0]?.props('to')).toBe('/reviews/7')
    expect(links[1]?.props('to')).toBe('/reviews/8')
  })

  it('renders placeholders for null summary and published timestamp', async () => {
    mockedGetReviewHistory.mockResolvedValue(
      makePage([
        makeItem({
          summaryCommentId: null,
          publishedAt: null,
        }),
      ]),
    )

    const wrapper = await mountView()

    expect(wrapper.find('.history-error').exists()).toBe(false)
    expect(wrapper.find('.history-table').exists()).toBe(true)
    const text = wrapper.text()
    expect(text).toContain('No summary')
    expect(text).toContain('—')
    expect(text).not.toContain('null')
  })

  it('shows a loading state until the request settles', async () => {
    const pending = deferred<ReviewHistoryPage>()
    mockedGetReviewHistory.mockReturnValueOnce(pending.promise)

    const wrapper = await mountView()

    expect(wrapper.get('.results-panel').attributes('aria-busy')).toBe('true')
    expect(wrapper.find('.history-loading').exists()).toBe(true)
    expect(wrapper.find('.history-table').exists()).toBe(false)

    pending.resolve(makePage([makeItem()]))
    await flushPromises()

    expect(wrapper.get('.results-panel').attributes('aria-busy')).toBe('false')
    expect(wrapper.find('.history-loading').exists()).toBe(false)
    expect(wrapper.find('.history-table').exists()).toBe(true)
  })

  it('renders an empty state when no reviews match', async () => {
    mockedGetReviewHistory.mockResolvedValue(makePage())

    const wrapper = await mountView()

    expect(wrapper.find('.history-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('No reviews match the current filters')
    expect(wrapper.findComponent({ name: 'ElPagination' }).exists()).toBe(false)
    expect(findButton(wrapper, 'Refresh')).toBeDefined()
  })

  it('keeps pagination available when an empty page still has total items', async () => {
    mockedGetReviewHistory
      .mockResolvedValueOnce(
        makePage([], {
          page: 5,
          size: 20,
          totalItems: 45,
          totalPages: 3,
        }),
      )
      .mockResolvedValueOnce(
        makePage([makeItem({ taskId: 21 })], {
          page: 1,
          size: 20,
          totalItems: 45,
          totalPages: 3,
        }),
      )

    const wrapper = await mountView()

    expect(wrapper.find('.history-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('No reviews on this page')
    expect(
      wrapper.getComponent({ name: 'ElPagination' }).props('total'),
    ).toBe(45)

    wrapper
      .getComponent({ name: 'ElPagination' })
      .vm.$emit('current-change', 1)
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      { page: 1, size: 20 },
      expect.any(AbortSignal),
    )
    expect(wrapper.find('.history-table').exists()).toBe(true)
    expect(wrapper.text()).toContain('#21')
  })

  it('renders an API error and retries the request', async () => {
    mockedGetReviewHistory.mockRejectedValueOnce(
      new ApiError('Backend unavailable', { code: 'NETWORK' }),
    )

    const wrapper = await mountView()

    expect(wrapper.find('.history-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('Unable to load review history')
    expect(wrapper.text()).toContain('Backend unavailable')

    mockedGetReviewHistory.mockResolvedValueOnce(makePage([makeItem()]))

    const retryButton = findButton(wrapper, 'Retry')
    expect(retryButton).toBeDefined()
    await retryButton?.trigger('click')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.history-error').exists()).toBe(false)
    expect(wrapper.text()).toContain('#7')
  })

  it('clears a stale filter error on reload and keeps the filters', async () => {
    mockedGetReviewHistory.mockResolvedValue(makePage([makeItem()]))

    const wrapper = await mountView()

    await wrapper
      .get('[data-testid="filter-owner"] input')
      .setValue('acme')
    await emitComponentUpdate(
      wrapper,
      'filter-created-range',
      'ElDatePicker',
      ['2026-02-01T00:00:00', '2026-01-01T00:00:00'],
    )
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain(
      'The created-from time must not be after the created-to time.',
    )

    const refreshButton = findButton(wrapper, 'Refresh')
    expect(refreshButton).toBeDefined()
    await refreshButton?.trigger('click')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain(
      'The created-from time must not be after the created-to time.',
    )
    expect(
      (
        wrapper.get('[data-testid="filter-owner"] input')
          .element as HTMLInputElement
      ).value,
    ).toBe('acme')
  })

  it('requests a new page and a new page size', async () => {
    mockedGetReviewHistory
      .mockResolvedValueOnce(
        makePage([makeItem()], {
          totalItems: 45,
          totalPages: 3,
          hasNext: true,
        }),
      )
      .mockResolvedValueOnce(
        makePage([makeItem({ taskId: 8 })], {
          page: 2,
          size: 20,
          totalItems: 45,
          totalPages: 3,
          hasNext: true,
        }),
      )
      .mockResolvedValueOnce(
        makePage([makeItem({ taskId: 9 })], {
          page: 1,
          size: 50,
          totalItems: 45,
          totalPages: 1,
        }),
      )

    const wrapper = await mountView()
    const pagination = wrapper.getComponent({ name: 'ElPagination' })

    pagination.vm.$emit('current-change', 2)
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      { page: 2, size: 20 },
      expect.any(AbortSignal),
    )
    expect(wrapper.text()).toContain('#8')

    pagination.vm.$emit('size-change', 50)
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      { page: 1, size: 50 },
      expect.any(AbortSignal),
    )
    expect(wrapper.text()).toContain('#9')
  })

  it('applies all filters together and resets the page', async () => {
    mockedGetReviewHistory
      .mockResolvedValueOnce(
        makePage([makeItem()], {
          page: 2,
          size: 20,
          totalItems: 45,
          totalPages: 3,
          hasNext: true,
        }),
      )
      .mockResolvedValueOnce(makePage([makeItem({ taskId: 11 })]))

    const wrapper = await mountView()
    const pagination = wrapper.getComponent({ name: 'ElPagination' })
    pagination.vm.$emit('current-change', 2)
    await flushPromises()

    await wrapper
      .get('[data-testid="filter-owner"] input')
      .setValue('  acme ')
    await wrapper
      .get('[data-testid="filter-repo"] input')
      .setValue('sentinel')
    await emitComponentUpdate(wrapper, 'filter-pr-number', 'ElInputNumber', 42)
    await emitComponentUpdate(
      wrapper,
      'filter-task-status',
      'ElSelect',
      'COMPLETED',
    )
    await emitComponentUpdate(
      wrapper,
      'filter-ai-status',
      'ElSelect',
      'DEGRADED',
    )
    await emitComponentUpdate(
      wrapper,
      'filter-publish-status',
      'ElSelect',
      'PARTIAL',
    )
    await emitComponentUpdate(
      wrapper,
      'filter-created-range',
      'ElDatePicker',
      ['2026-01-01T00:00:00', '2026-02-01T23:59:59'],
    )

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      {
        page: 1,
        size: 20,
        owner: 'acme',
        repo: 'sentinel',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        aiStatus: 'DEGRADED',
        publishStatus: 'PARTIAL',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59',
      },
      expect.any(AbortSignal),
    )
    expect(wrapper.text()).toContain('#11')
  })

  it('clears every filter, keeps the page size, and reloads from page 1', async () => {
    mockedGetReviewHistory
      .mockResolvedValueOnce(
        makePage([makeItem()], {
          totalItems: 100,
          totalPages: 5,
        }),
      )
      .mockResolvedValueOnce(
        makePage([makeItem({ taskId: 8 })], {
          page: 1,
          size: 50,
          totalItems: 100,
          totalPages: 2,
        }),
      )
      .mockResolvedValueOnce(
        makePage([makeItem({ taskId: 9 })], {
          page: 2,
          size: 50,
          totalItems: 100,
          totalPages: 2,
        }),
      )
      .mockResolvedValueOnce(
        makePage([makeItem({ taskId: 10 })], {
          page: 1,
          size: 50,
          totalItems: 1,
          totalPages: 1,
        }),
      )
      .mockResolvedValueOnce(makePage([], { page: 1, size: 50 }))

    const wrapper = await mountView()
    const pagination = wrapper.getComponent({ name: 'ElPagination' })

    pagination.vm.$emit('size-change', 50)
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      { page: 1, size: 50 },
      expect.any(AbortSignal),
    )

    pagination.vm.$emit('current-change', 2)
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      { page: 2, size: 50 },
      expect.any(AbortSignal),
    )
    expect(wrapper.text()).toContain('#9')

    await wrapper
      .get('[data-testid="filter-owner"] input')
      .setValue('acme')
    await emitComponentUpdate(
      wrapper,
      'filter-task-status',
      'ElSelect',
      'FAILED',
    )
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      {
        page: 1,
        size: 50,
        owner: 'acme',
        taskStatus: 'FAILED',
      },
      expect.any(AbortSignal),
    )

    const clearButton = findButton(wrapper, 'Clear filters')
    expect(clearButton).toBeDefined()
    await clearButton?.trigger('click')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenLastCalledWith(
      { page: 1, size: 50 },
      expect.any(AbortSignal),
    )
    expect(
      (
        wrapper.get('[data-testid="filter-owner"] input')
          .element as HTMLInputElement
      ).value,
    ).toBe('')
    expect(wrapper.find('.history-empty').exists()).toBe(true)
  })

  it('ignores a stale response when filters change quickly', async () => {
    const firstRequest = deferred<ReviewHistoryPage>()
    const secondRequest = deferred<ReviewHistoryPage>()
    mockedGetReviewHistory
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)

    const wrapper = await mountView()

    await wrapper
      .get('[data-testid="filter-owner"] input')
      .setValue('new-owner')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenCalledTimes(2)
    expect(mockedGetReviewHistory.mock.calls[0]?.[1]?.aborted).toBe(true)

    secondRequest.resolve(
      makePage([makeItem({ taskId: 21, owner: 'new-owner' })]),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('#21')
    expect(wrapper.text()).toContain('new-owner/repo')

    firstRequest.resolve(makePage([makeItem({ taskId: 99, owner: 'old-owner' })]))
    await flushPromises()

    expect(wrapper.text()).toContain('#21')
    expect(wrapper.text()).not.toContain('#99')
    expect(wrapper.text()).not.toContain('old-owner/repo')
  })

  it('keeps the newer request loading when a stale request settles', async () => {
    const firstRequest = deferred<ReviewHistoryPage>()
    const secondRequest = deferred<ReviewHistoryPage>()
    mockedGetReviewHistory
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)

    const wrapper = await mountView()

    await wrapper
      .get('[data-testid="filter-owner"] input')
      .setValue('new-owner')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mockedGetReviewHistory).toHaveBeenCalledTimes(2)
    expect(mockedGetReviewHistory.mock.calls[0]?.[1]?.aborted).toBe(true)
    expect(wrapper.get('.results-panel').attributes('aria-busy')).toBe('true')
    expect(wrapper.find('.history-loading').exists()).toBe(true)

    firstRequest.resolve(
      makePage([makeItem({ taskId: 99, owner: 'old-owner' })]),
    )
    await flushPromises()

    expect(wrapper.get('.results-panel').attributes('aria-busy')).toBe('true')
    expect(wrapper.find('.history-loading').exists()).toBe(true)
    expect(wrapper.find('.history-table').exists()).toBe(false)

    secondRequest.resolve(
      makePage([makeItem({ taskId: 21, owner: 'new-owner' })]),
    )
    await flushPromises()

    expect(wrapper.get('.results-panel').attributes('aria-busy')).toBe('false')
    expect(wrapper.find('.history-loading').exists()).toBe(false)
    expect(wrapper.find('.history-table').exists()).toBe(true)
    expect(wrapper.text()).toContain('#21')
  })

  it('aborts the in-flight request when the component unmounts', async () => {
    const pending = deferred<ReviewHistoryPage>()
    mockedGetReviewHistory.mockReturnValueOnce(pending.promise)

    const wrapper = await mountView()

    const signal = mockedGetReviewHistory.mock.calls[0]?.[1]
    expect(signal?.aborted).toBe(false)

    wrapper.unmount()

    expect(signal?.aborted).toBe(true)
  })
})
