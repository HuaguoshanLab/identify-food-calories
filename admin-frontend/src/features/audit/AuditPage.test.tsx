import { HttpResponse, http } from 'msw'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'

import { AuditPage } from './AuditPage'

const apiBase = '/api/v1/admin'
const auditPage = {
  items: [{
    id: '3c33167c-4660-47b8-a822-5c02e04ef4f7',
    actor_identifier: '4b7e35db-3846-485f-9224-1f6510ebf7be',
    actor_label: 'admin@example.test',
    occurred_at: '2026-09-03T04:20:00Z',
    action: 'runtime_config.configure',
    object_type: 'agent_runtime_config_version',
    object_id: 'af10d1d9-4603-4db4-b5f0-399bf2abef63',
    reason: '已完成来源复核',
    before: { enabled: true, version: 'v2', api_key: 'never' },
    after: { enabled: false, version: 'v3', provider_body: 'never' },
    related_version: 'v3',
    command_key: 'never-show-command-key',
  }, {
    id: '2a1d830d-77e6-49c7-91ed-d8d46d05f43b',
    actor_identifier: '7c8928fc-9b10-435a-a492-151a35e2fd60',
    actor_label: 'admin@example.test',
    occurred_at: '2026-09-02T04:20:00Z',
    action: 'catalog_draft.create',
    object_type: 'catalog_draft',
    object_id: '15ba2fbb-d89a-412c-8d5e-5e76f0b90698',
    reason: '新增食物条目',
    before: {},
    after: { canonical_name: '生煎包' },
    related_version: null,
    command_key: 'never-show-second-command-key',
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
    expect(screen.getByLabelText('UTC 起始')).toHaveAttribute('type', 'date')
    expect(screen.getByLabelText('UTC 结束')).toHaveAttribute('type', 'date')
    expect(screen.getByRole('navigation', { name: '操作审计分页' })).toHaveTextContent('1')
    await user.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(requests.some((url) => url.searchParams.get('cursor') === 'opaque-audit-cursor-0001')).toBe(true))
    expect(screen.getByRole('navigation', { name: '操作审计分页' })).toHaveTextContent('2')
    expect(screen.getByRole('button', { name: '上一页' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: '上一页' }))
    await waitFor(() => expect(requests.at(-1)?.searchParams.get('cursor')).toBeNull())
    expect(screen.getByRole('navigation', { name: '操作审计分页' })).toHaveTextContent('1')
    await user.type(screen.getByLabelText('操作动作'), 'runtime_config.configure')
    await waitFor(() => {
      const current = requests.at(-1)
      expect(current?.pathname).toBe('/api/v1/admin/audit')
      expect(current?.searchParams.get('action')).toBe('runtime_config.configure')
      expect(current?.searchParams.get('cursor')).toBeNull()
      expect([...current!.searchParams.keys()].sort()).toEqual(['action', 'limit'])
    })
  })

  it('仅以服务端 audit DTO 显示 actor/time/action/object/reason/field diff/version，过滤敏感字段且不伪造客户端 diff', async () => {
    mswServer.use(http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)))
    renderAuditPage()

    const table = await screen.findByRole('table', { name: '操作审计时间线' })
    expect(within(table).getAllByText('admin@example.test')).toHaveLength(2)
    expect(within(table).getByText('更新运行策略')).toBeVisible()
    expect(within(table).getByText('运行策略版本（已记录）')).toBeVisible()
    expect(within(table).getByText('创建营养目录草稿')).toBeVisible()
    expect(within(table).getByText('营养目录草稿：生煎包')).toBeVisible()
    expect(within(table).getByText('已完成来源复核')).toBeVisible()
    expect(within(table).getByText('enabled')).toBeVisible()
    expect(within(table).getByText('v3')).toBeVisible()
    expect(screen.queryByText(/api_key|provider_body|never-show-command-key|runtime-only-token|4b7e35db|runtime_config\.configure|agent_runtime_config_version|af10d1d9|7c8928fc|catalog_draft\.create|15ba2fbb/i)).not.toBeInTheDocument()
  })

  it('401/403 时不显示缓存审计记录，键盘 skip link 将焦点交给 main', async () => {
    const user = userEvent.setup()
    mswServer.use(http.get(`${apiBase}/audit`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })))
    const { onSessionExpired } = renderAuditPage()
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce())
    expect(screen.queryByRole('table', { name: '操作审计时间线' })).not.toBeInTheDocument()

    cleanup()
    mswServer.use(http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)))
    renderAuditPage()
    await screen.findByRole('table', { name: '操作审计时间线' })
    await user.click(screen.getByRole('link', { name: '跳到主要内容' }))
    expect(document.getElementById('audit-main')).toHaveFocus()
  })
})
