import { http, HttpResponse } from 'msw'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AdminAuthProvider, useAdminAuth } from '@/auth/AdminAuthProvider'
import { mswServer } from '@/test/setup'

import { AdminRouteGuard } from '@/auth/AdminRouteGuard'
import { RuntimeConfigSummaryPage } from './ConfigSummaryPage'

const apiBase = '/api/v1/admin'

const runtimeConfig = {
  id: '1d13dce6-5ca0-4a4d-8e4e-0bd3f2121410',
  version: 2,
  provider: 'deepseek',
  model_alias: 'deepseek-v4-flash',
  enabled: true,
  single_call_cap_usd: '0.02',
  period_cap_usd: '12',
  input_usd_per_m: '0.14',
  output_usd_per_m: '0.28',
  created_at: '2026-09-03T05:00:00Z',
}

function renderConfigPage() {
  const onSessionExpired = vi.fn()
  render(<RuntimeConfigSummaryPage accessToken="runtime-only-token" onSessionExpired={onSessionExpired} />)
  return { onSessionExpired }
}

function EstablishAdminSession() {
  const { establishSession } = useAdminAuth()
  useEffect(() => {
    establishSession({ accessToken: 'runtime-only-token', identity: { id: '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c' } })
  }, [establishSession])
  return null
}

function GuardFixture({ queryClient }: Readonly<{ queryClient: QueryClient }>) {
  return <QueryClientProvider client={queryClient}>
    <MemoryRouter initialEntries={['/admin/model-configs']}>
      <AdminAuthProvider>
        <SessionReadyRoutes />
      </AdminAuthProvider>
    </MemoryRouter>
  </QueryClientProvider>
}

function SessionReadyRoutes() {
  const [ready, setReady] = useState(false)
  return <><EstablishAdminSession />{ready ? <Routes>
    <Route path="/admin/login" element={<h1>后台登录</h1>} />
    <Route path="/admin/model-configs" element={<AdminRouteGuard><h1>受保护配置</h1></AdminRouteGuard>} />
    <Route path="/admin/forbidden" element={<h1>无后台访问权限</h1>} />
  </Routes> : <ReadySignal onReady={() => setReady(true)} />}</>
}

function ReadySignal({ onReady }: Readonly<{ onReady: () => void }>) {
  useEffect(onReady, [onReady])
  return null
}

describe('AdminRouteGuard 与 RuntimeConfigSummaryPage', () => {
  it('probe 成功后才渲染嵌套路由；401 清除会话和 Query cache，403 固定拒绝', async () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(['admin', 'private'], { title: '不应残留' })
    mswServer.use(http.get(`${apiBase}/probe`, ({ request }) => {
      expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
      return HttpResponse.json({ status: 'ADMIN_ACCESS_GRANTED' })
    }))
    render(<GuardFixture queryClient={queryClient} />)
    expect(screen.queryByRole('heading', { name: '受保护配置' })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '受保护配置' })).toBeVisible()

    mswServer.use(http.get(`${apiBase}/probe`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })))
    cleanup()
    render(<GuardFixture queryClient={queryClient} />)
    expect(await screen.findByRole('heading', { name: '后台登录' })).toBeVisible()
    expect(queryClient.getQueryData(['admin', 'private'])).toBeUndefined()

    mswServer.use(http.get(`${apiBase}/probe`, () => HttpResponse.json({ error: { code: 'ADMIN_PERMISSION_REQUIRED' } }, { status: 403 })))
    cleanup()
    render(<GuardFixture queryClient={new QueryClient()} />)
    expect(await screen.findByRole('heading', { name: '无后台访问权限' })).toBeVisible()
  })

  it('严格展示非密钥配置，键盘跳过链接聚焦主内容，并以理由、确认、If-Match 和幂等键提交', async () => {
    const user = userEvent.setup()
    let release: (() => void) | undefined
    mswServer.use(
      http.get(`${apiBase}/runtime-config`, () => HttpResponse.json(runtimeConfig)),
      http.post(`${apiBase}/runtime-config`, async ({ request }) => {
        expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
        expect(request.headers.get('Idempotency-Key')).toHaveLength(36)
        expect(request.headers.get('If-Match')).toBe('2')
        expect(await request.json()).toEqual({
          provider: 'deepseek', model_alias: 'deepseek-v4-flash', enabled: false,
          single_call_cap_usd: '0.02', period_cap_usd: '12', input_usd_per_m: '0.14', output_usd_per_m: '0.28',
          reason: '事故处置，暂停后续调用', confirm: true,
        })
        await new Promise<void>((resolve) => { release = resolve })
        return HttpResponse.json({ ...runtimeConfig, version: 3, enabled: false }, { status: 201 })
      }),
    )
    renderConfigPage()
    expect(await screen.findByText('配置版本 v2')).toBeVisible()
    expect(screen.queryByText(/api_key|endpoint|runtime-only-token/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: '跳到主要内容' }))
    expect(screen.getByRole('main')).toHaveFocus()
    await user.click(screen.getByRole('button', { name: '变更未来配置' }))
    const dialog = await screen.findByRole('alertdialog', { name: '确认变更未来运行配置？' })
    expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus()
    await user.click(within(dialog).getByRole('checkbox', { name: '启用新的运行配置' }))
    await user.type(within(dialog).getByLabelText('变更原因'), '事故处置，暂停后续调用')
    const confirm = within(dialog).getByRole('button', { name: '确认保存未来配置' })
    await user.click(confirm)
    expect(confirm).toBeDisabled()
    release?.()
    expect(await screen.findByText('配置版本 v3')).toBeVisible()
  })

  it('409 保留编辑；401/403 不渲染配置缓存', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.get(`${apiBase}/runtime-config`, () => HttpResponse.json(runtimeConfig)),
      http.post(`${apiBase}/runtime-config`, () => HttpResponse.json({ detail: 'conflict' }, { status: 409 })),
    )
    renderConfigPage()
    await screen.findByText('配置版本 v2')
    await user.click(screen.getByRole('button', { name: '变更未来配置' }))
    const dialog = await screen.findByRole('alertdialog')
    await user.type(within(dialog).getByLabelText('变更原因'), '并发变更需要重新审阅')
    await user.click(within(dialog).getByRole('button', { name: '确认保存未来配置' }))
    expect(await screen.findByText('配置已被其他管理员更新；你的编辑仍保留，请重新核对后再确认。')).toBeVisible()
    expect(within(await screen.findByRole('alertdialog')).getByLabelText('变更原因')).toHaveValue('并发变更需要重新审阅')

    cleanup()
    mswServer.use(http.get(`${apiBase}/runtime-config`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })))
    const { onSessionExpired } = renderConfigPage()
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce())
    expect(screen.queryByText('配置版本 v2')).not.toBeInTheDocument()

    cleanup()
    mswServer.use(http.get(`${apiBase}/runtime-config`, () => HttpResponse.json({ error: { code: 'ADMIN_PERMISSION_REQUIRED' } }, { status: 403 })))
    renderConfigPage()
    expect(await screen.findByRole('heading', { name: '无后台访问权限' })).toBeVisible()
    expect(screen.queryByText('配置版本 v2')).not.toBeInTheDocument()
  })
})
