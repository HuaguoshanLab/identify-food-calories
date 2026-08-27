import { afterEach, describe, expect, it, vi } from 'vitest'

type BrowserLockManager = {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>
}

const locksDescriptor = Object.getOwnPropertyDescriptor(navigator, 'locks')

afterEach(() => {
  if (locksDescriptor) {
    Object.defineProperty(navigator, 'locks', locksDescriptor)
  } else {
    Reflect.deleteProperty(navigator, 'locks')
  }
  vi.resetModules()
})

describe('refresh coordinator', () => {
  it('serializes refreshes from isolated same-origin tab runtimes', async () => {
    let lockTail = Promise.resolve()
    const locks: BrowserLockManager = {
      request: async (_name, callback) => {
        const previous = lockTail
        let releaseCurrentLock: (() => void) | undefined
        lockTail = new Promise<void>((resolve) => { releaseCurrentLock = resolve })
        await previous
        try {
          return await callback()
        } finally {
          releaseCurrentLock?.()
        }
      },
    }
    Object.defineProperty(navigator, 'locks', { configurable: true, value: locks })

    vi.resetModules()
    const firstTab = await import('./refreshCoordinator')
    vi.resetModules()
    const secondTab = await import('./refreshCoordinator')

    let activeRefreshes = 0
    let maximumConcurrentRefreshes = 0
    let releaseFirstRefresh: (() => void) | undefined
    let signalFirstRefreshStarted: (() => void) | undefined
    const firstRefresh = new Promise<void>((resolve) => { releaseFirstRefresh = resolve })
    const firstRefreshStarted = new Promise<void>((resolve) => { signalFirstRefreshStarted = resolve })
    let operationCount = 0
    const operation = async () => {
      operationCount += 1
      activeRefreshes += 1
      maximumConcurrentRefreshes = Math.max(maximumConcurrentRefreshes, activeRefreshes)
      if (operationCount === 1) {
        signalFirstRefreshStarted?.()
        await firstRefresh
      }
      activeRefreshes -= 1
      return activeRefreshes
    }

    const first = firstTab.coordinateRefresh(operation)
    const second = secondTab.coordinateRefresh(operation)
    await firstRefreshStarted
    releaseFirstRefresh?.()
    await Promise.all([first, second])

    expect(maximumConcurrentRefreshes).toBe(1)
  })
})
