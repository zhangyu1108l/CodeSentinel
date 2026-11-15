import { onBeforeUnmount, ref } from 'vue'

import { getStatisticsReviews } from '@/api'
import type {
  StatisticsReviewPage,
  StatisticsReviewsQuery,
} from '@/types/statistics'
import { getStatisticsErrorMessage } from '@/utils/statistics-error'

/**
 * Owns the paginated review-comparison request lifecycle with the same
 * single-flight, sequence-guarded and abortable behaviour as the overview.
 */
export function useReviewStatistics() {
  const data = ref<StatisticsReviewPage | null>(null)
  const loading = ref(false)
  const error = ref('')

  let activeRequest: AbortController | null = null
  let requestSequence = 0
  let disposed = false

  async function load(query: StatisticsReviewsQuery): Promise<void> {
    activeRequest?.abort()

    const request = new AbortController()
    activeRequest = request
    const sequence = ++requestSequence

    loading.value = true
    error.value = ''

    try {
      const result = await getStatisticsReviews(query, request.signal)
      if (disposed || request.signal.aborted || sequence !== requestSequence) {
        return
      }
      data.value = result
    } catch (requestError) {
      if (disposed || request.signal.aborted || sequence !== requestSequence) {
        return
      }
      error.value = getStatisticsErrorMessage(requestError)
    } finally {
      if (!disposed && sequence === requestSequence) {
        loading.value = false
        if (activeRequest === request) {
          activeRequest = null
        }
      }
    }
  }

  function abort(): void {
    activeRequest?.abort()
    activeRequest = null
  }

  onBeforeUnmount(() => {
    disposed = true
    abort()
  })

  return { data, loading, error, load, abort }
}
