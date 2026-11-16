import { toApiError } from '@/utils/api-error'

const STATISTICS_ERROR_MESSAGES: Record<string, string> = {
  invalid_filter:
    'The filters are not valid. Check the values and the date range.',
  invalid_range: 'The selected date range must not exceed 366 days.',
  invalid_granularity: 'The selected trend granularity is not supported.',
  invalid_pagination: 'The requested page is not valid.',
  invalid_sort: 'The requested sort order is not supported.',
  internal_error:
    'The statistics service could not read the stored review history. Please retry.',
}

/**
 * Maps stable backend error codes to user-facing text. Raw backend payloads,
 * SQL details and stack information are never displayed.
 */
export function getStatisticsErrorMessage(error: unknown): string {
  const apiError = toApiError(error)
  if (apiError.code === 'CANCELED') {
    return ''
  }
  if (apiError.status === 403) {
    return 'The local dashboard rejected this request. Open it from the same machine as the backend.'
  }
  return STATISTICS_ERROR_MESSAGES[apiError.code] ?? apiError.message
}
