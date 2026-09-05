import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AdminAuthProvider, useAdminAuth } from './AdminAuthProvider'
import { AdminLoginPage } from './AdminLoginPage'
import { mswServer } from '@/test/setup'

const apiBase = '/api/v1'

function renderLogin(path = '/admin/login?returnTo=%2Fadmin%2Foverview') {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <AdminAuthProvider>
          <AdminLoginPage />
          <SessionProbe />
        </AdminAuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function SessionProbe() {
  const { accessToken, identity } = useAdminAuth()
  const location = useLocation()
  return <output data-testid="admin-login-session">{JSON.stringify({ accessToken, identity, path: location.pathname })}</output>
}

describe('AdminLoginPage', () => {
  it('只以公开 login 与 active identity 建立内存 token/ID 交接，并 replace 到安全后台 returnTo', async () => {
    const user = userEvent.setup()
    const requests: string[] = []
    mswServer.use(
      http.post(`${apiBase}/auth/login`, async ({ request }) => {
        requests.push(new URL(request.url).pathname)
        expect(await request.json()).toEqual({ email: 'admin@example.com', password: 'correct-horse-battery' })
        return HttpResponse.json({ access_token: 'runtime-only-token', token_type: 'bearer', expires_in: 900 })
      }),
      http.get(`${apiBase}/users/me`, ({ request }) => {
        requests.push(new URL(request.url).pathname)
        expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
        return HttpResponse.json({ id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c', email: 'admin@example.com', email_verified_at: '2026-09-03T00:00:00Z', is_active: true, role: 'admin' })
      }),
    )
    renderLogin()
    await screen.findByRole('button', { name: '登录后台' })
    await user.click(screen.getByRole('button', { name: '登录后台' }))
    expect(await screen.findByText('请输入有效邮箱地址。')).toBeVisible()

    await user.type(screen.getByLabelText('邮箱'), 'admin@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: '登录后台' }))
    await waitFor(() => expect(requests).toEqual(['/api/v1/auth/login', '/api/v1/users/me']))
    expect(screen.getByTestId('admin-login-session')).toHaveTextContent(JSON.stringify({
      accessToken: 'runtime-only-token',
      identity: { id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c' },
      path: '/admin/overview',
    }))
  })

  it('active user 与 active admin 一样只完成认证交接，guard 才决定后台访问', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.post(`${apiBase}/auth/login`, () => HttpResponse.json({ access_token: 'runtime-only-token', token_type: 'bearer', expires_in: 900 })),
      http.get(`${apiBase}/users/me`, () => HttpResponse.json({ id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c', email: 'member@example.com', email_verified_at: '2026-09-03T00:00:00Z', is_active: true, role: 'user' })),
    )
    renderLogin('/admin/login?returnTo=%2Fadmin%2Fcatalog')
    await screen.findByLabelText('邮箱')
    await user.type(screen.getByLabelText('邮箱'), 'member@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: '登录后台' }))
    await waitFor(() => expect(screen.getByTestId('admin-login-session')).toHaveTextContent(JSON.stringify({
      accessToken: 'runtime-only-token',
      identity: { id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c' },
      path: '/admin/catalog',
    })))
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByText('runtime-only-token')).not.toBeInTheDocument()
  })

  it('inactive identity、malformed identity 与不安全 returnTo 都留在登录安全路径', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.post(`${apiBase}/auth/login`, () => HttpResponse.json({ access_token: 'runtime-only-token', token_type: 'bearer', expires_in: 900 })),
      http.get(`${apiBase}/users/me`, () => HttpResponse.json({ id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c', email: 'member@example.com', email_verified_at: '2026-09-03T00:00:00Z', is_active: false, role: 'user' })),
    )
    renderLogin('/admin/login?returnTo=https://attacker.invalid')
    await screen.findByLabelText('邮箱')
    await user.type(screen.getByLabelText('邮箱'), 'member@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: '登录后台' }))

    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.getByTestId('admin-login-session')).toHaveTextContent(JSON.stringify({ path: '/admin/login' }))
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})
