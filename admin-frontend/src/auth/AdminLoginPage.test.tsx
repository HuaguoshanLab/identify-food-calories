import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AdminAuthProvider } from './AdminAuthProvider'
import { AdminLoginPage } from './AdminLoginPage'
import { mswServer } from '@/test/setup'

const apiBase = '/api/v1'

function renderLogin(path = '/admin/login?returnTo=%2Fadmin%2Foverview') {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[path]}><AdminAuthProvider><AdminLoginPage /></AdminAuthProvider></MemoryRouter></QueryClientProvider>)
}

describe('AdminLoginPage', () => {
  it('校验凭据，并且只有公开 login、identity 与 probe 全部成功后才进入后台', async () => {
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
      http.get('/api/v1/admin/probe', ({ request }) => {
        requests.push(new URL(request.url).pathname)
        expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
        return HttpResponse.json({ status: 'ADMIN_ACCESS_GRANTED' })
      }),
    )
    renderLogin()
    await user.click(screen.getByRole('button', { name: '登录后台' }))
    expect(await screen.findByText('请输入有效邮箱地址。')).toBeVisible()

    await user.type(screen.getByLabelText('邮箱'), 'admin@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: '登录后台' }))
    await waitFor(() => expect(requests).toEqual(['/api/v1/auth/login', '/api/v1/users/me', '/api/v1/admin/probe']))
  })

  it('普通账号、过期会话及非后台 returnTo 都不渲染敏感导航', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.post(`${apiBase}/auth/login`, () => HttpResponse.json({ access_token: 'runtime-only-token', token_type: 'bearer', expires_in: 900 })),
      http.get(`${apiBase}/users/me`, () => HttpResponse.json({ id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c', email: 'member@example.com', email_verified_at: '2026-09-03T00:00:00Z', is_active: true, role: 'user' })),
    )
    renderLogin('/admin/login?returnTo=https://attacker.invalid')
    await user.type(screen.getByLabelText('邮箱'), 'member@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: '登录后台' }))
    expect(await screen.findByText('无后台访问权限')).toBeVisible()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByText('runtime-only-token')).not.toBeInTheDocument()
  })
})
