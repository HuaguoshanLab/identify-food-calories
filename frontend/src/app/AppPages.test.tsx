import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { TabHeader } from '@/layouts/TabHeader'
import { routePaths } from '@/routePaths'

import { AccountDetailsPage } from './AccountDetailsPage'
import { MePage } from './MePage'
import { PlaceholderTabPage } from './PlaceholderTabPage'
import { SessionsDetailsPage } from './SessionsDetailsPage'

function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(true),
    request: vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })),
    retryBootstrap: vi.fn(),
    status: 'authenticated',
    user: {
      email: 'database@example.com',
      email_verified_at: '2026-08-27T00:00:00Z',
      id: '00000000-0000-0000-0000-000000000001',
      is_active: true,
      role: 'user',
    },
    ...overrides,
  }
}

describe('honest placeholder tab pages', () => {
  it.each(['分析', '记录', '计划'] as const)('renders only the locked %s status', (title) => {
    render(
      <MemoryRouter>
        <PlaceholderTabPage title={title} />
      </MemoryRouter>,
    )

    const heading = screen.getByRole('heading', { level: 1, name: title })
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('功能即将开放')).toBeInTheDocument()
    expect(heading).toHaveFocus()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/上传|加载|骨架/i)).not.toBeInTheDocument()
  })
})

describe('account and session detail content', () => {
  it('maps only database-authoritative account fields to readonly Chinese details', () => {
    render(
      <AuthContext.Provider value={createAuthValue({ user: { ...createAuthValue().user!, role: 'admin' } })}>
        <AccountDetailsPage />
      </AuthContext.Provider>,
    )

    expect(screen.getByText('邮箱')).toBeInTheDocument()
    expect(screen.getByText('database@example.com')).toHaveClass('break-all')
    expect(screen.getByText('账号状态')).toBeInTheDocument()
    expect(screen.getByText('正常')).toBeInTheDocument()
    expect(screen.getByText('角色')).toBeInTheDocument()
    expect(screen.getByText('管理员')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /编辑|保存|修改|上传/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('reuses SessionList as the only session-query owner', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify([
      {
        created_at: '2026-08-01T00:00:00Z',
        device_label: '当前浏览器',
        expires_at: '2026-09-01T00:00:00Z',
        id: '00000000-0000-0000-0000-000000000010',
        is_current: true,
        last_seen_at: '2026-08-27T00:00:00Z',
        revoked_at: null,
      },
    ]), { status: 200 }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={createAuthValue({ request })}>
          <SessionsDetailsPage />
        </AuthContext.Provider>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('heading', { level: 2, name: '登录会话' })).toBeInTheDocument()
    expect(await screen.findByText('暂无其他登录会话')).toBeInTheDocument()
    expect(request).toHaveBeenCalledTimes(1)
    expect(request).toHaveBeenCalledWith('/auth/sessions', { method: 'GET' })
  })

  it('keeps an empty session response visibly recoverable instead of pretending it is current-only', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={createAuthValue({ request })}>
          <SessionsDetailsPage />
        </AuthContext.Provider>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('暂时没有可显示的登录会话。')).toBeInTheDocument()
    expect(screen.queryByText('暂无其他登录会话')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新尝试' })).toBeInTheDocument()
    expect(request).toHaveBeenCalledWith('/auth/sessions', { method: 'GET' })
  })
})

describe('my settings root page', () => {
  it('focuses the shell heading when my is mounted', () => {
    render(
      <MemoryRouter initialEntries={[routePaths.me]}>
        <TabHeader />
        <AuthContext.Provider value={createAuthValue()}><MePage /></AuthContext.Provider>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: '我的' })).toHaveFocus()
  })

  it('adds exactly one profile settings link and keeps keyboard navigation native', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[routePaths.me]}>
        <TabHeader />
        <AuthContext.Provider value={createAuthValue()}><MePage /></AuthContext.Provider>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: '我的' })).toBeInTheDocument()
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(4)
    expect(screen.getByRole('link', { name: /个人资料/ })).toHaveAttribute('href', routePaths.profile)
    expect(screen.getByRole('link', { name: /账号资料/ })).toHaveAttribute('href', routePaths.account)
    expect(screen.getByRole('link', { name: /登录会话/ })).toHaveAttribute('href', routePaths.sessions)
    expect(screen.getByText('database@example.com')).toBeInTheDocument()
    expect(screen.getByText('普通用户')).toBeInTheDocument()
    expect(screen.getByText('账号正常')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /退出|保存|编辑/i })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /饮食偏好与记忆/ })).toHaveAttribute('href', '/app/me/memories')

    for (const link of links) {
      expect(link.querySelectorAll('svg')).toHaveLength(2)
    }

    await user.tab()
    expect(screen.getByRole('link', { name: /个人资料/ })).toHaveFocus()
  })
})
