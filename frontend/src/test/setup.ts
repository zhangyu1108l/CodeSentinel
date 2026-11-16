import { vi } from 'vitest'

Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: vi.fn<() => void>(),
})

if (typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string): MediaQueryList =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>(() => false),
      }) as unknown as MediaQueryList,
  })
}

if (!('ResizeObserver' in globalThis)) {
  class ResizeObserverMock {
    observe(): void {
      // Layout observation is not needed in jsdom.
    }

    unobserve(): void {
      // Layout observation is not needed in jsdom.
    }

    disconnect(): void {
      // Layout observation is not needed in jsdom.
    }
  }

  Object.defineProperty(globalThis, 'ResizeObserver', {
    writable: true,
    value: ResizeObserverMock,
  })
}
