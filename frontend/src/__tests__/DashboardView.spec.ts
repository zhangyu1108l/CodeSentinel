import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getHealth } from '@/api'
import type { HealthResponse } from '@/types/api'
import { ApiError } from '@/utils/api-error'
import DashboardView from '@/views/DashboardView.vue'

vi.mock('@/api', () => ({
  getHealth: vi.fn<typeof getHealth>(),
}))

const mockedGetHealth = vi.mocked(getHealth)

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().includes(label))
}

describe('DashboardView', () => {
  beforeEach(() => {
    mockedGetHealth.mockReset()
  })

  it('renders the operational backend state', async () => {
    mockedGetHealth.mockResolvedValue({
      status: 'UP',
      service: 'codesentinel',
    })

    const wrapper = mount(DashboardView)
    await flushPromises()

    expect(mockedGetHealth).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Operational')
    expect(wrapper.text()).toContain('codesentinel')
    expect(wrapper.text()).toContain('Phases 1–10 complete')
  })

  it('shows a loading state until the health request settles', async () => {
    const pending = deferred<HealthResponse>()
    mockedGetHealth.mockReturnValueOnce(pending.promise)

    const wrapper = mount(DashboardView)
    await flushPromises()

    expect(wrapper.find('.el-skeleton').exists()).toBe(true)
    expect(wrapper.find('.status-pill--loading').exists()).toBe(true)
    expect(wrapper.text()).toContain('Checking')

    pending.resolve({ status: 'UP', service: 'codesentinel' })
    await flushPromises()

    expect(wrapper.find('.el-skeleton').exists()).toBe(false)
    expect(wrapper.find('.status-pill--loading').exists()).toBe(false)
    expect(wrapper.text()).toContain('Operational')
  })

  it('renders an error state and retries the health request', async () => {
    mockedGetHealth.mockRejectedValueOnce(
      new ApiError('Backend unavailable', { code: 'NETWORK' }),
    )

    const wrapper = mount(DashboardView)
    await flushPromises()

    expect(wrapper.text()).toContain('Unavailable')
    expect(wrapper.text()).toContain('Backend unavailable')

    mockedGetHealth.mockResolvedValueOnce({
      status: 'UP',
      service: 'codesentinel',
    })

    const retryButton = findButton(wrapper, 'Retry')

    expect(retryButton).toBeDefined()
    await retryButton?.trigger('click')
    await flushPromises()

    expect(mockedGetHealth).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Operational')
  })

  it('ignores a stale response that arrives after a newer request', async () => {
    const firstRequest = deferred<HealthResponse>()
    const secondRequest = deferred<HealthResponse>()
    mockedGetHealth
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)

    const wrapper = mount(DashboardView)
    await flushPromises()

    // The header button is disabled while loading, so emit its component
    // event directly to model a refresh that overlaps the in-flight request.
    const refreshButton = wrapper.findAllComponents({ name: 'ElButton' })[0]
    expect(refreshButton).toBeDefined()
    refreshButton?.vm.$emit('click')
    await flushPromises()

    expect(mockedGetHealth).toHaveBeenCalledTimes(2)
    expect(mockedGetHealth.mock.calls[0]?.[0]?.aborted).toBe(true)

    secondRequest.resolve({ status: 'UP', service: 'new-service' })
    await flushPromises()

    expect(wrapper.text()).toContain('Operational')
    expect(wrapper.text()).toContain('new-service')

    firstRequest.resolve({ status: 'DOWN', service: 'stale-service' })
    await flushPromises()

    expect(wrapper.text()).toContain('Operational')
    expect(wrapper.text()).toContain('new-service')
    expect(wrapper.text()).not.toContain('stale-service')
  })

  it('aborts the in-flight request when the component unmounts', async () => {
    const pending = deferred<HealthResponse>()
    mockedGetHealth.mockReturnValueOnce(pending.promise)

    const wrapper = mount(DashboardView)
    await flushPromises()

    const signal = mockedGetHealth.mock.calls[0]?.[0]
    expect(signal?.aborted).toBe(false)

    wrapper.unmount()

    expect(signal?.aborted).toBe(true)
  })

  it.each(['DOWN', 'DEGRADED'])(
    'reports a %s backend status as unavailable',
    async (status) => {
      mockedGetHealth.mockResolvedValue({
        status,
        service: 'codesentinel',
      })

      const wrapper = mount(DashboardView)
      await flushPromises()

      expect(wrapper.find('.status-pill--offline').exists()).toBe(true)
      expect(wrapper.text()).toContain('Unavailable')
      expect(wrapper.text()).toContain('Offline')
      expect(wrapper.text()).toContain(`The API reported status "${status}".`)
    },
  )
})
