import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { AuthProvider } from './auth/AuthProvider'

function NavigationProbe() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <>
      <output data-testid="pathname">{location.pathname}</output>
      <button onClick={() => navigate(-1)} type="button">测试返回</button>
    </>
  )
}

function renderApp(initialEntries: string[] = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <App />
          <NavigationProbe />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function stubAuthenticatedIdentity() {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/auth/refresh')) {
      return new Response(JSON.stringify({ access_token: 'runtime-only-access', expires_in: 900, token_type: 'bearer' }))
    }
    if (url.endsWith('/users/me')) {
      return new Response(JSON.stringify({
        id: '00000000-0000-0000-0000-000000000001',
        email: 'database@example.com',
        email_verified_at: null,
        is_active: true,
        role: 'user',
      }))
    }
    if (url.endsWith('/auth/sessions')) {
      return new Response(JSON.stringify([]))
    }
    return new Response(JSON.stringify({ error: { code: 'UNEXPECTED' } }), { status: 500 })
  }))
}

describe('App', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('renders the public product landing page', () => {
    renderApp()

    expect(
      screen.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '创建账号' })).toHaveAttribute('href', '/register')
  })

  it('replaces the protected index with 分析 and preserves normal tab history', async () => {
    const user = userEvent.setup()
    stubAuthenticatedIdentity()
    renderApp(['/app'])

    expect(await screen.findByRole('heading', { name: '描述这餐吃了什么' })).toBeInTheDocument()
    expect(screen.getByTestId('pathname')).toHaveTextContent('/app/analyze')

    await user.click(screen.getByRole('link', { name: '记录' }))
    expect(await screen.findByRole('heading', { name: '记录' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '测试返回' }))
    expect(await screen.findByRole('heading', { name: '分析' })).toBeInTheDocument()
  })

  it('uses the tab shell for a direct tab route and the detail shell without tab navigation', async () => {
    stubAuthenticatedIdentity()
    const { unmount } = renderApp(['/app/analyze'])

    expect(await screen.findByRole('heading', { name: '分析' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '主要导航' })).toBeInTheDocument()
    unmount()

    renderApp(['/app/me/account'])
    expect(await screen.findByRole('heading', { name: '账号资料' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回我的' })).toHaveAttribute('href', '/app/me')
    expect(screen.queryByRole('navigation', { name: '主要导航' })).not.toBeInTheDocument()
  })

  it('moves focus to my and detail page headings after route changes', async () => {
    const user = userEvent.setup()
    stubAuthenticatedIdentity()
    const analyzeRoute = renderApp(['/app/analyze'])

    await screen.findByRole('heading', { name: '分析' })
    await user.click(screen.getByRole('link', { name: '我的' }))
    expect(await screen.findByRole('heading', { name: '我的' })).toHaveFocus()

    await user.click(screen.getByRole('link', { name: /账号资料/ }))
    expect(await screen.findByRole('heading', { level: 1, name: '账号资料' })).toHaveFocus()
    analyzeRoute.unmount()

    const meRoute = renderApp(['/app/me'])
    await screen.findByRole('heading', { name: '我的' })
    await user.click(screen.getByRole('link', { name: /登录会话/ }))
    expect(await screen.findByRole('heading', { level: 1, name: '登录会话' })).toHaveFocus()
    meRoute.unmount()

    renderApp(['/app/me/account'])
    expect(await screen.findByRole('heading', { level: 1, name: '账号资料' })).toHaveFocus()
  })
})
