type BrowserLockManager = {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>
}

const refreshLockName = 'food-agent-refresh'
let pageRefreshFlight: Promise<unknown> | undefined

function browserLocks(): BrowserLockManager | undefined {
  if (typeof navigator === 'undefined') {
    return undefined
  }
  return (navigator as Navigator & { locks?: BrowserLockManager }).locks
}

async function runWithBrowserRefreshLock<T>(operation: () => Promise<T>): Promise<T> {
  const locks = browserLocks()
  if (!locks) {
    return operation()
  }
  // Refresh material is a shared HttpOnly cookie. Serializing its rotation across
  // same-origin tabs prevents a legitimate bootstrap race from resembling replay.
  return locks.request(refreshLockName, operation)
}

export function coordinateRefresh<T>(operation: () => Promise<T>): Promise<T> {
  if (pageRefreshFlight) {
    return pageRefreshFlight as Promise<T>
  }

  const flight = runWithBrowserRefreshLock(operation).finally(() => {
    pageRefreshFlight = undefined
  })
  pageRefreshFlight = flight
  return flight
}
