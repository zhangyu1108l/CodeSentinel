import { describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { createAppRouter } from '@/router'

describe('application routes', () => {
  it('resolves the dashboard route', () => {
    const router = createAppRouter(createMemoryHistory())

    expect(router.resolve('/').name).toBe('dashboard')
    expect(router.resolve('/').meta.title).toBe('Dashboard')
  })

  it('resolves the review history route', () => {
    const router = createAppRouter(createMemoryHistory())

    expect(router.resolve('/reviews').name).toBe('review-history')
    expect(router.resolve('/reviews').meta.title).toBe('Review History')
  })

  it('resolves a numeric review detail route', () => {
    const router = createAppRouter(createMemoryHistory())

    expect(router.resolve('/reviews/7').name).toBe('review-detail')
    expect(router.resolve('/reviews/7').meta.title).toBe('Review Detail')
  })

  it('resolves the review insights route', () => {
    const router = createAppRouter(createMemoryHistory())

    expect(router.resolve('/insights').name).toBe('insights')
    expect(router.resolve('/insights').meta.title).toBe('Review Insights')
  })

  it('keeps non-numeric review subpaths on the not-found route', () => {
    const router = createAppRouter(createMemoryHistory())

    expect(router.resolve('/reviews/missing-entry').name).toBe('not-found')
  })

  it('falls back to the not-found route', () => {
    const router = createAppRouter(createMemoryHistory())

    expect(router.resolve('/missing/page').name).toBe('not-found')
  })
})
