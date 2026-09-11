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

const embeddingStatus = {
  publication_id: publicationId,
  status: 'partial_failure',
  pending_count: 1,
  processing_count: 0,
  failed_count: 1,
  completed_count: 1,
  jobs: [
    { id: '7d9cbff6-334c-4d48-a29e-612f59e3e545', vector_space_id: '4c1b5f8d-cad6-424d-97c8-e6ec4f500274', status: 'completed', attempt_count: 1, max_attempts: 3, last_error_code: null, created_at: '2026-09-03T04:20:00Z', updated_at: '2026-09-03T04:21:00Z' },
    { id: '61bb3bb4-a7c3-48a8-8c44-d0e71f4a4a72', vector_space_id: '54dbf6c4-38a9-4643-a962-d6f2a468260b', status: 'failed', attempt_count: 1, max_attempts: 3, last_error_code: 'UPSTREAM_UNAVAILABLE', created_at: '2026-09-03T04:20:00Z', updated_at: '2026-09-03T04:21:00Z' },
    { id: 'ea212a59-0e67-4e36-bb79-202fdbf02531', vector_space_id: 'a065bd86-9969-4744-b870-56dd3da1e493', status: 'pending', attempt_count: 0, max_attempts: 3, last_error_code: null, created_at: '2026-09-03T04:20:00Z', updated_at: '2026-09-03T04:21:00Z' },
  ],
}

function renderPage() {
  const onSessionExpired = vi.fn()
  render(<CatalogLifecyclePage accessToken="runtime-only-token" draftId={draftId} onSessionExpired={onSessionExpired} />)
  return { onSessionExpired }
}

describe('CatalogLifecyclePage', () => {
  it.each([
    ['pending', '等待处理'], ['processing', '正在处理'], ['partial_failure', '部分失败'], ['failed', '处理失败'], ['ready', '已就绪'],
  ])('展示 %s 聚合状态而不泄露目录名称、向量或 Provider 详情', async (status, label) => {
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json(lifecyclePreview)),
      http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)),
      http.get(`${apiBase}/catalog-publications/${publicationId}/embedding-status`, () => HttpResponse.json({ ...embeddingStatus, status })),
    )
    renderPage()

    const statusSection = await screen.findByRole('region', { name: '嵌入构建状态' })
    expect(within(statusSection).getByText(label)).toBeVisible()
    expect(screen.queryByText(/燕麦|vector|provider|embedding/i)).not.toBeInTheDocument()
  })

  it('列出多条安全作业并只允许一个 publication 级批量重试', async () => {
    const user = userEvent.setup()
    let retryCalls = 0
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json(lifecyclePreview)),
      http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)),
      http.get(`${apiBase}/catalog-publications/${publicationId}/embedding-status`, () => HttpResponse.json(embeddingStatus)),
      http.post(`${apiBase}/catalog-publications/${publicationId}/embedding-retries`, async ({ request }) => {
        retryCalls += 1
        expect(request.headers.get('Idempotency-Key')).toHaveLength(36)
        expect(await request.json()).toEqual({ reason: '服务已恢复，重新排队' })
        return HttpResponse.json({ ...embeddingStatus, status: 'pending', failed_count: 0, pending_count: 2, reset_count: 1 })
      }),
    )
    renderPage()
    const statusSection = await screen.findByRole('region', { name: '嵌入构建状态' })
    expect(within(statusSection).getAllByRole('row')).toHaveLength(4)
    expect(within(statusSection).getByText('UPSTREAM_UNAVAILABLE')).toBeVisible()

    await user.click(screen.getByRole('button', { name: '重试 1 个可恢复任务' }))
    const dialog = await screen.findByRole('alertdialog', { name: '重新排队可恢复的嵌入任务？' })
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus())
    await user.type(within(dialog).getByLabelText('变更原因'), '服务已恢复，重新排队')
    const confirm = within(dialog).getByRole('button', { name: '确认重新排队' })
    await user.click(confirm)
    expect(confirm).toBeDisabled()
    expect(await screen.findByText('已重新排队 1 个可恢复任务，操作已记录。')).toBeVisible()
    expect(retryCalls).toBe(1)
  })

  it('409 重新读取状态，拒绝额外字段且保留已填写的重试理由', async () => {
    const user = userEvent.setup()
    let statusCalls = 0
    mswServer.use(
      http.get(`${apiBase}/catalog-drafts/${draftId}/lifecycle-preview`, () => HttpResponse.json(lifecyclePreview)),
      http.get(`${apiBase}/audit`, () => HttpResponse.json(auditPage)),
      http.get(`${apiBase}/catalog-publications/${publicationId}/embedding-status`, () => {
        statusCalls += 1
        return HttpResponse.json(statusCalls === 1 ? { ...embeddingStatus, provider_body: 'forbidden' } : embeddingStatus)
      }),
      http.post(`${apiBase}/catalog-publications/${publicationId}/embedding-retries`, () => HttpResponse.json({ detail: 'conflict' }, { status: 409 })),
    )
    renderPage()
    expect(await screen.findByText('暂时无法加载嵌入构建状态，请稍后重试。')).toBeVisible()
    await waitFor(() => expect(screen.queryByRole('button', { name: /重试 .*可恢复任务/ })).not.toBeInTheDocument())

    // A subsequent safe projection makes the action available; conflict keeps the operator's reason for review.
    await user.click(screen.getByRole('button', { name: '审核目录草稿' }))
    await user.keyboard('{Escape}')
    await waitFor(() => expect(statusCalls).toBeGreaterThan(1))
    await user.click(screen.getByRole('button', { name: '重试 1 个可恢复任务' }))
    const dialog = await screen.findByRole('alertdialog', { name: '重新排队可恢复的嵌入任务？' })
    await user.type(within(dialog).getByLabelText('变更原因'), '请重新检查')
    await user.click(within(dialog).getByRole('button', { name: '确认重新排队' }))
    expect(await screen.findByText('嵌入任务状态已变化。请查看最新状态后重新确认。')).toBeVisible()
    expect(within(await screen.findByRole('alertdialog')).getByLabelText('变更原因')).toHaveValue('请重新检查')
  })

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
