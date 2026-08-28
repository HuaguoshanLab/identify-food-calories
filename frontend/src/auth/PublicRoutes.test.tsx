import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { AuthProvider } from './AuthProvider'
import { LandingPage, PrivacyPage, TermsPage } from './PublicPages'
import { PublicAuthLayout } from '../layouts/PublicAuthLayout'

function renderRoute(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider><App /></AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function renderLegalContent(initialEntry: '/privacy' | '/terms') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route element={<PublicAuthLayout mode="entry" />}>
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('public user routes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('keeps landing CTAs as native navigation links without Base UI button warnings', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '创建账号' })).not.toHaveAttribute('data-slot', 'button')
    expect(screen.getByRole('link', { name: '登录' })).not.toHaveAttribute('data-slot', 'button')
    expect(consoleError).not.toHaveBeenCalledWith(
      expect.stringContaining('expected a native <button>'),
    )
  })

  it('keeps landing, legal and account-entry pages public', () => {
    const { container } = renderRoute('/')
    const landingHeading = screen.getByRole('heading', {
      name: '拍下或描述一餐，获得可追问的饮食分析',
    })

    expect(landingHeading).toBeInTheDocument()
    expect(landingHeading).toHaveFocus()
    expect(screen.getByRole('link', { name: '创建账号' })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: '创建账号' })).toHaveClass('bg-primary')
    expect(screen.getByRole('link', { name: '登录' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: '登录' })).toHaveClass('border-border')
    expect(screen.getByRole('link', { name: '查看隐私说明' })).toHaveAttribute('href', '/privacy')
    expect(screen.getByRole('link', { name: '查看使用条款' })).toHaveAttribute('href', '/terms')
    expect(screen.queryByRole('button', { name: /上传|分析|示例|Agent/i })).not.toBeInTheDocument()
    expect(container.querySelector('.min-h-dvh')).not.toBeInTheDocument()

    renderRoute('/privacy')
    expect(screen.getByRole('heading', { name: '隐私说明' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回首页' })).toHaveAttribute('href', '/')

    renderRoute('/terms')
    expect(screen.getByRole('heading', { name: '使用条款' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '返回首页' }).at(-1)).toHaveAttribute('href', '/')
  })

  it('declares authentication entry routes and sends the protected app route to login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'AUTHENTICATION_REQUIRED' } }), { status: 401 })))
    renderRoute('/app?tab=sessions')

    expect(await screen.findByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
    expect(screen.getByText('登录后继续管理你的饮食与登录会话。')).toBeInTheDocument()

    renderRoute('/register')
    expect(screen.getByRole('heading', { name: '创建账号' })).toBeInTheDocument()
    renderRoute('/register/verify')
    expect(screen.getByRole('heading', { name: '验证邮箱' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '返回上一步' }).at(-1)).toHaveAttribute('href', '/register')
    renderRoute('/forgot-password')
    expect(screen.getByRole('heading', { name: '忘记密码' })).toBeInTheDocument()
    renderRoute('/reset-password')
    expect(screen.getByRole('heading', { name: '重置密码' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '返回上一步' }).at(-1)).toHaveAttribute('href', '/forgot-password')
  })

  it.each([
    ['/privacy', '隐私说明'],
    ['/terms', '使用条款'],
  ] as const)('renders %s as scrollable public content without private navigation', (path, title) => {
    renderLegalContent(path)

    expect(screen.getByRole('main')).toHaveAttribute('data-testid', 'page-scroll-area')
    expect(screen.getByRole('heading', { name: title })).toHaveFocus()
    expect(screen.getByRole('link', { name: '返回首页' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('navigation', { name: '主要导航' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /后台|管理/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/上传/i)).not.toBeInTheDocument()
  })

  it('keeps an authentication entry inside the shared frame without a second main landmark', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'AUTHENTICATION_REQUIRED' } }), { status: 401 })))
    renderRoute('/login')

    await screen.findByRole('heading', { name: '欢迎回来' })
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('link', { name: '饮食健康 Agent' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
  })

  it('contains no admin route, navigation, or admin probe call in the user application', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'AUTHENTICATION_REQUIRED' } }), { status: 401 })))
    renderRoute('/admin')
    expect(
      screen.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /后台|管理/i })).not.toBeInTheDocument()
  })
})
