import axios from 'axios'

import { API_BASE_URL } from '@/config/app'
import { toApiError } from '@/utils/api-error'

/**
 * Browser API client.
 *
 * Only browser-safe endpoints belong here. Review history is read from the
 * loopback-only Dashboard BFF at `/api/dashboard/reviews`; the frontend never
 * sends `X-Internal-Token` and never stores credentials in browser storage.
 */
export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    Accept: 'application/json',
  },
})

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(toApiError(error)),
)

export type QueryParams = Record<
  string,
  string | number | boolean | null | undefined
>

export async function apiGet<T>(
  url: string,
  signal?: AbortSignal,
  params?: QueryParams,
): Promise<T> {
  const response = await http.get<T>(url, { params, signal })
  return response.data
}
