import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getStatisticsErrorMessage } from '@/utils/statistics-error'
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
  getStatisticsOverview,
  getStatisticsReviews,
  STATISTICS_OVERVIEW_ENDPOINT,
  STATISTICS_REVIEWS_ENDPOINT,
} from '@/api/statistics'

describe('statistics API client', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
  })

  it('requests the overview endpoint with granularity and every filter', async () => {
    const response = { summary: {} }
    apiGetMock.mockResolvedValue(response)
    const signal = new AbortController().signal

    const result = await getStatisticsOverview(
      {
        owner: '  acme ',
        repo: ' sentinel ',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        publishStatus: 'PARTIAL',
        aiStatus: 'DEGRADED',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59.999999',
        granularity: 'WEEK',
      },
      signal,
    )

    expect(STATISTICS_OVERVIEW_ENDPOINT).toBe(
      '/api/dashboard/statistics/overview',
    )
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/statistics/overview',
      signal,
      {
        owner: 'acme',
        repo: 'sentinel',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        publishStatus: 'PARTIAL',
        aiStatus: 'DEGRADED',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59.999999',
        granularity: 'WEEK',
      },
    )
    expect(result).toBe(response)
  })

  it('omits blank optional filters from the overview request', async () => {
    apiGetMock.mockResolvedValue({})

    await getStatisticsOverview({
      owner: '   ',
      repo: '',
      createdFrom: ' ',
      createdTo: '',
      granularity: 'DAY',
    })

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/statistics/overview',
      undefined,
      { granularity: 'DAY' },
    )
  })

  it('requests the reviews endpoint with pagination, sorting and filters', async () => {
    const response = { items: [] }
    apiGetMock.mockResolvedValue(response)

    const result = await getStatisticsReviews({
      page: 2,
      size: 50,
      sort: 'actualFindingCount',
      direction: 'asc',
      owner: 'acme',
      repo: 'sentinel',
      prNumber: 42,
      taskStatus: 'COMPLETED',
      publishStatus: 'PARTIAL',
      aiStatus: 'DEGRADED',
      createdFrom: '2026-01-01T00:00:00',
      createdTo: '2026-02-01T23:59:59.999999',
    })

    expect(STATISTICS_REVIEWS_ENDPOINT).toBe(
      '/api/dashboard/statistics/reviews',
    )
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/statistics/reviews',
      undefined,
      {
        page: 2,
        size: 50,
        sort: 'actualFindingCount',
        direction: 'asc',
        owner: 'acme',
        repo: 'sentinel',
        prNumber: 42,
        taskStatus: 'COMPLETED',
        publishStatus: 'PARTIAL',
        aiStatus: 'DEGRADED',
        createdFrom: '2026-01-01T00:00:00',
        createdTo: '2026-02-01T23:59:59.999999',
      },
    )
    expect(result).toBe(response)
  })

  it('keeps page, size, sort and direction in the reviews request', async () => {
    apiGetMock.mockResolvedValue({})

    await getStatisticsReviews({
      page: 1,
      size: 20,
      sort: 'createdAt',
      direction: 'desc',
    })

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/dashboard/statistics/reviews',
      undefined,
      {
        page: 1,
        size: 20,
        sort: 'createdAt',
        direction: 'desc',
      },
    )
  })
})

describe('statistics error messages', () => {
  it('maps stable backend codes to user-facing messages', () => {
    expect(
      getStatisticsErrorMessage(new ApiError('raw', { code: 'invalid_range' })),
    ).toContain('366 days')
    expect(
      getStatisticsErrorMessage(
        new ApiError('raw', { code: 'invalid_filter' }),
      ),
    ).toContain('filters are not valid')
    expect(
      getStatisticsErrorMessage(
        new ApiError('raw', { code: 'internal_error' }),
      ),
    ).toContain('could not read the stored review history')
  })

  it('replaces the generic 403 message with the local-dashboard explanation', () => {
    expect(
      getStatisticsErrorMessage(
        new ApiError('Forbidden', { code: 'HTTP_403', status: 403 }),
      ),
    ).toContain('same machine as the backend')
  })

  it('keeps unknown codes on their normalized message', () => {
    expect(
      getStatisticsErrorMessage(new ApiError('Backend unavailable', { code: 'NETWORK' })),
    ).toBe('Backend unavailable')
  })

  it('returns an empty message for canceled requests', () => {
    expect(
      getStatisticsErrorMessage(new ApiError('canceled', { code: 'CANCELED' })),
    ).toBe('')
  })
})
