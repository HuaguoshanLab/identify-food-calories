import { http, HttpResponse } from 'msw'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { CatalogDraftPage } from './CatalogDraftPage'
import { mswServer } from '@/test/setup'

const apiBase = '/api/v1/admin'

const createdDraft = {
  id: 'f2d9dbfc-2149-4d0e-bb36-b9d0cdb750f2',
  canonical_name: '燕麦',
  aliases: ['燕麦片', 'oats'],
  energy_kcal_per_100g: '389',
  protein_g_per_100g: '16.9',
  fat_g_per_100g: '6.9',
  carbohydrate_g_per_100g: '66.3',
  source_name: 'USDA FoodData Central',
  source_url: 'https://fdc.nal.usda.gov/',
  authorization_status: 'authorized',
  revision: 1,
}

const serverPreview = {
  draft_id: null,
  base_revision: 0,
  field_diffs: [
    { field: 'canonical_name', before: null, after: '燕麦' },
    { field: 'energy_kcal_per_100g', before: null, after: '389' },
  ],
  impact_categories: ['catalog_identity', 'nutrition_per_100g'],
}

function renderPage() {
  const onSessionExpired = vi.fn()
  render(
    <MemoryRouter>
      <CatalogDraftPage accessToken="runtime-only-token" onSessionExpired={onSessionExpired} />
    </MemoryRouter>,
  )
  return { onSessionExpired }
}

async function fillDraft(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('菜品名称'), '燕麦')
  await user.type(screen.getByLabelText('别名'), '燕麦片, oats')
  await user.type(screen.getByLabelText('每 100g 能量（kcal）'), '389')
  await user.type(screen.getByLabelText('每 100g 蛋白质（g）'), '16.9')
  await user.type(screen.getByLabelText('每 100g 脂肪（g）'), '6.9')
  await user.type(screen.getByLabelText('每 100g 碳水（g）'), '66.3')
  await user.type(screen.getByLabelText('来源名称'), 'USDA FoodData Central')
  await user.type(screen.getByLabelText('来源链接'), 'https://fdc.nal.usda.gov/')
  await user.selectOptions(screen.getByLabelText('授权状态'), 'authorized')
  await user.type(screen.getByLabelText('变更原因'), '补充已授权的基础营养数据')
}

describe('CatalogDraftPage', () => {
  it('通过键盘填写严格字段，预览受控命令，并发送 Idempotency-Key', async () => {
    const user = userEvent.setup()
    let idempotencyKey = ''
    let releaseResponse: (() => void) | undefined
    let markRequestStarted: (() => void) | undefined
    const requestStarted = new Promise<void>((resolve) => { markRequestStarted = resolve })
    mswServer.use(http.post(`${apiBase}/catalog-drafts/preview`, async ({ request }) => {
      expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
      expect(await request.json()).not.toHaveProperty('reason')
      return HttpResponse.json(serverPreview)
    }))
    mswServer.use(http.post(`${apiBase}/catalog-drafts`, async ({ request }) => {
      idempotencyKey = request.headers.get('Idempotency-Key') ?? ''
      expect(request.headers.get('Authorization')).toBe('Bearer runtime-only-token')
      markRequestStarted?.()
      await new Promise<void>((resolve) => { releaseResponse = resolve })
      return HttpResponse.json(createdDraft, { status: 201 })
    }))
    renderPage()

    await fillDraft(user)
    await user.tab()
    expect(screen.getByRole('button', { name: '预览并确认' })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: '预览并确认' }))

    const dialog = await screen.findByRole('alertdialog', { name: '确认创建营养目录草稿？' })
    expect(dialog).toBeVisible()
    expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
    expect(within(dialog).getByText('服务器字段差异')).toBeVisible()
    expect(within(dialog).getByText(/目录名称与别名、每 100g 营养数值/)).toBeVisible()
    expect(within(dialog).getByText(/→ 燕麦/)).toBeVisible()
    expect(screen.queryByText(/raw_json|api_key|runtime-only-token/i)).not.toBeInTheDocument()

    const confirm = screen.getByRole('button', { name: '确认创建草稿' })
    await user.click(confirm)
    await requestStarted
    expect(confirm).toBeDisabled()
    releaseResponse?.()

    await waitFor(() => expect(idempotencyKey).toHaveLength(36))
    expect(await screen.findByText('草稿已保存，当前 revision 为 1。')).toBeVisible()
    expect(screen.getByRole('link', { name: '审核与发布目录' })).toHaveAttribute('href', `/admin/catalog/${createdDraft.id}/lifecycle`)
  })

  it('PATCH 409 后读取当前草稿并重新展示服务器计算的最新差异，不自动覆盖编辑', async () => {
    const user = userEvent.setup()
    let previewCalls = 0
    let readCalls = 0
    mswServer.use(http.post(`${apiBase}/catalog-drafts/preview`, () => {
      previewCalls += 1
      return HttpResponse.json(previewCalls === 1 ? serverPreview : {
        draft_id: createdDraft.id,
        base_revision: 2,
        field_diffs: [{ field: 'canonical_name', before: '服务器更新的燕麦', after: '有机燕麦' }],
        impact_categories: ['catalog_identity'],
      })
    }))
    mswServer.use(http.post(`${apiBase}/catalog-drafts`, () => HttpResponse.json({
      ...createdDraft,
    }, { status: 201 })))
    mswServer.use(http.patch(`${apiBase}/catalog-drafts/${createdDraft.id}`, () => HttpResponse.json({
      detail: 'catalog draft command conflict',
    }, { status: 409 })))
    mswServer.use(http.get(`${apiBase}/catalog-drafts/${createdDraft.id}`, () => {
      readCalls += 1
      return HttpResponse.json({ ...createdDraft, canonical_name: '服务器更新的燕麦', revision: 2 })
    }))
    renderPage()
    await fillDraft(user)
    await user.click(screen.getByRole('button', { name: '预览并确认' }))
    await user.click(await screen.findByRole('button', { name: '确认创建草稿' }))

    await screen.findByText('草稿已保存，当前 revision 为 1。')
    const nameInput = screen.getByRole('textbox', { name: '菜品名称' })
    await user.clear(nameInput)
    await user.type(nameInput, '有机燕麦')
    await user.click(screen.getByRole('button', { name: '预览并确认' }))
    await user.click(await screen.findByRole('button', { name: '确认更新草稿' }))

    expect(await screen.findByText('此草稿已被其他管理员更新。以下为基于最新服务器版本重新计算的差异，请再次确认。')).toBeVisible()
    expect(readCalls).toBe(1)
    expect(await screen.findByText(/服务器更新的燕麦 → 有机燕麦/)).toBeVisible()
    expect(nameInput).toHaveValue('有机燕麦')
    expect(screen.getByDisplayValue('补充已授权的基础营养数据')).toBeVisible()
    expect(screen.getByRole('button', { name: '确认更新草稿' })).toBeEnabled()
  })

  it('401 清除会话且不显示目录数据，403 只显示固定无权页', async () => {
    const user = userEvent.setup()
    mswServer.use(http.post(`${apiBase}/catalog-drafts/preview`, () => HttpResponse.json({
      error: { code: 'AUTHENTICATION_REQUIRED' },
    }, { status: 401 })))
    const { onSessionExpired } = renderPage()
    await fillDraft(user)
    await user.click(screen.getByRole('button', { name: '预览并确认' }))
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce())
    expect(screen.getByText('登录已失效，请重新登录。')).toBeVisible()
    expect(screen.queryByText('燕麦')).not.toBeInTheDocument()

    mswServer.use(http.post(`${apiBase}/catalog-drafts/preview`, () => HttpResponse.json({
      error: { code: 'ADMIN_PERMISSION_REQUIRED' },
    }, { status: 403 })))
    renderPage()
    await fillDraft(user)
    await user.click(screen.getByRole('button', { name: '预览并确认' }))
    expect(await screen.findByRole('heading', { name: '无后台访问权限' })).toBeVisible()
    expect(screen.getByText('你的当前账号没有管理权限。请使用管理员账号登录。')).toBeVisible()
    expect(screen.queryByText('燕麦')).not.toBeInTheDocument()
  })
})
