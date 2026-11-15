import type {
  StatisticsFilters,
  StatisticsOverviewQuery,
  StatisticsOverviewResponse,
  StatisticsReviewPage,
  StatisticsReviewsQuery,
} from '@/types/statistics'

import { apiGet, type QueryParams } from './client'

export const STATISTICS_OVERVIEW_ENDPOINT =
  '/api/dashboard/statistics/overview'
export const STATISTICS_REVIEWS_ENDPOINT =
  '/api/dashboard/statistics/reviews'

/**
 * Serializes the filters shared by both statistics endpoints. Blank optional
 * strings are omitted so the backend applies its own defaults; page, size,
 * sort and direction are always sent by the reviews query.
 */
function toFilterParams(query: StatisticsFilters): QueryParams {
  const params: QueryParams = {}

  const owner = query.owner?.trim()
  if (owner) {
    params.owner = owner
  }

  const repo = query.repo?.trim()
  if (repo) {
    params.repo = repo
  }

  if (query.prNumber !== undefined && query.prNumber !== null) {
    params.prNumber = query.prNumber
  }

  if (query.taskStatus) {
    params.taskStatus = query.taskStatus
  }

  if (query.publishStatus) {
    params.publishStatus = query.publishStatus
  }

  if (query.aiStatus) {
    params.aiStatus = query.aiStatus
  }

  const createdFrom = query.createdFrom?.trim()
  if (createdFrom) {
    params.createdFrom = createdFrom
  }

  const createdTo = query.createdTo?.trim()
  if (createdTo) {
    params.createdTo = createdTo
  }

  return params
}

/** Reads summary, trend and data-quality counters from one backend snapshot. */
export function getStatisticsOverview(
  query: StatisticsOverviewQuery,
  signal?: AbortSignal,
): Promise<StatisticsOverviewResponse> {
  return apiGet<StatisticsOverviewResponse>(
    STATISTICS_OVERVIEW_ENDPOINT,
    signal,
    {
      ...toFilterParams(query),
      granularity: query.granularity,
    },
  )
}

/** Reads one page of per-review comparison rows. */
export function getStatisticsReviews(
  query: StatisticsReviewsQuery,
  signal?: AbortSignal,
): Promise<StatisticsReviewPage> {
  return apiGet<StatisticsReviewPage>(
    STATISTICS_REVIEWS_ENDPOINT,
    signal,
    {
      ...toFilterParams(query),
      page: query.page,
      size: query.size,
      sort: query.sort,
      direction: query.direction,
    },
  )
}
