import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import {
  getReviewComments,
  getReviewDetail,
  getReviewFindings,
} from '@/api'
import { createAppRouter } from '@/router'
import type {
  FindingCategory,
  FindingSeverity,
  ReviewComment,
  ReviewCommentPage,
  ReviewDetailReport,
  ReviewFinding,
  ReviewFindingPage,
} from '@/types/api'
import { ApiError } from '@/utils/api-error'
import ReviewDetailView from '@/views/ReviewDetailView.vue'

vi.mock('@/api', () => ({
  getReviewComments: vi.fn<typeof getReviewComments>(),
  getReviewDetail: vi.fn<typeof getReviewDetail>(),
  getReviewFindings: vi.fn<typeof getReviewFindings>(),
}))

const mockedGetReviewDetail = vi.mocked(getReviewDetail)
const mockedGetReviewFindings = vi.mocked(getReviewFindings)
const mockedGetReviewComments = vi.mocked(getReviewComments)

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

function makeReport(
  overrides: Partial<ReviewDetailReport> = {},
): ReviewDetailReport {
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

function makeFinding(
  overrides: Partial<ReviewFinding> = {},
): ReviewFinding {
  return {
    ordinal: 0,
    category: 'SECURITY',
    severity: 'HIGH',
    confidence: 0.94,
    ruleId: 'CWE-89',
    title: 'SQL injection',
    filePath: 'src/UserRepository.java',
    startLine: 52,
    endLine: 58,
    description: 'Externally controlled SQL.',
    reason: 'Input is concatenated into the query.',
    suggestion: 'Use parameterized queries.',
    references: ['CWE-89', null, ' ', 'OWASP'],
    ...overrides,
  }
}

function makeComment(
  overrides: Partial<ReviewComment> = {},
): ReviewComment {
  return {
    findingOrdinal: 0,
    githubCommentId: null,
    filePath: 'src/UserRepository.java',
    startLine: 52,
    endLine: 58,
    ...overrides,
  }
}

function makeFindingPage(
  items: ReviewFinding[] = [],
  overrides: Partial<ReviewFindingPage> = {},
): ReviewFindingPage {
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

function makeCommentPage(
  items: ReviewComment[] = [],
  overrides: Partial<ReviewCommentPage> = {},
): ReviewCommentPage {
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

function apiError(
  status: number,
  code: string,
  message = 'Request failed',
): ApiError {
  return new ApiError(message, { code, status })
}

async function mountDetail(path: string) {
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()

  const wrapper = mount(ReviewDetailView, {
    global: {
      plugins: [router],
    },
  })

  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().includes(label))
}

function sectionPagination(wrapper: VueWrapper, testId: string) {
  return wrapper
    .get(`[data-testid="${testId}"]`)
    .findComponent({ name: 'ElPagination' })
}

describe('ReviewDetailView', () => {
  beforeEach(() => {
    mockedGetReviewDetail.mockReset()
    mockedGetReviewFindings.mockReset()
    mockedGetReviewComments.mockReset()

    mockedGetReviewDetail.mockResolvedValue(makeReport())
    mockedGetReviewFindings.mockResolvedValue(makeFindingPage())
    mockedGetReviewComments.mockResolvedValue(makeCommentPage())
  })

  it('loads the report first and then requests findings and comments', async () => {
    const reportRequest = deferred<ReviewDetailReport>()
    mockedGetReviewDetail.mockReturnValueOnce(reportRequest.promise)

    const { wrapper } = await mountDetail('/reviews/7')

    expect(mockedGetReviewDetail).toHaveBeenCalledWith(
      7,
      expect.any(AbortSignal),
    )
    expect(mockedGetReviewFindings).not.toHaveBeenCalled()
    expect(mockedGetReviewComments).not.toHaveBeenCalled()
    expect(wrapper.find('.detail-loading').exists()).toBe(true)

    reportRequest.resolve(makeReport())
    await flushPromises()

    expect(mockedGetReviewFindings).toHaveBeenCalledWith(
      7,
      { page: 1, size: 20 },
      expect.any(AbortSignal),
    )
    expect(mockedGetReviewComments).toHaveBeenCalledWith(
      7,
      { page: 1, size: 20 },
      expect.any(AbortSignal),
    )
    expect(wrapper.find('.detail-loading').exists()).toBe(false)
    expect(wrapper.text()).toContain('Review information')
  })

  it('does not request section data when the report fails', async () => {
    mockedGetReviewDetail.mockRejectedValueOnce(
      apiError(500, 'HTTP_500', 'Backend unavailable'),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    expect(mockedGetReviewFindings).not.toHaveBeenCalled()
    expect(mockedGetReviewComments).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Unable to load review detail')
    expect(wrapper.text()).toContain('Backend unavailable')
    expect(findButton(wrapper, 'Retry')).toBeDefined()
  })

  it('shows a dedicated not-found state without child requests', async () => {
    mockedGetReviewDetail.mockRejectedValueOnce(
      apiError(404, 'review_not_found'),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    expect(mockedGetReviewFindings).not.toHaveBeenCalled()
    expect(mockedGetReviewComments).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Review not found')
    expect(wrapper.text()).toContain(
      'No structured review history is available for this task',
    )
    expect(findButton(wrapper, 'Retry')).toBeUndefined()
    expect(findButton(wrapper, 'Back to review history')).toBeUndefined()
    expect(wrapper.text()).toContain('Back to review history')
  })

  it('shows the incomplete state and retries the report', async () => {
    mockedGetReviewDetail.mockRejectedValueOnce(
      apiError(409, 'review_history_incomplete'),
    )
    mockedGetReviewDetail.mockResolvedValueOnce(makeReport())

    const { wrapper } = await mountDetail('/reviews/7')

    expect(wrapper.text()).toContain('Review history is incomplete')
    expect(wrapper.text()).toContain('Partial history is not shown')

    const retryButton = findButton(wrapper, 'Retry')
    expect(retryButton).toBeDefined()
    await retryButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Review information')
    expect(mockedGetReviewFindings).toHaveBeenCalledOnce()
    expect(mockedGetReviewComments).toHaveBeenCalledOnce()
  })

  it('shows a safe error state and retries the report', async () => {
    mockedGetReviewDetail.mockRejectedValueOnce(
      apiError(500, 'HTTP_500', 'The server encountered an unexpected error.'),
    )
    mockedGetReviewDetail.mockResolvedValueOnce(makeReport())

    const { wrapper } = await mountDetail('/reviews/7')

    expect(wrapper.text()).toContain('Unable to load review detail')
    expect(wrapper.text()).toContain(
      'The server encountered an unexpected error.',
    )

    const retryButton = findButton(wrapper, 'Retry')
    await retryButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Review information')
    expect(wrapper.text()).not.toContain('Unable to load review detail')
  })

  it('renders every stored report field and labels updatedAt correctly', async () => {
    const { wrapper } = await mountDetail('/reviews/7')

    const text = wrapper.text()
    expect(text).toContain('Review #7')
    expect(text).toContain('owner/repo')
    expect(text).toContain('PR #42')
    expect(text).toContain(COMMIT_SHA)
    expect(text).toContain('COMPLETED')
    expect(text).toContain('DEGRADED')
    expect(text).toContain('PARTIAL')
    expect(text).toContain('#900')
    expect(text).toContain('2026-01-02 03:04:05')
    expect(text).toContain('2026-01-02 03:00:00')
    expect(text).toContain('2026-01-02 03:04:00')
    expect(text).toContain('Last updated')
    expect(text).not.toContain('Completed at')
    expect(text).not.toContain('reportId')
  })

  it('renders placeholders for null summary id and published time', async () => {
    mockedGetReviewDetail.mockResolvedValueOnce(
      makeReport({ summaryCommentId: null, publishedAt: null }),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    const text = wrapper.text()
    expect(text).toContain('Not available')
    expect(text).toContain('—')
    expect(text).not.toContain('null')
  })

  it('describes the persisted AI summary without inventing a risk level', async () => {
    const { wrapper } = await mountDetail('/reviews/7')

    const summary = wrapper.get('.ai-summary').text()
    expect(summary).toContain('DEGRADED')
    expect(summary).toContain('PARTIAL')
    expect(summary).toContain('#900')
    expect(summary).toContain(
      'Narrative summary and risk level are not stored',
    )
    expect(summary).not.toContain('Overall risk')
    expect(summary).not.toContain('Review passed')
  })

  it('renders findings with severity, category, location, and confidence', async () => {
    mockedGetReviewFindings.mockResolvedValueOnce(
      makeFindingPage([makeFinding()]),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    const findings = wrapper.get('[data-testid="findings-section"]').text()
    expect(findings).toContain('#1')
    expect(findings).toContain('HIGH')
    expect(findings).toContain('SECURITY')
    expect(findings).toContain('SQL injection')
    expect(findings).toContain('CWE-89')
    expect(findings).toContain('src/UserRepository.java')
    expect(findings).toContain('L52–58')
    expect(findings).toContain('94%')
  })

  it('falls back safely for unknown severity and category values', async () => {
    mockedGetReviewFindings.mockResolvedValueOnce(
      makeFindingPage([
        makeFinding({
          severity: 'UNKNOWN' as FindingSeverity,
          category: 'MYSTERY' as FindingCategory,
        }),
      ]),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    const section = wrapper.get('[data-testid="findings-section"]')
    expect(section.text()).toContain('UNKNOWN')
    expect(section.text()).toContain('MYSTERY')

    const tags = section.findAllComponents({ name: 'ElTag' })
    expect(
      tags.find((tag: VueWrapper) => tag.text() === 'UNKNOWN')?.props('type'),
    ).toBe('info')
    expect(
      tags.find((tag: VueWrapper) => tag.text() === 'MYSTERY')?.props('type'),
    ).toBe('info')
  })

  it('expands a finding and filters null or blank references', async () => {
    mockedGetReviewFindings.mockResolvedValueOnce(
      makeFindingPage([makeFinding()]),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    const expand = wrapper.get('.el-table__expand-icon')
    await expand.trigger('click')
    await flushPromises()

    const detail = wrapper.get('.finding-detail')
    expect(detail.text()).toContain('Description')
    expect(detail.text()).toContain('Externally controlled SQL.')
    expect(detail.text()).toContain('Reason')
    expect(detail.text()).toContain('Input is concatenated into the query.')
    expect(detail.text()).toContain('Suggestion')
    expect(detail.text()).toContain('Use parameterized queries.')
    expect(detail.text()).toContain('References')

    const references = detail.findAll('.references-list li')
    expect(references).toHaveLength(2)
    expect(references[0]?.text()).toBe('CWE-89')
    expect(references[1]?.text()).toBe('OWASP')
    expect(detail.text()).not.toContain('null')
  })

  it('renders only published comment metadata and a safe id placeholder', async () => {
    mockedGetReviewComments.mockResolvedValueOnce(
      makeCommentPage([
        makeComment(),
        makeComment({ findingOrdinal: 1, githubCommentId: 123456 }),
      ]),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    const comments = wrapper.get('[data-testid="comments-section"]').text()
    expect(comments).toContain('Only comments confirmed published to GitHub')
    expect(comments).toContain('Failed or skipped comments are not listed')
    expect(comments).toContain('#1')
    expect(comments).toContain('#2')
    expect(comments).toContain('src/UserRepository.java')
    expect(comments).toContain('L52–58')
    expect(comments).toContain('ID unavailable')
    expect(comments).toContain('123456')
  })

  it('paginates findings and comments independently', async () => {
    mockedGetReviewFindings.mockImplementation(
      async (_taskId, params) => makeFindingPage(
        [makeFinding({ ordinal: params.page - 1 })],
        {
          page: params.page,
          size: params.size,
          totalItems: 45,
          totalPages: 3,
        },
      ),
    )
    mockedGetReviewComments.mockImplementation(
      async (_taskId, params) => makeCommentPage(
        [makeComment()],
        {
          page: params.page,
          size: params.size,
          totalItems: 5,
          totalPages: 1,
        },
      ),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    expect(mockedGetReviewFindings).toHaveBeenCalledTimes(1)
    expect(mockedGetReviewComments).toHaveBeenCalledTimes(1)

    sectionPagination(wrapper, 'findings-section').vm.$emit(
      'current-change',
      2,
    )
    await flushPromises()

    expect(mockedGetReviewFindings).toHaveBeenLastCalledWith(
      7,
      { page: 2, size: 20 },
      expect.any(AbortSignal),
    )
    expect(mockedGetReviewComments).toHaveBeenCalledTimes(1)

    sectionPagination(wrapper, 'comments-section').vm.$emit(
      'current-change',
      2,
    )
    await flushPromises()

    expect(mockedGetReviewComments).toHaveBeenLastCalledWith(
      7,
      { page: 2, size: 20 },
      expect.any(AbortSignal),
    )
    expect(mockedGetReviewFindings).toHaveBeenCalledTimes(2)

    sectionPagination(wrapper, 'findings-section').vm.$emit(
      'size-change',
      50,
    )
    await flushPromises()

    expect(mockedGetReviewFindings).toHaveBeenLastCalledWith(
      7,
      { page: 1, size: 50 },
      expect.any(AbortSignal),
    )
    expect(mockedGetReviewComments).toHaveBeenCalledTimes(2)
  })

  it('keeps pagination when an empty page still has total items', async () => {
    mockedGetReviewFindings.mockImplementation(
      async (_taskId, params) => (params.page === 3
        ? makeFindingPage([], {
          page: 3,
          size: params.size,
          totalItems: 45,
          totalPages: 3,
        })
        : makeFindingPage([makeFinding()], {
          page: params.page,
          size: params.size,
          totalItems: 45,
          totalPages: 3,
        })),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    sectionPagination(wrapper, 'findings-section').vm.$emit(
      'current-change',
      3,
    )
    await flushPromises()

    const section = wrapper.get('[data-testid="findings-section"]')
    expect(section.text()).toContain('No findings on this page')

    const pagination = section.findComponent({ name: 'ElPagination' })
    expect(pagination.exists()).toBe(true)
    expect(pagination.props('total')).toBe(45)

    pagination.vm.$emit('current-change', 1)
    await flushPromises()

    expect(mockedGetReviewFindings).toHaveBeenLastCalledWith(
      7,
      { page: 1, size: 20 },
      expect.any(AbortSignal),
    )
    expect(wrapper.text()).toContain('SQL injection')
  })

  it('keeps comments visible when the findings section fails', async () => {
    mockedGetReviewFindings.mockRejectedValueOnce(
      apiError(500, 'HTTP_500', 'Findings unavailable'),
    )
    mockedGetReviewComments.mockResolvedValueOnce(
      makeCommentPage([makeComment()]),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    const findings = wrapper.get('[data-testid="findings-section"]').text()
    expect(findings).toContain('Unable to load findings')
    expect(findings).toContain('Findings unavailable')

    const comments = wrapper.get('[data-testid="comments-section"]').text()
    expect(comments).toContain('#1')
    expect(comments).toContain('ID unavailable')

    mockedGetReviewFindings.mockResolvedValueOnce(
      makeFindingPage([makeFinding()]),
    )
    const retry = wrapper
      .get('[data-testid="findings-section"]')
      .findAll('button')
      .find((button) => button.text().includes('Retry'))
    await retry?.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="findings-section"]').text())
      .toContain('SQL injection')
  })

  it('ignores a stale findings response that settles last', async () => {
    const pageTwo = deferred<ReviewFindingPage>()
    const pageThree = deferred<ReviewFindingPage>()

    mockedGetReviewFindings
      .mockResolvedValueOnce(
        makeFindingPage([makeFinding({ title: 'page one' })], {
          page: 1,
          size: 20,
          totalItems: 45,
          totalPages: 3,
        }),
      )
      .mockReturnValueOnce(pageTwo.promise)
      .mockReturnValueOnce(pageThree.promise)

    const { wrapper } = await mountDetail('/reviews/7')

    sectionPagination(wrapper, 'findings-section').vm.$emit(
      'current-change',
      2,
    )
    await flushPromises()

    sectionPagination(wrapper, 'findings-section').vm.$emit(
      'current-change',
      3,
    )
    await flushPromises()

    const pageTwoSignal = mockedGetReviewFindings.mock.calls[1]?.[2]
    expect(pageTwoSignal?.aborted).toBe(true)

    pageThree.resolve(
      makeFindingPage([makeFinding({ title: 'page three' })], {
        page: 3,
        size: 20,
        totalItems: 45,
        totalPages: 3,
      }),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('page three')

    pageTwo.resolve(
      makeFindingPage([makeFinding({ title: 'page two' })], {
        page: 2,
        size: 20,
        totalItems: 45,
        totalPages: 3,
      }),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('page three')
    expect(wrapper.text()).not.toContain('page two')
  })

  it('reloads when the route moves to another review id', async () => {
    mockedGetReviewDetail.mockImplementation(
      async (taskId) => makeReport({ taskId }),
    )
    mockedGetReviewFindings.mockImplementation(
      async (taskId) => makeFindingPage([
        makeFinding({ title: `Finding for ${taskId}` }),
      ]),
    )

    const { wrapper, router } = await mountDetail('/reviews/7')

    expect(wrapper.text()).toContain('Review #7')
    expect(wrapper.text()).toContain('Finding for 7')

    await router.push('/reviews/8')
    await flushPromises()

    expect(mockedGetReviewDetail).toHaveBeenLastCalledWith(
      8,
      expect.any(AbortSignal),
    )
    expect(wrapper.text()).toContain('Review #8')
    expect(wrapper.text()).toContain('Finding for 8')
    expect(wrapper.text()).not.toContain('Finding for 7')
  })

  it('reloads the current pages after refresh', async () => {
    mockedGetReviewFindings.mockImplementation(
      async (_taskId, params) => makeFindingPage(
        [makeFinding()],
        {
          page: params.page,
          size: params.size,
          totalItems: 45,
          totalPages: 3,
        },
      ),
    )

    const { wrapper } = await mountDetail('/reviews/7')

    sectionPagination(wrapper, 'findings-section').vm.$emit(
      'current-change',
      2,
    )
    await flushPromises()

    expect(mockedGetReviewFindings).toHaveBeenLastCalledWith(
      7,
      { page: 2, size: 20 },
      expect.any(AbortSignal),
    )

    const refreshButton = findButton(wrapper, 'Refresh')
    await refreshButton?.trigger('click')
    await flushPromises()

    expect(mockedGetReviewDetail).toHaveBeenCalledTimes(2)
    expect(mockedGetReviewFindings).toHaveBeenLastCalledWith(
      7,
      { page: 2, size: 20 },
      expect.any(AbortSignal),
    )
    expect(mockedGetReviewComments).toHaveBeenLastCalledWith(
      7,
      { page: 1, size: 20 },
      expect.any(AbortSignal),
    )
  })

  it('aborts every in-flight request on unmount', async () => {
    const findingsRequest = deferred<ReviewFindingPage>()
    const commentsRequest = deferred<ReviewCommentPage>()

    mockedGetReviewFindings.mockReturnValueOnce(findingsRequest.promise)
    mockedGetReviewComments.mockReturnValueOnce(commentsRequest.promise)

    const { wrapper } = await mountDetail('/reviews/7')

    const findingsSignal = mockedGetReviewFindings.mock.calls[0]?.[2]
    const commentsSignal = mockedGetReviewComments.mock.calls[0]?.[2]
    expect(findingsSignal?.aborted).toBe(false)
    expect(commentsSignal?.aborted).toBe(false)

    wrapper.unmount()

    expect(findingsSignal?.aborted).toBe(true)
    expect(commentsSignal?.aborted).toBe(true)
  })

  it('does not send requests for an invalid numeric task id', async () => {
    const { wrapper } = await mountDetail('/reviews/0')

    expect(mockedGetReviewDetail).not.toHaveBeenCalled()
    expect(mockedGetReviewFindings).not.toHaveBeenCalled()
    expect(mockedGetReviewComments).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Review not found')
    expect(wrapper.text()).toContain('valid positive review task ID')
  })

  it('does not send requests for an unsafe integer task id', async () => {
    const { wrapper } = await mountDetail(
      '/reviews/999999999999999999999',
    )

    expect(mockedGetReviewDetail).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Review not found')
  })
})
