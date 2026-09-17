import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'
import { RecipeListPage } from './RecipeListPage'

vi.mock('@/auth/AdminAuthProvider', () => ({ useAdminAuth: () => ({ accessToken: 'test-runtime-token', clearSession: vi.fn() }) }))

const base = '/api/v1/admin/recipe-candidates'
const candidate = { id: 'f2d9dbfc-2149-4d0e-bb36-b9d0cdb750f2', catalog_food_name: '辣椒炒肉', meal_slot: 'lunch', portion_grams: '180', portion_description: '1 盘', method_tags: ['炒'], flavour_tags: ['微辣'], status: 'pending', revision: 1 }

function setup() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RecipeListPage /></QueryClientProvider>)
}

describe('RecipeListPage', () => {
  it('可选择当前页并提交批量启用，带上审计原因和幂等键', async () => {
    const user = userEvent.setup()
    mswServer.use(http.get(base, () => HttpResponse.json({ items: [candidate], total: 1, page: 1, page_size: 100 })), http.post(`${base}/enable`, async ({ request }) => {
      expect(request.headers.get('Authorization')).toBe('Bearer test-runtime-token')
      expect(request.headers.get('Idempotency-Key')).toMatch(/.+/)
      expect(await request.json()).toEqual({ ids: [candidate.id], reason: '核对完毕', confirm: true })
      return HttpResponse.json([candidate])
    }))
    setup()
    await user.click(await screen.findByRole('checkbox', { name: '选择 辣椒炒肉' }))
    await user.click(screen.getByRole('button', { name: '批量启用' }))
    await user.type(screen.getByLabelText('操作原因'), '核对完毕')
    await user.click(screen.getByRole('button', { name: '确认操作' }))
    expect(await screen.findByRole('status')).toHaveTextContent('已启用 1 条菜谱候选')
  })

  it('导入显示逐行校验错误并禁止确认', async () => {
    const user = userEvent.setup()
    mswServer.use(http.get(base, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 })), http.post(`${base}/import-preview`, () => HttpResponse.json({ total_rows: 1, valid_rows: 0, rows: [], errors: [{ row: 2, field: '餐次', message: '格式不正确' }] })))
    setup()
    await user.click(screen.getByRole('button', { name: '导入' }))
    const first = new File(['bad'], 'bad.csv', { type: 'text/csv' })
    Object.defineProperty(first, 'text', { value: async () => 'bad' })
    await user.upload(screen.getByLabelText('选择 CSV 文件'), first)
    expect(await screen.findByText(/第 2 行 · 餐次/)).toBeVisible()
    expect(screen.getByRole('button', { name: '确认导入' })).toBeDisabled()
  })

  it('使用服务端分页并保留跨页选择', async () => {
    const user = userEvent.setup()
    const second = { ...candidate, id: '0a4f72d4-ec6b-42af-b876-16df9957bb1b', catalog_food_name: '宫保鸡丁' }
    const pages: string[] = []
    mswServer.use(http.get(base, ({ request }) => {
      const page = new URL(request.url).searchParams.get('page')
      pages.push(page ?? '')
      return HttpResponse.json({ items: page === '2' ? [second] : [candidate], total: 21, page: Number(page), page_size: 20 })
    }))
    setup()
    await user.click(await screen.findByRole('checkbox', { name: '选择 辣椒炒肉' }))
    expect(screen.getByRole('region', { name: '菜谱候选表格' })).toHaveClass('overflow-auto', 'lg:flex-1')
    expect(screen.getByRole('columnheader', { name: '目录菜品' }).closest('thead')).toHaveClass('sticky', 'top-0')
    expect(screen.getByText('已选 1 条')).toBeVisible()
    await user.click(screen.getByRole('button', { name: '下一页' }))
    await screen.findByRole('checkbox', { name: '选择 宫保鸡丁' })
    expect(screen.getByText('已选 1 条')).toBeVisible()
    expect(screen.getByText('第 21–21 条 / 共 21 条')).toBeVisible()
    await waitFor(() => expect(pages).toContain('2'))
  })

  it('全选全部会读取所有页并显示完整选择数量', async () => {
    const user = userEvent.setup()
    const candidates = Array.from({ length: 21 }, (_, index) => ({
      ...candidate,
      id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
      catalog_food_name: `候选菜${index + 1}`,
    }))
    mswServer.use(http.get(base, ({ request }) => {
      const url = new URL(request.url)
      const page = Number(url.searchParams.get('page'))
      const size = Number(url.searchParams.get('page_size'))
      return HttpResponse.json({ items: candidates.slice((page - 1) * size, page * size), total: candidates.length, page, page_size: size })
    }))
    setup()
    await screen.findByRole('checkbox', { name: '选择 候选菜1' })
    await user.click(screen.getByRole('button', { name: '全选全部（21）' }))
    expect(await screen.findByText('已选 21 条')).toBeVisible()
  })
})

it('预览三维分类，重试沿用幂等键并保存后展示分类', async () => {
  const user = userEvent.setup()
  const classification = { version: 'recipe-classification.v1', purpose: 'component', role: 'protein', ingredient_tags: ['livestock'], evidence: '根据菜名', basis: 'name_and_legacy_role' }
  let saved = false
  const keys: string[] = []
  mswServer.use(
    http.get(base, () => HttpResponse.json({ items: [{ ...candidate, classification: saved ? classification : null }], total: 1, page: 1, page_size: 20 })),
    http.post(`${base}/classification-preview`, () => HttpResponse.json({ entries: [{ id: candidate.id, revision: 1, catalog_food_name: candidate.catalog_food_name, classification }], skipped_count: 0 })),
    http.post(`${base}/classification-backfill`, async ({ request }) => {
      keys.push(request.headers.get('Idempotency-Key')!)
      const body = await request.json() as { reason: string }
      expect(body.reason).toBe('回填旧数据')
      if (keys.length === 1) return new HttpResponse(null, { status: 503 })
      saved = true
      return HttpResponse.json({ changed_count: 1 })
    }),
  )
  setup()
  await user.click(await screen.findByRole('checkbox', { name: '选择 辣椒炒肉' }))
  await user.click(screen.getByRole('button', { name: '补齐三维分类' }))
  expect(await screen.findByText(/待补齐 1 条/)).toBeVisible()
  await user.type(screen.getByLabelText('修改原因'), '回填旧数据')
  await user.click(screen.getByRole('button', { name: '保存分类' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('保存未确认')
  await user.click(screen.getByRole('button', { name: '保存分类' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('已补齐 1 条'))
  expect(keys[0]).toBe(keys[1])
  expect(await screen.findByText('畜肉')).toBeVisible()
})

it('编辑三维分类校验原因、依据，并在失败重试时复用请求标识', async () => {
  const user = userEvent.setup()
  const keys: string[] = []
  mswServer.use(http.get(base, () => HttpResponse.json({ items: [candidate], total: 1, page: 1, page_size: 20 })), http.post(`${base}/classification-review`, async ({ request }) => {
    keys.push(request.headers.get('Idempotency-Key')!)
    expect(await request.json()).toMatchObject({ entries: [{ id: candidate.id, revision: 1, classification: { purpose: 'component', role: 'protein', ingredient_tags: ['livestock'], basis: 'admin_review', evidence: '根据菜品配料确认' } }], reason: '纠正用途' })
    return keys.length === 1 ? HttpResponse.json({}, { status: 503 }) : HttpResponse.json({ changed_count: 1 })
  }))
  setup()
  await user.click(await screen.findByRole('button', { name: '编辑 辣椒炒肉 分类' }))
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByText('请填写分类依据')).toBeVisible()
  await user.selectOptions(screen.getByLabelText('配餐用途'), 'component')
  await user.selectOptions(screen.getByLabelText('餐内角色'), 'protein')
  await user.click(screen.getByLabelText('畜肉'))
  await user.type(screen.getByLabelText('分类依据'), '根据菜品配料确认')
  await user.type(screen.getByLabelText('修改原因'), '纠正用途')
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByText(/保存未确认/)).toBeVisible()
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByText('分类已更新，将用于新配餐。')).toBeVisible()
  expect(keys).toHaveLength(2)
  expect(keys[0]).toBe(keys[1])
})
