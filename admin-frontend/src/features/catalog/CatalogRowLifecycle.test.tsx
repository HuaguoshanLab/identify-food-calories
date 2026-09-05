import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'
import { CatalogRowLifecycle } from './CatalogRowLifecycle'

const id = '170d36bc-28da-4eb7-9a6d-bdca560763c1'
const base = `/api/v1/admin/catalog-drafts/${id}`
const preview = {
  draft: { id, canonical_name: '担担饭', aliases: ['dandanfan'], energy_kcal_per_100g: '180', protein_g_per_100g: '4', fat_g_per_100g: '4', carbohydrate_g_per_100g: '32', source_name: '目录来源', source_url: 'https://example.test/', authorization_status: 'authorized', revision: 1 },
  publication: null,
  field_diffs: [{ field: 'canonical_name', before: null, after: '担担饭', change: 'added' }],
  impact: { affected_catalog_items: 1, description: '发布后用于新分析，不更改历史餐食。' },
}
const result = { id, draft_id: id, draft_revision: 1, content_hash: 'a'.repeat(64), eligibility: 'eligible' }

function setup(action: 'review' | 'publish' = 'review') {
  const props = { accessToken: 'test-token', draftId: id, action, onClose: vi.fn(), onSuccess: vi.fn(), onSecurityError: vi.fn(() => false), onBusyChange: vi.fn() }
  render(<CatalogRowLifecycle {...props} />)
  return props
}

describe('CatalogRowLifecycle', () => {
  it.each(['review', 'publish'] as const)('%s 使用当前服务端版本，在表格内验证原因再提交', async (action) => {
    const user = userEvent.setup()
    let calls = 0
    mswServer.use(http.get(`${base}/lifecycle-preview`, () => HttpResponse.json(preview)), http.post(`${base}/${action}`, async ({ request }) => {
      calls += 1
      expect(request.headers.get('If-Match')).toBe('1')
      expect(request.headers.get('Authorization')).toBe('Bearer test-token')
      expect(await request.json()).toEqual({ reason: '核对完成', confirm: true })
      return HttpResponse.json(result)
    }))
    const props = setup(action)
    const confirm = await screen.findByRole('button', { name: action === 'review' ? '确认审核草稿' : '确认发布版本' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(document.querySelector('details')).not.toHaveAttribute('open')
    await user.click(confirm)
    expect(await screen.findByRole('alert')).toHaveTextContent('请说明此次变更原因')
    expect(calls).toBe(0)
    await user.type(screen.getByLabelText('操作原因'), '核对完成')
    await user.click(confirm)
    await waitFor(() => expect(props.onSuccess).toHaveBeenCalledWith(expect.stringContaining(action === 'review' ? '已审核草稿 v1' : '已发布版本 v1')))
    expect(calls).toBe(1)
  })

  it('请求中锁定，未知失败重试复用命令键，409 在操作区显示且不声称他人修改', async () => {
    const user = userEvent.setup()
    const keys: string[] = []
    let release: (() => void) | undefined
    mswServer.use(http.get(`${base}/lifecycle-preview`, () => HttpResponse.json(preview)), http.post(`${base}/publish`, async ({ request }) => {
      keys.push(request.headers.get('Idempotency-Key')!)
      if (keys.length === 1) { await new Promise<void>((resolve) => { release = resolve }); return HttpResponse.json({}, { status: 500 }) }
      return HttpResponse.json({}, { status: 409 })
    }))
    const props = setup('publish')
    await screen.findByLabelText('操作原因')
    await user.type(screen.getByLabelText('操作原因'), '核对完成')
    await user.click(screen.getByRole('button', { name: '确认发布版本' }))
    await waitFor(() => expect(release).toBeDefined())
    expect(screen.getByRole('button', { name: '正在提交…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '取消' })).toBeDisabled()
    release?.()
    await screen.findByText(/未能确认操作结果/)
    await user.click(screen.getByRole('button', { name: '确认发布版本' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请确认当前草稿已授权、已审核且未被修改')
    expect(screen.getByLabelText('操作原因')).toHaveValue('核对完成')
    expect(keys[0]).toBe(keys[1])
    expect(props.onSuccess).not.toHaveBeenCalled()
  })

  it.each(['pending', 'published'] as const)('%s 状态不允许误发布', async (state) => {
    mswServer.use(http.get(`${base}/lifecycle-preview`, () => HttpResponse.json({ ...preview,
      draft: { ...preview.draft, authorization_status: state === 'pending' ? 'pending' : 'authorized' },
      publication: state === 'published' ? { id, draft_revision: 1, eligibility: 'eligible', related_version: 'v1' } : null,
    })))
    setup('publish')
    await screen.findByText(state === 'pending' ? /请先编辑菜品/ : /已经发布，无需重复发布/)
    expect(screen.queryByRole('button', { name: '确认发布版本' })).not.toBeInTheDocument()
  })

  it.each([401, 403])('读取 %s 交给认证边界，不展示菜品详情', async (status) => {
    mswServer.use(http.get(`${base}/lifecycle-preview`, () => HttpResponse.json({}, { status })))
    const props = setup()
    await waitFor(() => expect(props.onSecurityError).toHaveBeenCalledWith(expect.objectContaining({ status })))
    expect(screen.queryByText(/担担饭/)).not.toBeInTheDocument()
  })
})
