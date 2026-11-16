import {
  AxiosError,
  AxiosHeaders,
  CanceledError,
  type AxiosResponse,
} from 'axios'
import { describe, expect, it } from 'vitest'

import { ApiError, getErrorMessage, toApiError } from '@/utils/api-error'

function axiosErrorWithResponse(status: number, data: unknown): AxiosError {
  const response = {
    data,
    status,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as unknown as AxiosResponse

  return new AxiosError(
    'Request failed',
    'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    response,
  )
}

describe('toApiError', () => {
  it('keeps an existing ApiError unchanged', () => {
    const original = new ApiError('Already normalized', { code: 'TEST' })

    expect(toApiError(original)).toBe(original)
  })

  it('maps a timeout', () => {
    const error = new AxiosError('timeout', 'ECONNABORTED')

    expect(toApiError(error)).toMatchObject({
      code: 'TIMEOUT',
      message: 'The request timed out. Please try again.',
    })
  })

  it('maps a missing response to a network error', () => {
    const error = new AxiosError('network', 'ERR_NETWORK')

    expect(toApiError(error)).toMatchObject({
      code: 'NETWORK',
    })
  })

  it('maps an ERR_CANCELED error to a cancellation, not a network error', () => {
    const error = new AxiosError('canceled', 'ERR_CANCELED')

    expect(toApiError(error)).toMatchObject({
      code: 'CANCELED',
      message: 'The request was canceled.',
    })
  })

  it('maps an axios CanceledError instance to a cancellation', () => {
    const error = toApiError(new CanceledError())

    expect(error.code).toBe('CANCELED')
    expect(error.code).not.toBe('NETWORK')
  })

  it('maps HTTP statuses to stable messages', () => {
    const error = toApiError(axiosErrorWithResponse(401, null))

    expect(error.status).toBe(401)
    expect(error.code).toBe('HTTP_401')
    expect(error.message).toBe('Authentication is required.')
  })

  it('preserves a safe server error code', () => {
    const error = toApiError(
      axiosErrorWithResponse(409, { code: 'review_history_incomplete' }),
    )

    expect(error).toMatchObject({
      code: 'review_history_incomplete',
      status: 409,
      message: 'The request conflicts with the current state.',
    })
  })

  it('does not retain the raw server response payload', () => {
    const error = toApiError(
      axiosErrorWithResponse(500, {
        code: 'internal_error',
        message: 'secret server detail',
        stack: 'at com.example.Secret.method(Secret.java:42)',
        token: 'should-not-leak',
      }),
    )

    expect(error).not.toHaveProperty('details')
    expect(Object.keys(error)).not.toContain('details')
    expect(error.message).toBe('The server encountered an unexpected error.')
    expect(error.message).not.toContain('secret server detail')
    expect(error.message).not.toContain('Secret.java')
    expect(error.message).not.toContain('should-not-leak')
  })

  it('falls back for an unknown HTTP status', () => {
    const error = toApiError(axiosErrorWithResponse(418, null))

    expect(error.code).toBe('HTTP_418')
    expect(error.message).toBe('Request failed with status 418.')
  })

  it('wraps non-Axios errors without retaining the original error', () => {
    const error = toApiError(new Error('boom'))

    expect(error).toMatchObject({
      code: 'UNKNOWN',
      message: 'Something went wrong. Please try again.',
    })
    expect(error).not.toHaveProperty('details')
    expect(error.message).not.toContain('boom')
  })
})

describe('getErrorMessage', () => {
  it('returns the normalized message', () => {
    expect(getErrorMessage(new ApiError('Custom failure', { code: 'X' }))).toBe(
      'Custom failure',
    )
  })
})
