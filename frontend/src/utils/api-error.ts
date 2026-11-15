import axios from 'axios'

import type { ApiErrorPayload } from '@/types/api'

const DEFAULT_MESSAGE = 'Something went wrong. Please try again.'

const HTTP_MESSAGES: Record<number, string> = {
  400: 'The request could not be processed.',
  401: 'Authentication is required.',
  403: 'You do not have permission to perform this action.',
  404: 'The requested resource was not found.',
  409: 'The request conflicts with the current state.',
  429: 'Too many requests. Please try again shortly.',
  500: 'The server encountered an unexpected error.',
  502: 'The server returned an invalid response.',
  503: 'The service is temporarily unavailable.',
}

interface ApiErrorOptions {
  code: string
  status?: number
}

/**
 * Normalized error exposed to views. UI code should never depend on
 * Axios-specific error shapes, raw response bodies, or stack details.
 */
export class ApiError extends Error {
  readonly code: string
  readonly status?: number

  constructor(message: string, options: ApiErrorOptions) {
    super(message)
    this.name = 'ApiError'
    this.code = options.code
    this.status = options.status
  }
}

function readPayloadCode(payload: unknown): string | undefined {
  if (typeof payload !== 'object' || payload === null) {
    return undefined
  }
  const candidate = (payload as ApiErrorPayload).code ?? (payload as ApiErrorPayload).error
  return typeof candidate === 'string' && candidate.trim() ? candidate : undefined
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error
  }

  if (!axios.isAxiosError(error)) {
    return new ApiError(DEFAULT_MESSAGE, { code: 'UNKNOWN' })
  }

  if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
    return new ApiError('The request was canceled.', { code: 'CANCELED' })
  }

  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return new ApiError('The request timed out. Please try again.', { code: 'TIMEOUT' })
  }

  if (!error.response) {
    return new ApiError(
      'Cannot reach the CodeSentinel API. Check that the backend is running.',
      { code: 'NETWORK' },
    )
  }

  const status = error.response.status
  const code = readPayloadCode(error.response.data) ?? `HTTP_${status}`
  const message = HTTP_MESSAGES[status] ?? `Request failed with status ${status}.`

  return new ApiError(message, {
    code,
    status,
  })
}

export function getErrorMessage(error: unknown): string {
  return toApiError(error).message
}
