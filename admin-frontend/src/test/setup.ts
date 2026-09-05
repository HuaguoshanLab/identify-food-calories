import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { http, HttpResponse } from 'msw'

export const mswServer = setupServer(http.post('/api/v1/auth/refresh', () => HttpResponse.json({}, { status: 401 })))

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
