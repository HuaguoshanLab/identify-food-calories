import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { mswServer } from '@/test/setup'
import { AdminOverviewPage } from './AdminOverviewPage'

const apiBase = '/api/v1/admin'
const response = { terminal_count: 42, failure_ratio: '0.125', p50_elapsed_ms: 180, p95_elapsed_ms: 800, total_cost_usd: '4.20', from: '2026-09-02T12:00:00Z', to: '2026-09-03T12:00:00Z' }

describe('AdminOverviewPage', () => {
  it('只显示严格运行指标，并将同一 UTC 窗口带到运行审计链接', async () => {
    mswServer.use(http.get(`${apiBase}/runs/metrics`, () => HttpResponse.json(response)))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AdminOverviewPage accessToken="runtime-only-token" onSessionExpired={() => undefined} /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('42')).toBeVisible()
    expect(screen.getByText('P50 / P95 耗时')).toBeVisible()
    for (const link of screen.getAllByRole('link', { name: /查看运行审计|总终态运行数|失败率|P50|总估算费用/ })) {
      const url = new URL(link.getAttribute('href') ?? '', 'http://localhost')
      expect(url.pathname).toBe('/admin/runs')
      expect(url.searchParams.get('occurred_after')).toBe(response.from)
      expect(url.searchParams.get('occurred_before')).toBe(response.to)
    }
    expect(screen.queryByText(/provider_body|reasoning|api_key|runtime-only-token/i)).not.toBeInTheDocument()
  })
})
