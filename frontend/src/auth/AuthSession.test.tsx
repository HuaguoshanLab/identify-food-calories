import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider, useAuth } from './AuthProvider'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function AuthProbe() {
  const auth = useAuth()

  return (
    <>
      <p data-testid="status">{auth.status}</p>
      <p data-testid="identity">{auth.user?.email ?? 'none'}:{auth.user?.role ?? 'none'}</p>
      <button onClick={() => void Promise.all([auth.request('/protected'), auth.request('/protected')])} type="button">
        并发请求
      </button>
    </>
  )
}

function renderWithAuth() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('authentication session bootstrap', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('refreshes before loading the database-authoritative current user', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) {
        return jsonResponse({ access_token: 'header.claims.are.untrusted', expires_in: 900, token_type: 'bearer' })
      }
      expect(init?.headers).toMatchObject({ Authorization: 'Bearer header.claims.are.untrusted' })
      return jsonResponse({
        id: '00000000-0000-0000-0000-000000000001',
        email: 'database@example.com',
        email_verified_at: '2026-08-27T00:00:00Z',
        is_active: true,
        role: 'admin',
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    renderWithAuth()

    expect(await screen.findByTestId('identity')).toHaveTextContent('database@example.com:admin')
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      'http://127.0.0.1:8000/api/v1/auth/refresh',
      'http://127.0.0.1:8000/api/v1/users/me',
    ])
  })

  it('shares one refresh for concurrent 401 retries and never persists tokens', async () => {
    let refreshCount = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCount += 1
        return jsonResponse({ access_token: `access-${refreshCount}`, expires_in: 900, token_type: 'bearer' })
      }
      if (url.endsWith('/users/me')) {
        return jsonResponse({
          id: '00000000-0000-0000-0000-000000000001',
          email: 'database@example.com',
          email_verified_at: '2026-08-27T00:00:00Z',
          is_active: true,
          role: 'user',
        })
      }
      return String((init?.headers as HeadersInit | undefined)?.Authorization ?? '').includes('access-1')
        ? jsonResponse({ error: { code: 'AUTHENTICATION_REQUIRED' } }, 401)
        : jsonResponse({ ok: true })
    })
    const localStorageSetItem = vi.spyOn(Storage.prototype, 'setItem')
    vi.stubGlobal('fetch', fetchMock)

    renderWithAuth()
    await screen.findByText('database@example.com:user')
    fireEvent.click(screen.getByRole('button', { name: '并发请求' }))

    await waitFor(() => expect(refreshCount).toBe(2))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7))
    expect(localStorageSetItem).not.toHaveBeenCalled()
  })
})
