import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { useEffect, useState } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'

import { AdminAuthProvider, useAdminAuth } from './AdminAuthProvider'
import { AdminRouteGuard } from './AdminRouteGuard'
import { mswServer } from '@/test/setup'

const apiBase = '/api/v1/admin'
const identity = { id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c' }

function EstablishAdminSession() {
  const { establishSession } = useAdminAuth()
  useEffect(() => {
    establishSession({ accessToken: 'runtime-only-token', identity })
  }, [establishSession])
  return null
}

function SessionProbe() {
  const { accessToken, identity: currentIdentity } = useAdminAuth()
  return <output data-testid="guard-session">{JSON.stringify({ accessToken, identity: currentIdentity })}</output>
}

function GuardFixture({ queryClient, establishSession = true }: Readonly<{ queryClient: QueryClient, establishSession?: boolean }>) {
  return <QueryClientProvider client={queryClient}>
    <MemoryRouter initialEntries={['/admin/overview']}>
      <AdminAuthProvider>
        <SessionReadyRoutes establishSession={establishSession} />
      </AdminAuthProvider>
    </MemoryRouter>
  </QueryClientProvider>
}

function SessionReadyRoutes({ establishSession }: Readonly<{ establishSession: boolean }>) {
  const [ready, setReady] = useState(!establishSession)
  return <>
    {establishSession ? <EstablishAdminSession /> : null}
    <SessionProbe />
    {ready ? <Routes>
      <Route path="/admin/login" element={<h1>后台登录</h1>} />
      <Route path="/admin/forbidden" element={<h1>无后台访问权限</h1>} />
      <Route path="/admin/overview" element={<AdminRouteGuard><section><h1>私有概览</h1><p>私有缓存</p></section></AdminRouteGuard>} />
    </Routes> : <ReadySignal onReady={() => setReady(true)} />}
  </>
}

function ReadySignal({ onReady }: Readonly<{ onReady: () => void }>) {
  useEffect(onReady, [onReady])
  return null
}

describe('AdminRouteGuard', () => {
  it('只在严格 Bearer probe 成功后渲染私有 children', async () => {
    const queryClient = new QueryClient()
    mswServer.use(http.get(`${apiBase}/probe`, ({ request }) => {
      expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
      return HttpResponse.json({ status: 'ADMIN_ACCESS_GRANTED' })
    }))

    render(<GuardFixture queryClient={queryClient} />)
    expect(screen.queryByRole('heading', { name: '私有概览' })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '私有概览' })).toBeVisible()
  })

  it('403 清空会话与 Query cache、replace 到 forbidden，且从不渲染私有内容', async () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(['admin', 'private'], { title: '不应残留' })
    mswServer.use(http.get(`${apiBase}/probe`, () => HttpResponse.json({ error: { code: 'ADMIN_PERMISSION_REQUIRED' } }, { status: 403 })))

    render(<GuardFixture queryClient={queryClient} />)
    expect(screen.queryByRole('heading', { name: '私有概览' })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '无后台访问权限' })).toBeVisible()
    expect(queryClient.getQueryData(['admin', 'private'])).toBeUndefined()
    expect(screen.getByTestId('guard-session')).toHaveTextContent('{}')
    expect(screen.queryByText('私有缓存')).not.toBeInTheDocument()
  })

  it('401、无 token、网络失败或无效 probe DTO 都清空 cache 并 fail closed 到 login，且不调用持久化 API', async () => {
    const storageSetItem = vi.spyOn(Storage.prototype, 'setItem')
    const queryClient = new QueryClient()
    queryClient.setQueryData(['admin', 'private'], { title: '不应残留' })
    mswServer.use(http.get(`${apiBase}/probe`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })))

    const first = render(<GuardFixture queryClient={queryClient} />)
    expect(await screen.findByRole('heading', { name: '后台登录' })).toBeVisible()
    expect(queryClient.getQueryData(['admin', 'private'])).toBeUndefined()
    expect(storageSetItem).not.toHaveBeenCalled()

    first.unmount()
    const noTokenCache = new QueryClient()
    noTokenCache.setQueryData(['admin', 'private'], { title: '不应残留' })
    render(<GuardFixture establishSession={false} queryClient={noTokenCache} />)
    expect(await screen.findByRole('heading', { name: '后台登录' })).toBeVisible()
    await waitFor(() => expect(noTokenCache.getQueryData(['admin', 'private'])).toBeUndefined())
    expect(storageSetItem).not.toHaveBeenCalled()
  })

  it('严格拒绝额外 probe 字段并安全返回 login', async () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(['admin', 'private'], { title: '不应残留' })
    mswServer.use(http.get(`${apiBase}/probe`, () => HttpResponse.json({ status: 'ADMIN_ACCESS_GRANTED', role: 'admin' })))

    render(<GuardFixture queryClient={queryClient} />)
    expect(await screen.findByRole('heading', { name: '后台登录' })).toBeVisible()
    expect(queryClient.getQueryData(['admin', 'private'])).toBeUndefined()
    expect(screen.queryByRole('heading', { name: '私有概览' })).not.toBeInTheDocument()
  })
})
