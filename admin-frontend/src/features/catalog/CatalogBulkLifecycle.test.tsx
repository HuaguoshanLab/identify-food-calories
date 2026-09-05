import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'
import { type CatalogDraft } from './api'
import { CatalogBulkLifecycle } from './CatalogBulkLifecycle'

const base = '/api/v1/admin/catalog-drafts'
const drafts: CatalogDraft[] = [1, 2, 3].map(i => ({ id: `170d36bc-28da-4eb7-9a6d-bdca560763c${i}`, canonical_name: `菜品${i}`, aliases: [`food${i}`], energy_kcal_per_100g: '180', protein_g_per_100g: '4', fat_g_per_100g: '4', carbohydrate_g_per_100g: '32', source_name: '来源', source_url: 'https://example.test/', authorization_status: 'authorized', revision: 1 }))
const preview = (draft: CatalogDraft) => ({ draft, publication: null, field_diffs: [{ field: 'canonical_name', before: null, after: draft.canonical_name, change: 'added' }], impact: { affected_catalog_items: 1, description: '发布用于新分析，历史不变。' } })
const result = (id: string) => ({ id, draft_id: id, draft_revision: 1, content_hash: 'a'.repeat(64), eligibility: 'eligible' })
function setup(action: 'review' | 'publish' = 'review') {
  const props = { accessToken: 'test-token', drafts, action, onClose: vi.fn(), onChanged: vi.fn(), onSecurityError: vi.fn((error: unknown) => [401, 403].includes((error as { status: number }).status)) }
  render(<CatalogBulkLifecycle {...props} />)
  return props
}
function previews() {
  mswServer.use(http.get(`${base}/:id/lifecycle-preview`, ({ params }) => HttpResponse.json(preview(drafts.find(d => d.id === params.id)!))))
}

describe('CatalogBulkLifecycle', () => {
  it.each(['review', 'publish'] as const)('%s 一次原因确认，多条独立版本/幂等命令和真实成功结果', async action => {
    const user = userEvent.setup()
    previews()
    const keys: string[] = []
    mswServer.use(http.post(`${base}/:id/${action}`, async ({ params, request }) => {
      expect(request.headers.get('If-Match')).toBe('1')
      expect(request.headers.get('Authorization')).toBe('Bearer test-token')
      expect(await request.json()).toEqual({ reason: '统一核对', confirm: true })
      keys.push(request.headers.get('Idempotency-Key')!)
      return HttpResponse.json(result(String(params.id)))
    }))
    setup(action)
    const confirm = await screen.findByRole('button', { name: `确认批量${action === 'review' ? '审核' : '发布'}（3）` })
    await user.click(confirm)
    expect(await screen.findByRole('alert')).toHaveTextContent('请说明此次变更原因')
    expect(keys).toHaveLength(0)
    await user.type(screen.getByLabelText('批量操作原因'), '统一核对')
    await user.click(confirm)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('成功 3 条'))
    expect(new Set(keys).size).toBe(3)
    expect(screen.getByRole('button', { name: '重试未确认项（0）' })).toBeDisabled()
  })

  it('失败不重复成功项，原键原原因重试；执行时不可关闭或重复提交', async () => {
    const user = userEvent.setup()
    previews()
    const calls: { id: string; key: string }[] = []
    let release: (() => void) | undefined
    mswServer.use(http.post(`${base}/:id/review`, async ({ params, request }) => {
      const id = String(params.id)
      calls.push({ id, key: request.headers.get('Idempotency-Key')! })
      if (calls.length === 1) await new Promise<void>(resolve => { release = resolve })
      if (id === drafts[1].id && calls.filter(c => c.id === id).length === 1) return HttpResponse.json({}, { status: 500 })
      if (id === drafts[2].id) return HttpResponse.json({}, { status: 409 })
      return HttpResponse.json(result(id))
    }))
    setup()
    await waitFor(() => expect(screen.getByRole('button', { name: '确认批量审核（3）' })).toBeEnabled())
    await user.type(screen.getByLabelText('批量操作原因'), '统一核对')
    await user.click(screen.getByRole('button', { name: '确认批量审核（3）' }))
    await waitFor(() => expect(release).toBeDefined())
    expect(screen.getByRole('button', { name: '正在执行…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '关闭窗口' })).toBeDisabled()
    release?.()
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('成功 1 条 · 跳过/失败 1 条 · 结果未确认 1 条'))
    expect(screen.getByLabelText('批量操作原因')).toHaveAttribute('readonly')
    await user.click(screen.getByRole('button', { name: '重试未确认项（1）' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('成功 2 条'))
    expect(calls).toHaveLength(4)
    expect(calls[1]).toEqual(calls[3])
  })

  it('未授权、已发布和版本变化均不提交', async () => {
    mswServer.use(http.get(`${base}/:id/lifecycle-preview`, ({ params }) => {
      const draft = drafts.find(d => d.id === params.id)!
      const data = preview(draft)
      if (draft.id === drafts[0].id) return HttpResponse.json({ ...data, draft: { ...draft, authorization_status: 'pending' } })
      if (draft.id === drafts[1].id) return HttpResponse.json({ ...data, publication: { id: draft.id, draft_revision: 1, eligibility: 'eligible', related_version: 'v1' } })
      return HttpResponse.json({ ...data, draft: { ...draft, revision: 2 } })
    }))
    setup('publish')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('跳过/失败 3 条'))
    expect(screen.getByRole('button', { name: '确认批量发布（0）' })).toBeDisabled()
  })

  it.each([401, 403])('提交 %s 后停止，不再请求后续项目', async status => {
    const user = userEvent.setup()
    previews()
    const post = vi.fn(() => HttpResponse.json({}, { status }))
    mswServer.use(http.post(`${base}/:id/review`, post))
    const props = setup()
    await waitFor(() => expect(screen.getByRole('button', { name: '确认批量审核（3）' })).toBeEnabled())
    await user.type(screen.getByLabelText('批量操作原因'), '统一核对')
    await user.click(screen.getByRole('button', { name: '确认批量审核（3）' }))
    await waitFor(() => expect(props.onSecurityError).toHaveBeenCalledWith(expect.objectContaining({ status })))
    expect(post).toHaveBeenCalledTimes(1)
  })
})
