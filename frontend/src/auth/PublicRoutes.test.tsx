import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App, userRoutePaths } from '../App'

function renderRoute(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('public user routes', () => {
  it('keeps landing, legal and account-entry pages public', () => {
    renderRoute('/')
    expect(
      screen.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '创建账号' })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: '登录' })).toHaveAttribute('href', '/login')

    renderRoute('/privacy')
    expect(screen.getByRole('heading', { name: '隐私说明' })).toBeInTheDocument()

    renderRoute('/terms')
    expect(screen.getByRole('heading', { name: '使用条款' })).toBeInTheDocument()
  })

  it('declares authentication entry routes and sends the protected app route to login', () => {
    renderRoute('/app?tab=sessions')

    expect(screen.getByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
    expect(screen.getByText('请先登录后继续使用账号功能。')).toBeInTheDocument()

    expect(userRoutePaths).toEqual(
      expect.arrayContaining([
        '/',
        '/login',
        '/register',
        '/register/verify',
        '/forgot-password',
        '/reset-password',
        '/privacy',
        '/terms',
        '/app',
      ]),
    )
  })

  it('contains no admin route, navigation, or admin probe call in the user application', () => {
    renderRoute('/')

    expect(userRoutePaths).not.toContain('/admin')
    expect(screen.queryByRole('link', { name: /后台|管理/i })).not.toBeInTheDocument()
  })
})
