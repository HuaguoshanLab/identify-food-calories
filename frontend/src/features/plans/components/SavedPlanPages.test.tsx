import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { PlanPage } from './PlanPage'
import { SavedPlanPage } from './SavedPlanPage'
import { PlanHistoryPage } from './PlanHistoryPage'

const id = '11111111-1111-4111-8111-111111111111'
const saved = {
  id, plan_date: '2026-09-06', time_zone: 'Asia/Shanghai', current_version: 2, version: 2,
  created_at: '2026-09-06T01:00:00Z', updated_at: '2026-09-06T02:00:00Z', saved_at: '2026-09-06T02:00:00Z', adjustment_thread_id: null,
  totals: { energy_kcal: '1200', protein_g: '60', fat_g: '30', carbohydrate_g: '150' },
  report: { stage: 'complete', target: Object.fromEntries(['energy_kcal', 'protein_g', 'fat_g', 'carbohydrate_g'].map((key) => [key, { lower: '0', upper: '2000' }])), meals: ['breakfast', 'lunch', 'dinner'].map((slot) => ({ slot, display_name: `存档${slot}`, portion_description: '一份', portion_grams: '200', method_tags: [], flavour_tags: [], matched_preference_summaries: [], matched_exclusion_summaries: [], nutrients: { energy_kcal: '400', protein_g: '20', fat_g: '10', carbohydrate_g: '50' } })), disclaimer: '普通饮食参考，不替代医疗建议。', adjustment: null },
}

function renderPage(request: AuthContextValue['request'], entry = '/app/plans') {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthContext.Provider value={{ status: 'authenticated', request, login: vi.fn(), logout: vi.fn(), retryBootstrap: vi.fn() }}><MemoryRouter initialEntries={[entry]}><Routes><Route path="/app/plans" element={<PlanPage />} /><Route path="/app/plans/history" element={<PlanHistoryPage />} /><Route path="/app/plans/detail" element={<SavedPlanPage />} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>)
}

function response(payload: unknown) { return new Response(JSON.stringify(payload)) }

describe('saved plans', () => {
  it('restores today after a fresh mount without regenerating or relying on a live thread', async () => {
    const request = vi.fn(async (path: string) => path === '/planning/plans/today' ? response({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: saved }) : path === '/memories' ? response([]) : new Response('', { status: 404 }))
    const first = renderPage(request)
    expect(await screen.findByText('存档breakfast')).toBeVisible()
    expect(screen.getByText(/已自动保存.*第 2 版/)).toBeVisible()
    expect(screen.queryByLabelText('身高')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '提交调整' })).not.toBeInTheDocument()
    first.unmount()
    renderPage(request)
    expect(await screen.findByText('存档breakfast')).toBeVisible()
    expect(request.mock.calls.every(([path]) => !path.startsWith('/agent/'))).toBe(true)
  })

  it('requires timezone confirmation and offers retry when the current-day read fails', async () => {
    const user = userEvent.setup()
    let reads = 0
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/planning/plans/today') return ++reads === 1 ? new Response('', { status: 503 }) : response({ time_zone: null, today: null, plan: null })
      if (init?.method === 'POST') return new Response('', { status: 500 })
      return path === '/memories' ? response([]) : new Response('', { status: 404 })
    })
    renderPage(request)
    await user.click(await screen.findByRole('button', { name: '重新读取' }))
    await user.click(await screen.findByRole('button', { name: '确认时区' }))
    expect(await screen.findByText(/确认失败/)).toBeVisible()
    expect(screen.queryByRole('button', { name: '生成今日餐单' })).not.toBeInTheDocument()
  })

  it('reads older versions and requires confirmation before deleting all versions', async () => {
    const user = userEvent.setup()
    let deleted = false
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') { deleted = true; return new Response(null, { status: 204 }) }
      if (path === '/planning/plans') return response({ items: [], next_before: null })
      return response({ ...saved, version: path.endsWith('version=1') ? 1 : 2 })
    })
    renderPage(request, `/app/plans/detail?id=${id}`)
    await user.click(await screen.findByRole('button', { name: '上一版' }))
    expect(await screen.findByText(/第 1 \/ 2 版/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: '删除这天的计划' }))
    expect(deleted).toBe(false)
    await user.click(screen.getByRole('button', { name: '取消' }))
    expect(deleted).toBe(false)
    await user.click(screen.getByRole('button', { name: '删除这天的计划' }))
    await user.click(screen.getByRole('button', { name: '确认删除' }))
    await waitFor(() => expect(deleted).toBe(true))
    expect(await screen.findByText(/还没有保存的计划/)).toBeVisible()
  })

  it('shows recoverable history failures and an honest empty state', async () => {
    const user = userEvent.setup()
    let fail = true
    const request = vi.fn(async () => fail ? new Response('', { status: 503 }) : response({ items: [], next_before: null }))
    renderPage(request, '/app/plans/history')
    expect(await screen.findByText('无法读取历史计划')).toBeVisible()
    fail = false
    await user.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText(/还没有保存的计划/)).toBeVisible()
  })
})
