import type {
  ReviewHistoryPage,
  ReviewHistoryQuery,
} from '@/types/api'

import { apiGet, type QueryParams } from './client'

export const REVIEW_HISTORY_ENDPOINT = '/api/dashboard/reviews'

/**
 * Reads one page of review history from the same-origin Dashboard BFF.
 *
 * Empty optional filters are omitted so the backend applies its defaults.
 * `page` and `size` are always sent; the backend caps `size` at 100.
 */
export function getReviewHistory(
  query: ReviewHistoryQuery,
  signal?: AbortSignal,
): Promise<ReviewHistoryPage> {
  const params: QueryParams = {
    page: query.page,
    size: query.size,
  }

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

  if (query.aiStatus) {
    params.aiStatus = query.aiStatus
  }

  if (query.publishStatus) {
    params.publishStatus = query.publishStatus
  }

  const createdFrom = query.createdFrom?.trim()
  if (createdFrom) {
    params.createdFrom = createdFrom
  }

  const createdTo = query.createdTo?.trim()
  if (createdTo) {
    params.createdTo = createdTo
  }

  return apiGet<ReviewHistoryPage>(
    REVIEW_HISTORY_ENDPOINT,
    signal,
    params,
  )
}
