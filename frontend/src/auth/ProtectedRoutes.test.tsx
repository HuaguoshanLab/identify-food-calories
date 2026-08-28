import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { AuthProvider } from './AuthProvider'
import { RequireAuthentication } from './RouteGuards'
import { parseReturnTo } from './returnTo'

function renderApp(initialEntry: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('protected user routes', () => {
  afterEach(() => vi.unstubAllGlobals())

  it.each(['https://attacker.example/app', '//attacker.example/app', '/login', '/unknown', '/app#fragment'])(
    'falls back from unsafe returnTo %s',
    (returnTo) => {
      expect(parseReturnTo(returnTo)).toBe('/app')
    },
  )

  it.each([
    '/app',
    '/app/analyze',
    '/app/records',
    '/app/plans',
    '/app/me',
    '/app/me/account',
    '/app/me/sessions',
    '/app/me/sessions?source=login',
  ])('keeps the exact registered deep link %s for login completion', (returnTo) => {
    expect(parseReturnTo(returnTo)).toBe(returnTo)
  })

  it.each(['/app/admin', '/application', '/app/me/unknown', '/app/analyze/extra', '/app\\admin'])(
    'falls back from an unregistered path that resembles a protected route: %s',
    (returnTo) => {
      expect(parseReturnTo(returnTo)).toBe('/app')
    },
  )

  it('preserves the registered protected deep link and redirects unauthenticated visitors to login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'AUTHENTICATION_REQUIRED' } }), { status: 401 })))
    renderApp('/app?tab=sessions')

    expect(await screen.findByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '创建账号' })).toHaveAttribute('href', '/register')
  })

  it('does not register an admin page in the user H5', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
    renderApp('/admin')

    expect(screen.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' })).toBeInTheDocument()
    expect(screen.queryByText(/admin/i)).not.toBeInTheDocument()
  })

  it('returns to the registered protected route after database-authoritative login', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) {
        return new Response(JSON.stringify({ error: { code: 'AUTHENTICATION_REQUIRED' } }), { status: 401 })
      }
      if (url.endsWith('/auth/login')) {
        return new Response(JSON.stringify({ access_token: 'runtime-only-access', expires_in: 900, token_type: 'bearer' }))
      }
      if (url.endsWith('/users/me')) {
        return new Response(JSON.stringify({ id: '00000000-0000-0000-0000-000000000001', email: 'database@example.com', email_verified_at: null, is_active: true, role: 'user' }))
      }
      if (url.endsWith('/auth/sessions')) {
        return new Response(JSON.stringify([]))
      }
      return new Response(JSON.stringify({ error: { code: 'UNEXPECTED' } }), { status: 500 })
    }))
    renderApp('/login?returnTo=%2Fapp%3Ftab%3Dsessions')

    await user.type(await screen.findByLabelText('邮箱'), 'mina@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: '登录并继续' }))

    expect(await screen.findByRole('heading', { name: '账号与会话' })).toBeInTheDocument()
    expect(screen.getByText('database@example.com')).toBeInTheDocument()
  })

  it('renders nested protected routes through the guard Outlet after identity recovery', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) {
        return new Response(JSON.stringify({ access_token: 'runtime-only-access', expires_in: 900, token_type: 'bearer' }))
      }
      if (url.endsWith('/users/me')) {
        return new Response(JSON.stringify({ id: '00000000-0000-0000-0000-000000000001', email: 'database@example.com', email_verified_at: null, is_active: true, role: 'user' }))
      }
      return new Response(JSON.stringify({ error: { code: 'UNEXPECTED' } }), { status: 500 })
    }))

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <MemoryRouter initialEntries={['/app/test']}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <Routes>
              <Route element={<RequireAuthentication />}>
                <Route path="/app/test" element={<h1>受保护的嵌套路由</h1>} />
              </Route>
            </Routes>
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '受保护的嵌套路由' })).toBeInTheDocument()
  })
})
