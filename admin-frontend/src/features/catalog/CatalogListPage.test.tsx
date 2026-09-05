import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { mswServer } from '@/test/setup'
import { CatalogListPage } from './CatalogListPage'

const base = '/api/v1/admin/catalog-drafts'
const draft = { id: 'f2d9dbfc-2149-4d0e-bb36-b9d0cdb750f2', canonical_name: '燕麦', aliases: ['oats'],
  energy_kcal_per_100g: '389', protein_g_per_100g: '16.9', fat_g_per_100g: '6.9', carbohydrate_g_per_100g: '66.3',
  source_name: 'USDA', source_url: 'https://example.test/', authorization_status: 'pending', revision: 1 }
const item = { ...draft, updated_at: '2026-09-05T03:00:00Z' }

function setup() {
  const expired = vi.fn()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><CatalogListPage accessToken="test-runtime-token" onSessionExpired={expired} /></MemoryRouter></QueryClientProvider>)
  return { expired }
}

describe('CatalogListPage', () => {
  it('默认表格，按查询应用筛选、服务端分页，重置条件并按需打开新增或编辑', async () => {
    const user = userEvent.setup()
    const seen: URL[] = []
    mswServer.use(http.get(base, ({ request }) => {
      const url = new URL(request.url); seen.push(url)
      expect(request.headers.get('Authorization')).toBe('Bearer test-runtime-token')
      return HttpResponse.json({ items: [item], total: 24, page: Number(url.searchParams.get('page')), page_size: 20 })
    }), http.get(`${base}/${draft.id}`, () => HttpResponse.json(draft)))
    setup()
    expect(await screen.findByRole('button', { name: '燕麦' })).toBeVisible()
    expect(screen.queryByLabelText('变更原因')).not.toBeInTheDocument()
    await user.type(screen.getByPlaceholderText('搜索名称或别名'), 'oats')
    expect(seen).toHaveLength(1)
    await user.selectOptions(screen.getByLabelText('授权状态'), 'pending')
    await user.click(screen.getByRole('button', { name: '查询' }))
    await waitFor(() => expect(seen.at(-1)?.searchParams.get('search')).toBe('oats'))
    await screen.findByRole('button', { name: '燕麦' })
    await user.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(seen.at(-1)?.searchParams.get('page')).toBe('2'))
    await user.click(screen.getByRole('button', { name: '重置' }))
    await waitFor(() => expect(screen.getByPlaceholderText('搜索名称或别名')).toHaveValue(''))
    await user.click(screen.getByRole('button', { name: '新增' }))
    const dialog = screen.getByRole('dialog', { name: '新增营养目录' })
    expect(within(dialog).getByLabelText('菜品名称')).toHaveValue('')
    await user.click(within(dialog).getByRole('button', { name: '关闭窗口' }))
    await user.click(screen.getByRole('button', { name: '编辑' }))
    expect(await screen.findByRole('dialog', { name: '编辑营养目录' })).toBeVisible()
    expect(within(screen.getByRole('dialog')).getByLabelText('菜品名称')).toHaveValue('燕麦')
  })

  it('导入错误显示行号且禁止提交，通过后才导入；失败重试复用同一幂等键', async () => {
    const user = userEvent.setup()
    const keys: string[] = []
    let valid = false
    let saved = false
    mswServer.use(http.get(base, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 })),
      http.post(`${base}/import-preview`, () => HttpResponse.json({ total_rows: 1, valid_rows: valid ? 1 : 0,
        rows: valid ? [{ ...Object.fromEntries(Object.entries(draft).filter(([key]) => !['id', 'revision'].includes(key))), reason: 'CSV preview' }] : [],
        errors: valid ? [] : [{ row: 2, field: '来源链接', message: '格式不正确' }],
      })),
      http.post(`${base}/import`, async ({ request }) => {
        keys.push(request.headers.get('Idempotency-Key')!)
        expect(await request.json()).toMatchObject({ reason: '核对来源后导入', confirm: true, csv_text: 'csv fixture' })
        if (!saved) { saved = true; return HttpResponse.json({}, { status: 500 }) }
        return HttpResponse.json({ imported_count: 1, draft_ids: [draft.id] }, { status: 201 })
      }))
    setup()
    await user.click(screen.getByRole('button', { name: '导入' }))
    const file = new File(['csv fixture'], 'catalog.csv', { type: 'text/csv' })
    Object.defineProperty(file, 'text', { value: async () => 'csv fixture' })
    await user.upload(screen.getByLabelText('选择 CSV 文件'), file)
    expect(await screen.findByText(/第 2 行 · 来源链接/)).toBeVisible()
    expect(screen.getByRole('button', { name: '确认导入' })).toBeDisabled()
    valid = true
    const nextFile = new File(['csv fixture'], 'correct.csv', { type: 'text/csv' })
    Object.defineProperty(nextFile, 'text', { value: async () => 'csv fixture' })
    await user.upload(screen.getByLabelText('选择 CSV 文件'), nextFile)
    await screen.findByText('共 1 条，1 条校验通过。')
    await user.type(screen.getByLabelText('导入原因'), '核对来源后导入')
    await user.click(screen.getByRole('button', { name: '确认导入 1 条' }))
    await screen.findByText(/暂时无法完成导入/)
    await user.click(screen.getByRole('button', { name: '确认导入 1 条' }))
    expect(await screen.findByText(/成功导入 1 条草稿/)).toBeVisible()
    expect(keys).toHaveLength(2)
    expect(keys[0]).toBe(keys[1])
  })

  it('读取失败可重试，403 不显示缓存列表或导入入口', async () => {
    const user = userEvent.setup()
    mswServer.use(http.get(base, () => HttpResponse.json({}, { status: 500 })))
    setup()
    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法加载目录')
    mswServer.use(http.get(base, () => HttpResponse.json({}, { status: 403 })))
    await user.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByRole('heading', { name: '无后台访问权限' })).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '导入' })).not.toBeInTheDocument()
  })
})
