import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthContext } from '@/auth/AuthContext'
import type { AuthenticatedRequest } from '@/auth/AuthContext'
import { RecordsPage } from './RecordsPage'

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

afterEach(() => { vi.restoreAllMocks() })

describe('RecordsPage timezone confirmation gate', () => {
  it('只有 same-zone 200 才读取服务端 current projection，且请求不含浏览器范围', async () => {
    const request = vi.fn<AuthenticatedRequest>((path: string) => {
      if (path === '/meal-records/dashboard-time-zone-confirmations') {
        return Promise.resolve(new Response(JSON.stringify({ dashboard_time_zone: 'Asia/Shanghai', confirmed_at: '2026-09-04T02:00:00Z' }), { status: 200 }))
      }
      if (path === '/dashboard/overview') return Promise.resolve(new Response(JSON.stringify(overview), { status: 200 }))
      if (path === '/dashboard/history') return Promise.resolve(new Response(JSON.stringify({ groups: [] }), { status: 200 }))
      if (path === '/dashboard/weekly-review') return Promise.resolve(new Response(JSON.stringify(review), { status: 200 }))
      throw new Error(`Unexpected request: ${path}`)
    })

    renderPage(request)

    await waitFor(() => expect(request).toHaveBeenCalledWith('/meal-records/dashboard-time-zone-confirmations', expect.anything()))
    await waitFor(() => expect(request).toHaveBeenCalledWith('/dashboard/overview'))
    expect(request).toHaveBeenCalledWith('/dashboard/weekly-review')
    expect(request.mock.calls.filter(([path]) => String(path).startsWith('/dashboard/')).map(([path]) => String(path))).not.toContainEqual(expect.stringMatching(/(?:week_start|time_zone)/))
    expect(screen.getByText('查看你已确认保存的餐食。')).toBeInTheDocument()
    const today = screen.getByText('今日已记录摄入')
    const trend = screen.getByRole('heading', { name: '本周趋势' })
    const history = screen.getByRole('heading', { name: '历史记录' })
    const weeklyReview = screen.getByRole('heading', { name: '周复盘' })
    expect(today.compareDocumentPosition(trend) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(trend.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(history.compareDocumentPosition(weeklyReview) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('different-zone 409 显示安全冲突，并关闭所有 dashboard reads', async () => {
    const request = vi.fn<AuthenticatedRequest>((path: string) => {
      if (path === '/meal-records/dashboard-time-zone-confirmations') return Promise.resolve(new Response(null, { status: 409 }))
      throw new Error(`Unexpected dashboard read: ${path}`)
    })

    renderPage(request)

    await waitFor(() => expect(screen.getByText('当前浏览器时区与已确认的统计时区不一致。请使用已确认的浏览器设置后重试。')).toBeInTheDocument())
    expect(request).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/HTTP|provider|stack|token|state/i)).not.toBeInTheDocument()
  })

  it.each([
    { browserZone: 'Asia/Shanghai', today: '2026-09-07', weekStart: '2026-09-07', week: ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11', '2026-09-12', '2026-09-13'] },
    { browserZone: 'America/Los_Angeles', today: '2026-09-06', weekStart: '2026-08-31', week: ['2026-08-31', '2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04', '2026-09-05', '2026-09-06'] },
  ])('同一 UTC instant 的 $browserZone fixture 只渲染 server today/week，不读取 host 时区', async ({ browserZone, today, weekStart, week }) => {
    vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockReturnValue({ timeZone: browserZone } as Intl.ResolvedDateTimeFormatOptions)
    const serverOverview = {
      ...overview,
      today: { ...overview.today, consumed_local_date: today },
      week: week.map((consumed_local_date) => ({ ...overview.week[0], consumed_local_date })),
    }
    const request = vi.fn<AuthenticatedRequest>((path: string) => {
      if (path === '/meal-records/dashboard-time-zone-confirmations') return Promise.resolve(new Response(JSON.stringify({ dashboard_time_zone: browserZone, confirmed_at: '2026-09-04T02:00:00Z' }), { status: 200 }))
      if (path === '/dashboard/overview') return Promise.resolve(new Response(JSON.stringify(serverOverview), { status: 200 }))
      if (path === '/dashboard/history') return Promise.resolve(new Response(JSON.stringify({ groups: [] }), { status: 200 }))
      if (path === '/dashboard/weekly-review') return Promise.resolve(new Response(JSON.stringify({ ...review, week_start: weekStart }), { status: 200 }))
      throw new Error(`Unexpected request: ${path}`)
    })

    renderPage(request)

    await waitFor(() => expect(request).toHaveBeenCalledWith('/dashboard/overview'))
    expect(serverOverview.week.map((day) => day.consumed_local_date)).toContain(serverOverview.today.consumed_local_date)
    expect(request.mock.calls.map(([path]) => String(path)).join(' ')).not.toMatch(/week_start|time_zone/)
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
