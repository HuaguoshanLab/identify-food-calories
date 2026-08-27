import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { AuthProvider } from './AuthProvider'
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
})
