import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from './AuthProvider'
import { SessionList } from './SessionList'
import { useAuth } from './useAuth'

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

function renderSessionList() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SessionList />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function renderIndependentAuthProviders() {
  const firstClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const secondClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  return render(
    <MemoryRouter>
      <QueryClientProvider client={firstClient}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>
      <QueryClientProvider client={secondClient}>
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
      '/api/v1/auth/refresh',
      '/api/v1/users/me',
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
      return new Headers(init?.headers).get('Authorization')?.includes('access-1')
        ? jsonResponse({ error: { code: 'AUTHENTICATION_REQUIRED' } }, 401)
        : jsonResponse({ ok: true })
    })
    const localStorageSetItem = vi.spyOn(Storage.prototype, 'setItem')
    vi.stubGlobal('fetch', fetchMock)

    renderWithAuth()
    await screen.findByText('database@example.com:user')
    fireEvent.click(screen.getByRole('button', { name: '并发请求' }))

    await waitFor(() => expect(refreshCount).toBe(2))
    // Bootstrap and the shared refresh both verify identity through /users/me.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(8))
    expect(localStorageSetItem).not.toHaveBeenCalled()
  })

  it('shares a bootstrap refresh across independent providers', async () => {
    let resolveRefresh: ((response: Response) => void) | undefined
    const pendingRefresh = new Promise<Response>((resolve) => { resolveRefresh = resolve })
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) return pendingRefresh
      if (url.endsWith('/users/me')) {
        return Promise.resolve(jsonResponse({
          id: '00000000-0000-0000-0000-000000000001',
          email: 'database@example.com',
          email_verified_at: null,
          is_active: true,
          role: 'user',
        }))
      }
      return Promise.resolve(jsonResponse({ error: { code: 'UNEXPECTED' } }, 500))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderIndependentAuthProviders()
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'))).toHaveLength(1))
    resolveRefresh?.(jsonResponse({ access_token: 'shared-access', expires_in: 900, token_type: 'bearer' }))

    await waitFor(() => expect(screen.getAllByTestId('identity')).toHaveLength(2))
    for (const identity of screen.getAllByTestId('identity')) {
      expect(identity).toHaveTextContent('database@example.com:user')
    }
  })
})

describe('session management', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses logout for the current session and requires explicit confirmation before revoking another session', async () => {
    const user = (await import('@testing-library/user-event')).default.setup()
    let remoteSessionRevoked = false
    const sessions = [
      {
        id: '00000000-0000-0000-0000-000000000010',
        created_at: '2026-08-01T00:00:00Z',
        last_seen_at: '2026-08-27T00:00:00Z',
        expires_at: '2026-09-01T00:00:00Z',
        revoked_at: null,
        device_label: '当前浏览器',
        is_current: true,
      },
      {
        id: '00000000-0000-0000-0000-000000000011',
        created_at: '2026-08-02T00:00:00Z',
        last_seen_at: '2026-08-26T00:00:00Z',
        expires_at: '2026-09-02T00:00:00Z',
        revoked_at: null,
        device_label: '平板设备',
        is_current: false,
      },
    ]
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) return jsonResponse({ access_token: 'access', expires_in: 900, token_type: 'bearer' })
      if (url.endsWith('/users/me')) return jsonResponse({ id: '00000000-0000-0000-0000-000000000001', email: 'database@example.com', email_verified_at: null, is_active: true, role: 'user' })
      if (url.endsWith('/auth/sessions') && init?.method === 'GET') {
        return jsonResponse(sessions.filter((session) => !remoteSessionRevoked || session.is_current))
      }
      if (url.endsWith('/auth/logout')) return new Response(null, { status: 204 })
      if (url.endsWith('/00000000-0000-0000-0000-000000000011') && init?.method === 'DELETE') {
        remoteSessionRevoked = true
        return new Response(null, { status: 204 })
      }
      return jsonResponse({ error: { code: 'UNEXPECTED' } }, 500)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderSessionList()

    const revokeButton = await screen.findByRole('button', { name: '撤销会话' })
    expect(screen.getByRole('button', { name: '退出当前设备' })).toBeInTheDocument()
    await user.click(revokeButton)
    expect(screen.getByRole('heading', { name: '撤销这个登录会话？' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '保留这个会话' }))
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('/00000000-0000-0000-0000-000000000011') && init?.method === 'DELETE')).toBe(false)

    await user.click(revokeButton)
    await user.keyboard('{Escape}')
    expect(revokeButton).toHaveFocus()

    await user.click(revokeButton)
    await user.click(screen.getByRole('button', { name: '撤销这个会话' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('/00000000-0000-0000-0000-000000000011') && init?.method === 'DELETE')).toBe(true))
    expect(await screen.findByRole('status')).toHaveTextContent('登录会话已撤销。')
    await waitFor(() => expect(screen.queryByRole('button', { name: '撤销会话' })).not.toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: '退出当前设备' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/auth/logout'))).toBe(true))
  })
})
