import { onBeforeUnmount, ref } from 'vue'

import { getStatisticsOverview } from '@/api'
import type {
  StatisticsOverviewQuery,
  StatisticsOverviewResponse,
} from '@/types/statistics'
import { getStatisticsErrorMessage } from '@/utils/statistics-error'

/**
 * Owns the overview request lifecycle: one in-flight request at a time, a
 * monotonic sequence guard against stale responses, and an abort on unmount
 * or on the next load.
 */
export function useStatisticsOverview() {
  const data = ref<StatisticsOverviewResponse | null>(null)
  const loading = ref(false)
  const error = ref('')

  let activeRequest: AbortController | null = null
  let requestSequence = 0
  let disposed = false

  async function load(query: StatisticsOverviewQuery): Promise<void> {
    activeRequest?.abort()

    const request = new AbortController()
    activeRequest = request
    const sequence = ++requestSequence

    loading.value = true
    error.value = ''

    try {
      const result = await getStatisticsOverview(query, request.signal)
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
