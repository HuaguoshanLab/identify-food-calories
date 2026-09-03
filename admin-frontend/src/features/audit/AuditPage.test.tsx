import { HttpResponse, http } from 'msw'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'

import { AuditPage } from './AuditPage'

const apiBase = '/api/v1/admin'
const auditPage = {
  items: [{
    id: '3c33167c-4660-47b8-a822-5c02e04ef4f7',
    actor_identifier: 'admin-42',
    occurred_at: '2026-09-03T04:20:00Z',
    action: 'runtime_config.updated',
    object_type: 'runtime_config',
    object_id: 'runtime-v3',
    reason: '已完成来源复核',
    before: { enabled: true, version: 'v2', api_key: 'never' },
    after: { enabled: false, version: 'v3', provider_body: 'never' },
    related_version: 'v3',
    command_key: 'never-show-command-key',
  }],
  next_cursor: 'opaque-audit-cursor-0001',
}

function renderAuditPage() {
  const onSessionExpired = vi.fn()
  render(<AuditPage accessToken="runtime-only-token" onSessionExpired={onSessionExpired} />)
  return { onSessionExpired }
}

describe('AuditPage', () => {
  it('只向 audit endpoint 发送 allowlist filters 与 opaque cursor，筛选改变会重置 cursor', async () => {
    const user = userEvent.setup()
    const requests: URL[] = []
    mswServer.use(http.get(`${apiBase}/audit`, ({ request }) => {
      requests.push(new URL(request.url))
      return HttpResponse.json(auditPage)
    }))
    renderAuditPage()

    await screen.findByRole('table', { name: '操作审计时间线' })
    await user.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(requests.some((url) => url.searchParams.get('cursor') === 'opaque-audit-cursor-0001')).toBe(true))
    await user.type(screen.getByLabelText('操作动作'), 'runtime_config.updated')
    await waitFor(() => {
      const current = requests.at(-1)
      expect(current?.pathname).toBe('/api/v1/admin/audit')
      expect(current?.searchParams.get('action')).toBe('runtime_config.updated')
      expect(current?.searchParams.get('cursor')).toBeNull()
      expect([...current!.searchParams.keys()].sort()).toEqual(['action', 'limit'])
    })
  })

  it('仅以服务端 audit DTO 显示 actor/time/action/object/reason/field diff/version，过滤敏感字段且不伪造客户端 diff', async () => {
    mswServer.use(http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)))
    renderAuditPage()

    const table = await screen.findByRole('table', { name: '操作审计时间线' })
    expect(within(table).getByText('admin-42')).toBeVisible()
    expect(within(table).getByText('runtime_config.updated')).toBeVisible()
    expect(within(table).getByText('已完成来源复核')).toBeVisible()
    expect(within(table).getByText('enabled')).toBeVisible()
    expect(within(table).getByText('v3')).toBeVisible()
    expect(screen.queryByText(/api_key|provider_body|never-show-command-key|runtime-only-token/i)).not.toBeInTheDocument()
  })

  it('401/403 时不显示缓存审计记录，键盘 skip link 将焦点交给 main', async () => {
    const user = userEvent.setup()
    mswServer.use(http.get(`${apiBase}/audit`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })))
    const { onSessionExpired } = renderAuditPage()
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce())
    expect(screen.queryByRole('table', { name: '操作审计时间线' })).not.toBeInTheDocument()

    mswServer.use(http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)))
    renderAuditPage()
    await screen.findByRole('table', { name: '操作审计时间线' })
    await user.click(screen.getByRole('link', { name: '跳到主要内容' }))
    expect(screen.getByRole('main')).toHaveFocus()
  })
})
