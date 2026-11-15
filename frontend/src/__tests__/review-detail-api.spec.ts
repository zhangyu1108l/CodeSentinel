import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  ReviewCommentPage,
  ReviewDetailReport,
  ReviewFindingPage,
} from '@/types/api'
import { ApiError } from '@/utils/api-error'

const { apiGetMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn<
    (
      url: string,
      signal?: AbortSignal,
      params?: Record<string, unknown>,
    ) => Promise<unknown>
  >(),
}))

vi.mock('@/api/client', () => ({
  apiGet: apiGetMock,
}))

import {
  getReviewComments,
  getReviewDetail,
  getReviewFindings,
  REVIEW_DETAIL_ENDPOINT,
} from '@/api/review-detail'

function makeReport(): ReviewDetailReport {
  return {
    taskId: 7,
    owner: 'owner',
    repo: 'repo',
    prNumber: 42,
    commitSha: 'abc123',
    taskStatus: 'COMPLETED',
    aiStatus: 'DEGRADED',
    publishStatus: 'PARTIAL',
    findingCount: 2,
    publishedCommentCount: 1,
    summaryCommentId: 900,
    publishedAt: '2026-01-02T03:04:05',
    createdAt: '2026-01-02T03:00:00',
    updatedAt: '2026-01-02T03:04:00',
  }
}

function makeFindingPage(
  overrides: Partial<ReviewFindingPage> = {},
): ReviewFindingPage {
  return {
    items: [
      {
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
        reason: 'Input is concatenated.',
        suggestion: 'Use parameters.',
        references: ['CWE-89', null],
      },
    ],
    page: 1,
    size: 20,
    totalItems: 1,
    totalPages: 1,
    hasNext: false,
    ...overrides,
  }
}

function makeCommentPage(
  overrides: Partial<ReviewCommentPage> = {},
): ReviewCommentPage {
  return {
    items: [
      {
        findingOrdinal: 0,
        githubCommentId: null,
        filePath: 'src/UserRepository.java',
        startLine: 52,
        endLine: 58,
      },
    ],
    page: 1,
    size: 20,
    totalItems: 1,
    totalPages: 1,
    hasNext: false,
    ...overrides,
  }
}

describe('review detail API', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
  })

  it('uses the same-origin Dashboard detail endpoint', () => {
    expect(REVIEW_DETAIL_ENDPOINT).toBe('/api/dashboard/reviews')
  })

  it('loads one review report and forwards the abort signal', async () => {
    const report = makeReport()
    apiGetMock.mockResolvedValue(report)

    const signal = new AbortController().signal
    const result = await getReviewDetail(7, signal)

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/reviews/7',
      signal,
    )
    expect(result).toBe(report)
  })

  it('loads findings with explicit page and size', async () => {
    const response = makeFindingPage({ page: 2, size: 50 })
    apiGetMock.mockResolvedValue(response)

    const signal = new AbortController().signal
    const result = await getReviewFindings(7, { page: 2, size: 50 }, signal)

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/reviews/7/findings',
      signal,
      { page: 2, size: 50 },
    )
    expect(result).toBe(response)
  })

  it('loads published comments with explicit page and size', async () => {
    const response = makeCommentPage({ page: 3, size: 10 })
    apiGetMock.mockResolvedValue(response)

    const result = await getReviewComments(7, { page: 3, size: 10 })

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/reviews/7/comments',
      undefined,
      { page: 3, size: 10 },
    )
    expect(result).toBe(response)
  })

  it('keeps every request on the browser-safe BFF namespace', async () => {
    apiGetMock.mockResolvedValue(makeFindingPage())

    await getReviewDetail(7)
    await getReviewFindings(7, { page: 1, size: 20 })
    await getReviewComments(7, { page: 1, size: 20 })

    for (const call of apiGetMock.mock.calls) {
      expect(call[0].startsWith('/api/dashboard/reviews/')).toBe(true)
      expect(call[0].startsWith('/api/reviews/')).toBe(false)
    }
  })

  it('preserves a normalized ApiError from the shared client', async () => {
    const error = new ApiError('Review history is incomplete.', {
      code: 'review_history_incomplete',
      status: 409,
    })
    apiGetMock.mockRejectedValue(error)

    await expect(
      getReviewFindings(7, { page: 1, size: 20 }),
    ).rejects.toBe(error)
  })
})
