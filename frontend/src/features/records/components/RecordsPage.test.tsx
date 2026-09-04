import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext } from '@/auth/AuthContext'
import type { AuthenticatedRequest } from '@/auth/AuthContext'
import { deriveLocalWeekStart, RecordsPage } from './RecordsPage'

const totals = { energy_kcal: '0', protein_g: '0', fat_g: '0', carbohydrate_g: '0' }
const overview = {
  today: { consumed_local_date: '2026-09-07', totals, meal_count: 0 },
  week: Array.from({ length: 7 }, (_, index) => ({
    consumed_local_date: `2026-09-${String(index + 7).padStart(2, '0')}`,
    totals,
    meal_count: 0,
  })),
}
const review = {
  status: 'insufficient_coverage', week_start: '2026-09-07', week_end: '2026-09-13',
  coverage_days: 0, meal_count: 0, totals, suggestions: [],
}

function renderPage(request: AuthenticatedRequest) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}>
        <RecordsPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

describe('deriveLocalWeekStart', () => {
  it('以明确 IANA calendar parts 计算上海周一凌晨，而不是 UTC 周日', () => {
    expect(deriveLocalWeekStart(new Date('2026-09-06T16:30:00Z'), 'Asia/Shanghai')).toBe('2026-09-07')
  })

  it('在 Los Angeles DST 和 UTC 跨日时保持正确的当地周一', () => {
    expect(deriveLocalWeekStart(new Date('2026-03-09T06:30:00Z'), 'America/Los_Angeles')).toBe('2026-03-02')
    expect(deriveLocalWeekStart(new Date('2026-03-09T07:30:00Z'), 'America/Los_Angeles')).toBe('2026-03-09')
  })
})

describe('RecordsPage timezone confirmation gate', () => {
  it.each([200, 409])('确认返回 %s 后才读取公开 dashboard projection', async (status) => {
    const request = vi.fn<AuthenticatedRequest>((path: string) => {
      if (path === '/meal-records/dashboard-time-zone-confirmations') {
        return Promise.resolve(status === 409
          ? new Response(null, { status })
          : new Response(JSON.stringify({ dashboard_time_zone: 'Asia/Shanghai', confirmed_at: '2026-09-04T02:00:00Z' }), { status }))
      }
      if (path.startsWith('/dashboard/overview')) return Promise.resolve(new Response(JSON.stringify(overview), { status: 200 }))
      if (path === '/dashboard/history') return Promise.resolve(new Response(JSON.stringify({ groups: [] }), { status: 200 }))
      if (path.startsWith('/dashboard/weekly-review')) return Promise.resolve(new Response(JSON.stringify(review), { status: 200 }))
      throw new Error(`Unexpected request: ${path}`)
    })

    renderPage(request)

    await waitFor(() => expect(request).toHaveBeenCalledWith('/meal-records/dashboard-time-zone-confirmations', expect.anything()))
    await waitFor(() => expect(request).toHaveBeenCalledWith(expect.stringMatching(/^\/dashboard\/overview\?week_start=/)))
    expect(request.mock.calls.filter(([path]) => String(path).includes('time_zone'))).toHaveLength(0)
    expect(screen.getByRole('heading', { name: '记录' })).toBeInTheDocument()
  })

  it('确认失败时关闭 dashboard 请求，并提供安全的重试界面', async () => {
    const request = vi.fn<AuthenticatedRequest>().mockResolvedValue(new Response(null, { status: 400 }))

    renderPage(request)

    await waitFor(() => expect(screen.getByText('暂时无法确认统计时区。请检查浏览器设置后重试。')).toBeInTheDocument())
    expect(request).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: '重新尝试' })).toBeInTheDocument()
    expect(screen.queryByText(/HTTP|provider|stack/i)).not.toBeInTheDocument()
  })
})
