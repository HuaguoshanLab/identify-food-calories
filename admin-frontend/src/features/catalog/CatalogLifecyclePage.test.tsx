import { HttpResponse, http } from 'msw'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'

import { CatalogLifecyclePage } from './CatalogLifecyclePage'

const apiBase = '/api/v1/admin'
const draftId = '9a79c487-2c83-4b26-b9ae-7607ebba7a89'
const publicationId = '87e28c97-10ce-4a6d-bd67-2b43c37fd113'

const lifecyclePreview = {
  draft: {
    id: draftId,
    canonical_name: '燕麦',
    aliases: ['燕麦片', 'oats'],
    energy_kcal_per_100g: '389',
    protein_g_per_100g: '16.9',
    fat_g_per_100g: '6.9',
    carbohydrate_g_per_100g: '66.3',
    source_name: 'USDA FoodData Central',
    source_url: 'https://fdc.nal.usda.gov/',
    authorization_status: 'authorized',
    revision: 3,
  },
  publication: {
    id: publicationId,
    draft_revision: 2,
    eligibility: 'eligible',
    related_version: 'catalog-v2',
  },
  field_diffs: [
    { field: 'canonical_name', before: '即食燕麦', after: '燕麦', change: 'modified' },
    { field: 'aliases', before: '燕麦片', after: '燕麦片、oats', change: 'added' },
    { field: 'energy_kcal_per_100g', before: '376', after: '389', change: 'modified' },
    { field: 'source_name', before: '旧来源', after: 'USDA FoodData Central', change: 'modified' },
    { field: 'authorization_status', before: 'pending', after: 'authorized', change: 'modified' },
  ],
  impact: { affected_catalog_items: 1, description: '新分析和新餐单将使用此不可变版本。' },
}

const auditPage = {
  items: [{
    id: '3c33167c-4660-47b8-a822-5c02e04ef4f7',
    actor_identifier: 'admin-42',
    occurred_at: '2026-09-03T04:20:00Z',
    action: 'catalog.publish',
    object_type: 'catalog_publication',
    object_id: publicationId,
    reason: '已完成来源复核',
    before: { authorization_status: 'pending' },
    after: { authorization_status: 'authorized' },
    related_version: 'catalog-v3',
    command_key: 'safe-command-key',
  }],
  next_cursor: null,
}

function renderPage() {
  const onSessionExpired = vi.fn()
  render(<CatalogLifecyclePage accessToken="runtime-only-token" draftId={draftId} onSessionExpired={onSessionExpired} />)
  return { onSessionExpired }
}

describe('CatalogLifecyclePage', () => {
  it('以两列可读 diff 和影响数量预览审核，不暴露 raw JSON 或敏感字段', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json(lifecyclePreview)),
      http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)),
    )
    renderPage()

    const preview = await screen.findByRole('region', { name: '发布前字段差异' })
    expect(within(preview).getByRole('columnheader', { name: '当前值' })).toBeVisible()
    expect(within(preview).getByRole('columnheader', { name: '拟发布值' })).toBeVisible()
    expect(within(preview).getAllByText('已修改')).not.toHaveLength(0)
    expect(within(preview).getByText('已新增')).toBeVisible()
    expect(within(preview).getByText('受影响菜品数量：1')).toBeVisible()
    expect(screen.queryByText(/raw_json|api_key|runtime-only-token|provider body/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '审核目录草稿' }))
    await user.click(await screen.findByRole('button', { name: '确认审核草稿' }))
    expect(await screen.findByText('请说明此次变更原因。')).toBeVisible()
  })

  it('发布必须在带理由的取消优先确认后触发，提交期间拒绝重复', async () => {
    const user = userEvent.setup()
    let release: (() => void) | undefined
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json(lifecyclePreview)),
      http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)),
      http.post(`${apiBase}/catalog-drafts/${draftId}/publish`, async ({ request }) => {
        expect(request.headers.get('Idempotency-Key')).toHaveLength(36)
        expect(await request.json()).toEqual({ reason: '已完成证据复核', confirm: true })
        await new Promise<void>((resolve) => { release = resolve })
        return HttpResponse.json({ id: publicationId, draft_id: draftId, draft_revision: 3, content_hash: 'a'.repeat(64), eligibility: 'eligible' })
      }),
    )
    renderPage()
    await screen.findByRole('region', { name: '发布前字段差异' })

    await user.click(screen.getByRole('button', { name: '发布营养目录版本' }))
    const dialog = await screen.findByRole('alertdialog', { name: '发布营养目录版本？' })
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus())
    await user.type(within(dialog).getByLabelText('变更原因'), '已完成证据复核')
    const confirm = within(dialog).getByRole('button', { name: '确认发布版本' })
    await user.click(confirm)
    expect(confirm).toBeDisabled()
    release?.()
    expect(await screen.findByText('已发布版本 v3，操作已记录。')).toBeVisible()
  })

  it('失格确认明确只阻止未来使用，409 保留理由与最新 diff', async () => {
    const user = userEvent.setup()
    let previewCalls = 0
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => {
        previewCalls += 1
        return HttpResponse.json({ ...lifecyclePreview, draft: { ...lifecyclePreview.draft, revision: previewCalls + 2 } })
      }),
      http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)),
      http.post(`${apiBase}/catalog-publications/${publicationId}/disqualifications`, () => HttpResponse.json({ detail: 'catalog lifecycle conflict' }, { status: 409 })),
    )
    renderPage()
    await screen.findByRole('region', { name: '发布前字段差异' })

    await user.click(screen.getByRole('button', { name: '立即失格' }))
    const dialog = await screen.findByRole('alertdialog', { name: '确认立即失格？' })
    expect(within(dialog).getByText('仅阻止后续分析和新餐单使用该条目，不重算或删除历史餐食快照。')).toBeVisible()
    await user.type(within(dialog).getByLabelText('变更原因'), '授权状态已撤销')
    await user.click(within(dialog).getByRole('button', { name: '确认立即失格' }))

    expect(await screen.findByText('此草稿已被其他管理员更新。请查看最新差异后重新确认。')).toBeVisible()
    expect(previewCalls).toBe(2)
    expect(within(await screen.findByRole('alertdialog')).getByLabelText('变更原因')).toHaveValue('授权状态已撤销')
  })

  it('401 清空会话，403 固定拒绝，审计时间线只渲染 allowlist 字段', async () => {
    const user = userEvent.setup()
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json({ error: { code: 'AUTHENTICATION_REQUIRED' } }, { status: 401 })),
    )
    const { onSessionExpired } = renderPage()
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce())
    expect(screen.getByText('登录已失效，请重新登录。')).toBeVisible()

    cleanup()
    mswServer.use(http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json({ error: { code: 'ADMIN_PERMISSION_REQUIRED' } }, { status: 403 })))
    renderPage()
    expect(await screen.findByRole('heading', { name: '无后台访问权限' })).toBeVisible()

    cleanup()
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json(lifecyclePreview)),
      http.get(`${apiBase}/audit`, () => HttpResponse.json({ items: [{ ...auditPage.items[0], before: { api_key: 'secret', authorization_status: 'pending' }, after: { provider_body: 'secret', authorization_status: 'authorized' } }], next_cursor: null })),
    )
    renderPage()
    await screen.findByRole('heading', { name: '操作审计' })
    expect(screen.getByText(/已完成来源复核/)).toBeVisible()
    expect(screen.queryByText(/api_key|provider_body|secret/i)).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
  })
})
