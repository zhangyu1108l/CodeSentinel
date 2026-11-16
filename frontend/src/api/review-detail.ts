import type {
  ReviewCommentPage,
  ReviewDetailReport,
  ReviewFindingPage,
} from '@/types/api'

import { apiGet } from './client'

/** Same-origin Dashboard BFF namespace implemented in Phase 11.2.3-B. */
export const REVIEW_DETAIL_ENDPOINT = '/api/dashboard/reviews'

export interface ReviewPageParams {
  page: number
  size: number
}

/**
 * Reads the report metadata of one review. The response is the exact
 * `ReviewReportResponse` shape used by the review history list.
 */
export function getReviewDetail(
  taskId: number,
  signal?: AbortSignal,
): Promise<ReviewDetailReport> {
  return apiGet<ReviewDetailReport>(
    `${REVIEW_DETAIL_ENDPOINT}/${taskId}`,
    signal,
  )
}

export function getReviewFindings(
  taskId: number,
  params: ReviewPageParams,
  signal?: AbortSignal,
): Promise<ReviewFindingPage> {
  return apiGet<ReviewFindingPage>(
    `${REVIEW_DETAIL_ENDPOINT}/${taskId}/findings`,
    signal,
    { page: params.page, size: params.size },
  )
}

export function getReviewComments(
  taskId: number,
  params: ReviewPageParams,
  signal?: AbortSignal,
): Promise<ReviewCommentPage> {
  return apiGet<ReviewCommentPage>(
    `${REVIEW_DETAIL_ENDPOINT}/${taskId}/comments`,
    signal,
    { page: params.page, size: params.size },
  )
}
