import { StrictMode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { mswServer } from '@/test/setup'
import { AdminAuthProvider, useAdminAuth } from './AdminAuthProvider'
import { AdminRouteGuard } from './AdminRouteGuard'

const me = { id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c', email: 'admin@example.test', email_verified_at: '2026-09-03T00:00:00Z', is_active: true, role: 'admin' }
const access = { access_token: 'restored-token', token_type: 'bearer', expires_in: 900 }
function Location() { return <output data-testid="path">{useLocation().pathname}{useLocation().search}</output> }
function Clear() { const { clearSession } = useAdminAuth(); return <button onClick={clearSession}>清空会话</button> }
function setup() {
  const client = new QueryClient()
  render(<StrictMode><QueryClientProvider client={client}><MemoryRouter initialEntries={['/admin/catalog?view=current']}><AdminAuthProvider><Clear /><Location /><Routes>
    <Route path="/admin/catalog" element={<AdminRouteGuard><h1>私有目录</h1></AdminRouteGuard>} />
    <Route path="/admin/login" element={<h1>登录页</h1>} />
    <Route path="/admin/forbidden" element={<h1>无权限</h1>} />
  </Routes></AdminAuthProvider></MemoryRouter></QueryClientProvider></StrictMode>)
  return client
}

describe('后台刷新恢复', () => {
  it('慢恢复不提前跳登录；StrictMode 仅轮换一次，身份与权限验证后保留原路径', async () => {
    let release: (() => void) | undefined
    const requests: string[] = []
    const persisted = vi.spyOn(Storage.prototype, 'setItem')
    mswServer.use(http.post('/api/v1/auth/refresh', async ({ request }) => {
      requests.push('refresh'); expect(request.credentials).toBe('include')
      await new Promise<void>(resolve => { release = resolve })
      return HttpResponse.json(access)
    }), http.get('/api/v1/users/me', ({ request }) => {
      requests.push('me'); expect(request.headers.get('Authorization')).toBe('Bearer restored-token'); return HttpResponse.json(me)
    }), http.get('/api/v1/admin/probe', () => { requests.push('probe'); return HttpResponse.json({ status: 'ADMIN_ACCESS_GRANTED' }) }))
    setup()
    await waitFor(() => expect(release).toBeDefined())
    expect(screen.getByTestId('path')).toHaveTextContent('/admin/catalog?view=current')
    expect(screen.queryByText('私有目录')).not.toBeInTheDocument()
    expect(screen.queryByText('登录页')).not.toBeInTheDocument()
    release?.()
    expect(await screen.findByText('私有目录')).toBeVisible()
    expect(requests).toEqual(['refresh', 'me', 'probe'])
    expect(persisted).not.toHaveBeenCalled()
  })

  it('无刷新凭据才回登录，并保留 returnTo', async () => {
    setup()
    expect(await screen.findByText('登录页')).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent('/admin/login?returnTo=%2Fadmin%2Fcatalog%3Fview%3Dcurrent')
  })

  it('恢复普通账号仍须通过数据库角色 probe，403 不展示后台', async () => {
    mswServer.use(http.post('/api/v1/auth/refresh', () => HttpResponse.json(access)),
      http.get('/api/v1/users/me', () => HttpResponse.json({ ...me, role: 'user' })),
      http.get('/api/v1/admin/probe', () => HttpResponse.json({}, { status: 403 })))
    setup()
    expect(await screen.findByText('无权限')).toBeVisible()
    expect(screen.queryByText('私有目录')).not.toBeInTheDocument()
  })

  it('清空会话后迟到的恢复响应不能重新登录', async () => {
    const user = userEvent.setup()
    let release: (() => void) | undefined
    mswServer.use(http.post('/api/v1/auth/refresh', async () => { await new Promise<void>(resolve => { release = resolve }); return HttpResponse.json(access) }),
      http.get('/api/v1/users/me', () => HttpResponse.json(me)))
    setup()
    await waitFor(() => expect(release).toBeDefined())
    await user.click(screen.getByText('清空会话'))
    await screen.findByText('登录页')
    release?.()
    await waitFor(() => expect(screen.getByText('登录页')).toBeVisible())
    expect(screen.queryByText('私有目录')).not.toBeInTheDocument()
  })
})
