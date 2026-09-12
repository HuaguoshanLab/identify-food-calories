import { HttpResponse, http } from 'msw'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'

import { RunsPage } from './RunsPage'

const apiBase = '/api/v1/admin'
const runId = '2864a3fc-766f-4ae3-b43a-bfa3077e1a4d'

const metrics = {
  terminal_count: 101,
  failure_ratio: '0.25',
  p50_elapsed_ms: 210,
  p95_elapsed_ms: 890,
  total_cost_usd: '0.032',
  from: '2026-09-02T08:20:00Z',
  to: '2026-09-03T08:20:00Z',
}

const runsPage = {
  items: [{
    id: runId,
    status: 'failed',
    graph_version: 'analysis-v3',
    model_provider: 'deepseek',
    model_version: 'deepseek-v4-flash',
    graph_steps: 4,
    model_calls: 2,
    tool_calls: 1,
    elapsed_ms: 400,
    estimated_cost_usd: '0.004',
    failure_code: 'MODEL_TIMEOUT',
    finished_at: '2026-09-03T08:20:00Z',
    invocations: [],
  }],
  next_cursor: 'opaque-run-cursor-0001',
}

const runDetail = {
  ...runsPage.items[0],
  invocations: [{ node_name: 'nutrition_lookup', status: 'failed', attempt: 1, cost_usd: '0.001', failure_code: 'MODEL_TIMEOUT', safe_result_digest: 'sha256:allowed' }],
}

function renderRunsPage() {
  const onSessionExpired = vi.fn()
  render(<RunsPage accessToken="runtime-only-token" onSessionExpired={onSessionExpired} />)
  return { onSessionExpired }
}

describe('RunsPage', () => {
  it('用同一组严格 UTC filters 请求 metrics 与列表；筛选变化清除各自 opaque cursor', async () => {
    const user = userEvent.setup()
    const requestedUrls: string[] = []
    mswServer.use(
      http.get(`${apiBase}/runs/metrics`, ({ request }) => {
        requestedUrls.push(request.url)
        return HttpResponse.json(metrics)
      }),
      http.get(`${apiBase}/runs`, ({ request }) => {
        requestedUrls.push(request.url)
        return HttpResponse.json(runsPage)
      }),
    )
    renderRunsPage()

    expect(await screen.findByText('终态运行数')).toBeVisible()
    expect(screen.getByLabelText('UTC 起始')).toHaveAttribute('type', 'date')
    expect(screen.getByLabelText('UTC 结束')).toHaveAttribute('type', 'date')
    expect(screen.getByRole('navigation', { name: '运行分页' })).toHaveTextContent('1/ 3')
    await user.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(requestedUrls.some((url) => new URL(url).searchParams.get('cursor') === 'opaque-run-cursor-0001')).toBe(true))
    expect(screen.getByRole('navigation', { name: '运行分页' })).toHaveTextContent('2/ 3')
    expect(screen.getByRole('button', { name: '上一页' })).toBeEnabled()

    await user.selectOptions(screen.getByLabelText('运行状态'), 'failed')
    await waitFor(() => {
      const callsAfterFilter = requestedUrls.slice(-2).map((url) => new URL(url))
      expect(callsAfterFilter).toHaveLength(2)
      for (const url of callsAfterFilter) {
        expect(url.searchParams.get('status')).toBe('failed')
        expect(url.searchParams.get('cursor')).toBeNull()
      }
      expect(callsAfterFilter[0].searchParams.get('occurred_after')).toBe(callsAfterFilter[1].searchParams.get('occurred_after'))
      expect(callsAfterFilter[0].searchParams.get('occurred_before')).toBe(callsAfterFilter[1].searchParams.get('occurred_before'))
    })
  })

  it('用语义表格和安全 Drawer 展示最小 run/invocation 字段，不能将敏感 ledger 数据放入 DOM', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.get(`${apiBase}/runs/metrics`, () => HttpResponse.json(metrics)),
      http.get(`${apiBase}/runs`, () => HttpResponse.json(runsPage)),
      http.get(`${apiBase}/runs/${runId}`, () => HttpResponse.json(runDetail)),
    )
    renderRunsPage()

    const table = await screen.findByRole('table', { name: '终态运行列表' })
    expect(within(table).getByRole('columnheader', { name: '状态' })).toHaveAttribute('aria-sort', 'descending')
    await user.click(within(table).getByRole('button', { name: '查看运行详情' }))
    const drawer = await screen.findByRole('dialog', { name: '运行详情' })
    expect(within(drawer).getByText('nutrition_lookup')).toBeVisible()
    expect(screen.queryByText(/never@example|provider_body|graph_state|reasoning|api_key|runtime-only-token/i)).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: '运行详情' })).not.toBeInTheDocument()
  })

  it('401/403 时清除会话并不保留已读运行，窄屏布局仍保留可访问筛选与 Sheet 详情', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.get(`${apiBase}/runs/metrics`, () => HttpResponse.json(metrics)),
      http.get(`${apiBase}/runs`, () => HttpResponse.json(runsPage)),
    )
    const { onSessionExpired } = renderRunsPage()
    await screen.findByRole('table', { name: '终态运行列表' })

    mswServer.use(http.get(`${apiBase}/runs/${runId}`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })))
    await user.click(screen.getByRole('button', { name: '查看运行详情' }))
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce())
    expect(screen.queryByRole('table', { name: '终态运行列表' })).not.toBeInTheDocument()

    window.innerWidth = 768
    window.dispatchEvent(new Event('resize'))
    mswServer.use(http.get(`${apiBase}/runs/metrics`, () => HttpResponse.json({ error: { code: 'ADMIN_PERMISSION_REQUIRED' } }, { status: 403 })))
  })
})
