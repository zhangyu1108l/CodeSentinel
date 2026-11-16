import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import DashboardLayout from '@/layouts/DashboardLayout.vue'
import { createAppRouter } from '@/router'

function mockViewport(matches: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches,
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>(() => false),
      }) as unknown as MediaQueryList,
  )
}

async function mountLayout(path = '/') {
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()

  const wrapper = mount(DashboardLayout, {
    global: {
      plugins: [router],
      stubs: {
        RouterView: true,
      },
    },
  })

  await flushPromises()
  return { wrapper, router }
}

describe('DashboardLayout', () => {
  it('renders the brand, navigation, and active page title', async () => {
    const { wrapper } = await mountLayout('/reviews')

    expect(wrapper.text()).toContain('CodeSentinel')
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Review History')
    expect(wrapper.text()).toContain('Review Insights')
    expect(wrapper.text()).toContain('Phase 11.1')
    expect(wrapper.find('.breadcrumb__current').text()).toBe('Review History')
  })

  it('highlights Review Insights on the insights route', async () => {
    const { wrapper } = await mountLayout('/insights')

    expect(wrapper.get('.el-menu-item.is-active').text()).toContain(
      'Review Insights',
    )
    expect(wrapper.find('.breadcrumb__current').text()).toBe('Review Insights')
  })

  it('exposes the sidebar state through the desktop toggle', async () => {
    const { wrapper } = await mountLayout()

    const toggle = wrapper.get('.sidebar-toggle')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(toggle.attributes('aria-controls')).toBe('app-sidebar')

    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.attributes('aria-expanded')).toBe('false')
  })

  it('gives the mobile drawer an accessible name and a close button', async () => {
    mockViewport(true)
    const { wrapper } = await mountLayout()

    const toggle = wrapper.get('.sidebar-toggle')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.attributes('aria-controls')).toBe('mobile-navigation-drawer')

    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.attributes('aria-expanded')).toBe('true')

    const drawer = wrapper.get('[role="dialog"]')
    expect(drawer.attributes('aria-label')).toBe('Navigation')

    const closeButton = wrapper.get('[aria-label="Close navigation"]')
    await closeButton.trigger('click')
    await flushPromises()

    expect(toggle.attributes('aria-expanded')).toBe('false')
  })

  it('closes the mobile drawer when the route changes', async () => {
    mockViewport(true)
    const { wrapper, router } = await mountLayout()

    const toggle = wrapper.get('.sidebar-toggle')
    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.attributes('aria-expanded')).toBe('true')

    await router.push('/reviews')
    await flushPromises()

    expect(toggle.attributes('aria-expanded')).toBe('false')
  })
})
