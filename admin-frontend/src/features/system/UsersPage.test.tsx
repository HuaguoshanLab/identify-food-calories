import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useEffect } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { AdminAuthProvider, useAdminAuth } from '@/auth/AdminAuthProvider'
import { mswServer } from '@/test/setup'
import { AdminUsersPage } from './UsersPage'

const adminId = '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c'
const targetId = '02d49e0d-4ddb-4df2-b7ac-34993a625919'
const page = { items: [
  { id: adminId, email: 'admin@example.test', email_verified_at: '2026-09-01T00:00:00Z', is_active: true, role: 'admin', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
  { id: targetId, email: 'member@example.test', email_verified_at: '2026-09-01T00:00:00Z', is_active: true, role: 'user', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
], total: 2, page: 1, page_size: 20 }

function Establish() { const { establishSession } = useAdminAuth(); useEffect(() => establishSession({ accessToken: 'runtime-token', identity: { id: adminId } }), [establishSession]); return null }
function renderPage() { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AdminAuthProvider><Establish /><AdminUsersPage /></AdminAuthProvider></MemoryRouter></QueryClientProvider>) }

it('展示全部邮箱、禁止修改自己并以原因提交公开角色命令', async () => {
  const calls: unknown[] = []
  mswServer.use(
    http.get('/api/v1/admin/users', ({ request }) => { expect(request.headers.get('Authorization')).toBe('Bearer runtime-token'); return HttpResponse.json(page) }),
    http.patch(`/api/v1/admin/users/${targetId}/role`, async ({ request }) => { calls.push(await request.json()); expect(request.headers.get('Idempotency-Key')).toBeTruthy(); return HttpResponse.json({ audit_id: 'fc1e1f59-4e08-4c17-96b7-eb1e53f52d9a', target_user_id: targetId, before_role: 'user', after_role: 'admin', occurred_at: '2026-09-08T00:00:00Z' }) }),
  )
  renderPage()
  const table = await screen.findByRole('table')
  expect(within(table).getByText('admin@example.test')).toBeVisible()
  expect(within(table).getByText('member@example.test')).toBeVisible()
  expect(within(table).getByRole('button', { name: '撤销管理员' })).toBeDisabled()
  const user = userEvent.setup()
  await user.click(within(table).getByRole('button', { name: '设为管理员' }))
  expect(screen.getByRole('button', { name: '确认变更角色' })).toBeDisabled()
  await user.type(screen.getByLabelText('变更原因'), '承担目录维护职责')
  await user.click(screen.getByRole('button', { name: '确认变更角色' }))
  await waitFor(() => expect(calls).toEqual([{ role: 'admin', reason: '承担目录维护职责', confirm: true }]))
  expect(await screen.findByRole('status')).toHaveTextContent('操作已记录')
})
