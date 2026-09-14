import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useEffect } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { AdminAuthProvider, useAdminAuth } from '@/auth/AdminAuthProvider'
import { mswServer } from '@/test/setup'
import type { VectorBuild } from './api'
import { hasRunningVectorBuild, VectorRetrievalPage } from './VectorRetrievalPage'

const id = '5d41f8f5-a892-48f3-ab62-12f0f4a9c80c'
const buildId = '2d49e0d1-4ddb-4df2-b7ac-34993a625919'
const spaceId = '3d49e0d2-4ddb-4df2-b7ac-34993a625919'
const build: VectorBuild = { id: buildId, vector_space_id: spaceId, embedding_model: 'text-embedding-v4', embedding_dimension: 1024, adapter_version: 'dashscope-text-embedding-v4-1024.v1', retrieval_version: 'retrieval-06-3-v1', snapshot_hash: 'a'.repeat(64), expected_name_count: 2, pending_count: 0, failed_count: 1, completed_count: 1, status: 'partial_failure', requested_at: '2026-09-12T00:00:00.000Z', is_active: false, activation_ready: false }

function Establish() { const { establishSession } = useAdminAuth(); useEffect(() => establishSession({ accessToken: 'runtime-token', identity: { id } }), [establishSession]); return null }
function renderPage() { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AdminAuthProvider><Establish /><VectorRetrievalPage /></AdminAuthProvider></MemoryRouter></QueryClientProvider>) }

it('以固定 DashScope 身份创建、重试失败任务，并且服务端未准入时不显示激活', async () => {
  const createBodies: unknown[] = []; const retryBodies: unknown[] = []
  mswServer.use(
    http.get('/api/v1/admin/vector-space-builds', ({ request }) => { expect(request.headers.get('Authorization')).toBe('Bearer runtime-token'); return HttpResponse.json({ items: [build] }) }),
    http.post('/api/v1/admin/vector-space-builds', async ({ request }) => { createBodies.push(await request.json()); return HttpResponse.json(build, { status: 201 }) }),
    http.post(`/api/v1/admin/vector-space-builds/${buildId}/retries`, async ({ request }) => { retryBodies.push(await request.json()); return HttpResponse.json({ ...build, pending_count: 1, failed_count: 0, reset_count: 1 }) }),
  )
  renderPage()
  expect(await screen.findByRole('button', { name: '重试失败项' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '激活' })).not.toBeInTheDocument()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '创建 DashScope 构建' }))
  await user.type(screen.getByLabelText('操作原因'), '首次构建真实向量')
  await user.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(createBodies).toEqual([{ embedding_model: 'text-embedding-v4', embedding_dimension: 1024, adapter_version: 'dashscope-text-embedding-v4-1024.v1', retrieval_version: 'retrieval-06-3-v1', reason: '首次构建真实向量', confirm: true }]))
  await user.click(screen.getByRole('button', { name: '重试失败项' }))
  await user.type(screen.getByLabelText('操作原因'), '上游已恢复')
  await user.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(retryBodies).toEqual([{ reason: '上游已恢复', confirm: true }]))
})

it('回填旧目录检索名称并明确提示可能产生的任务数量', async () => {
  const backfillBodies: unknown[] = []
  mswServer.use(
    http.get('/api/v1/admin/vector-space-builds', () => HttpResponse.json({ items: [build] })),
    http.post('/api/v1/admin/catalog-search-index-backfills', async ({ request }) => {
      expect(request.headers.get('Authorization')).toBe('Bearer runtime-token')
      expect(request.headers.get('Idempotency-Key')).toBeTruthy()
      backfillBodies.push(await request.json())
      return HttpResponse.json({ audit_id: id, publication_count: 612, name_count: 928, embedding_job_count: 0 }, { status: 201 })
    }),
  )
  renderPage()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '回填检索名称' }))
  expect(screen.getByText(/可能同时排队 Embedding 任务并产生 Provider 费用/)).toBeVisible()
  await user.type(screen.getByLabelText('操作原因'), '补齐升级前目录的检索名称')
  await user.click(screen.getByRole('button', { name: '确认操作' }))

  await waitFor(() => expect(backfillBodies).toEqual([{ reason: '补齐升级前目录的检索名称', confirm: true }]))
  expect(await screen.findByRole('status')).toHaveTextContent('更新 612 条目录，创建 928 个名称，排队 0 个任务')
})

it('历史零任务记录显示为空构建而不是已完成', async () => {
  mswServer.use(http.get('/api/v1/admin/vector-space-builds', () => HttpResponse.json({
    items: [{ ...build, expected_name_count: 0, completed_count: 0, failed_count: 0, status: 'empty' }],
  })))
  renderPage()

  expect(await screen.findByText('空构建')).toBeVisible()
  expect(screen.getByText(/检测到历史空构建/)).toBeVisible()
  expect(screen.queryByText('已完成')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '激活' })).not.toBeInTheDocument()
})

it('403 时不显示构建数据', async () => {
  mswServer.use(http.get('/api/v1/admin/vector-space-builds', () => new HttpResponse(null, { status: 403 })))
  renderPage()
  expect(await screen.findByText('无后台访问权限')).toBeVisible()
  expect(screen.queryByText('text-embedding-v4')).not.toBeInTheDocument()
})

it('只在存在等待或处理中的构建时继续轮询', () => {
  expect(hasRunningVectorBuild([{ ...build, failed_count: 0, completed_count: 2, status: 'ready', is_active: true }])).toBe(false)
  expect(hasRunningVectorBuild([{ ...build, pending_count: 1, failed_count: 0, status: 'processing' }])).toBe(true)
})
