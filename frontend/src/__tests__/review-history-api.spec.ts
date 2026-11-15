import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ReviewHistoryPage } from '@/types/api'

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
  getReviewHistory,
  REVIEW_HISTORY_ENDPOINT,
} from '@/api/review-history'

function makePage(overrides: Partial<ReviewHistoryPage> = {}): ReviewHistoryPage {
  return {
    items: [
      {
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

describe('getReviewHistory', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
  })

  it('calls only the same-origin Dashboard endpoint with page and size', async () => {
    const response = makePage()
    apiGetMock.mockResolvedValue(response)

    const signal = new AbortController().signal
    const result = await getReviewHistory({ page: 2, size: 50 }, signal)

    expect(REVIEW_HISTORY_ENDPOINT).toBe('/api/dashboard/reviews')
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/reviews',
      signal,
      { page: 2, size: 50 },
    )
    expect(result).toBe(response)
  })

  it('trims strings and forwards every supported filter', async () => {
    apiGetMock.mockResolvedValue(makePage())

    await getReviewHistory({
      page: 1,
      size: 100,
      owner: '  acme ',
      repo: ' sentinel  ',
      prNumber: 42,
      taskStatus: 'COMPLETED',
      aiStatus: 'DEGRADED',
      publishStatus: 'PARTIAL',
      createdFrom: '2026-01-01T00:00:00',
      createdTo: '2026-02-01T23:59:59',
    })

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/reviews',
      undefined,
      {
        page: 1,
        size: 100,
        owner: 'acme',
        repo: 'sentinel',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        aiStatus: 'DEGRADED',
        publishStatus: 'PARTIAL',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59',
      },
    )
  })

  it('omits blank optional filters and undefined values', async () => {
    apiGetMock.mockResolvedValue(makePage())

    await getReviewHistory({
      page: 1,
      size: 20,
      owner: '   ',
      repo: '',
      prNumber: undefined,
      taskStatus: undefined,
      aiStatus: undefined,
      publishStatus: undefined,
      createdFrom: '  ',
      createdTo: '',
    })

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/reviews',
      undefined,
      { page: 1, size: 20 },
    )
  })

  it('preserves the response envelope and item fields', async () => {
    const response = makePage({
      page: 3,
      size: 10,
      totalItems: 25,
      totalPages: 3,
      hasNext: false,
    })
    apiGetMock.mockResolvedValue(response)

    const result = await getReviewHistory({ page: 3, size: 10 })

    expect(result).toEqual(response)
    expect(result.items[0]).toMatchObject({
      taskId: 7,
      taskStatus: 'COMPLETED',
      aiStatus: 'DEGRADED',
      publishStatus: 'PARTIAL',
      findingCount: 2,
      publishedCommentCount: 1,
      summaryCommentId: 900,
    })
  })
})
