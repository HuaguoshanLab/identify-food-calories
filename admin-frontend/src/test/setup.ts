import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

export const mswServer = setupServer()

beforeAll(() => {
  mswServer.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  cleanup()
  mswServer.resetHandlers()
  vi.restoreAllMocks()
})

afterAll(() => {
  mswServer.close()
})
