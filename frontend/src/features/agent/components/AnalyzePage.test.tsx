import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { AnalyzePage } from './AnalyzePage'

function renderPage(request: AuthContextValue['request'] = vi.fn(async () => new Response('{}', { status: 500 }))) {
  return render(<AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}><AnalyzePage /></AuthContext.Provider>)
}

describe('AnalyzePage', () => {
  afterEach(() => window.history.replaceState({}, '', '/'))
  it('uses a labelled text input and does not invent a report before an API response', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: '分析这餐' })).toBeInTheDocument()
    expect(screen.getByLabelText('餐食描述')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '营养分析报告' })).not.toBeInTheDocument()
  })

  it('explains empty and too-long descriptions next to the input', async () => {
    const user = userEvent.setup({ applyAccept: false })
    renderPage()
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(screen.getByText('请先描述这餐吃了什么。')).toBeInTheDocument()
    await user.type(screen.getByLabelText('餐食描述'), 'a'.repeat(1001))
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(screen.getByText('描述最多可输入 1000 个字符。')).toBeInTheDocument()
  })

  it('uploads an image through the generated multipart contract and discloses estimated weight', async () => {
    const user = userEvent.setup()
    const threadId = '11111111-1111-4111-8111-111111111111'
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      void init
      if (path === '/agent/threads/image') return new Response(JSON.stringify({ thread_id: threadId, status: 'partial', revision: 0 }), { status: 201 })
      if (path.endsWith('/images')) return new Response(JSON.stringify({ thread_id: threadId, image_id: '22222222-2222-4222-8222-222222222222', status: 'completed' }), { status: 202 })
      if (path === `/agent/threads/${threadId}`) return new Response(JSON.stringify({
        thread_id: threadId, status: 'completed', revision: 1,
        report: { items: [{ item_id: 'rice-1', name: '米饭', grams: '100', energy_kcal: '130.0', protein_g: '2.7', fat_g: '0.3', carbohydrate_g: '28.0', is_estimated: true }], totals: { energy_kcal: '130.0', protein_g: '2.7', fat_g: '0.3', carbohydrate_g: '28.0' } },
      }), { status: 200 })
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await user.upload(screen.getByLabelText('从相册选择上传'), new File(['meal'], 'meal.jpg', { type: 'image/jpeg' }))

    expect(await screen.findByRole('heading', { name: '营养分析报告' })).toBeInTheDocument()
    expect(screen.getByText('估算重量')).toBeInTheDocument()
    expect(screen.getByText('估算重量，可能与实际份量存在偏差。')).toBeInTheDocument()
    const upload = request.mock.calls.find(([path]) => String(path).endsWith('/images'))
    expect(upload?.[0]).toBe(`/agent/threads/${threadId}/images`)
    expect(upload?.[1]?.body).toBeInstanceOf(FormData)
    expect(new Headers(upload?.[1]?.headers).get('Idempotency-Key')).toMatch(/^image-/)
  })

  it('keeps unsupported files local and places the safe error beside upload controls', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const request = vi.fn()
    renderPage(request)

    await user.upload(screen.getByLabelText('从相册选择上传'), new File(['not-an-image'], 'meal.txt', { type: 'text/plain' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('请选择 JPG、PNG 或 WebP 格式的餐食图片。')
    expect(request).not.toHaveBeenCalled()
  })

  it('does not leave an old running summary beside a terminal image failure', async () => {
    const threadId = '11111111-1111-4111-8111-111111111111'
    window.history.replaceState({}, '', `/app/analyze?thread=${threadId}`)
    const request = vi.fn(async (path: string) => {
      if (path.endsWith('/events')) return new Response('', { status: 200 })
      return new Response(JSON.stringify({ thread_id: threadId, status: 'retryable', revision: 2, report: null, recovery_code: 'VISION_ANALYSIS_FAILED' }))
    })
    renderPage(request)

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('本次分析暂未完成'))
    expect(screen.getByRole('alert')).toHaveTextContent('图片未能识别')
    expect(screen.queryByText('分析任务正在运行。')).not.toBeInTheDocument()
  })

  it('renders authoritative nutrition values with Chinese controlled-food display names', async () => {
    const user = userEvent.setup()
    const request = vi.fn(async () => new Response(JSON.stringify({
      thread_id: '11111111-1111-4111-8111-111111111111', status: 'completed', revision: 1,
      report: { items: [
        { item_id: 'rice-1', name: 'Rice, white, long-grain, regular, cooked, enriched', grams: '100', energy_kcal: '130.0' },
        { item_id: 'chicken-1', name: 'Chicken breast, cooked, skinless', grams: '120', energy_kcal: '198.0' },
      ], totals: { energy_kcal: '328.0', protein_g: '39.9', fat_g: '4.6', carbohydrate_g: '28.2' }, disclaimer: '普通饮食参考，不替代医疗建议。' },
    }), { status: 201 }))
    renderPage(request)
    await user.type(screen.getByLabelText('餐食描述'), '米饭 100 克')
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(await screen.findByRole('heading', { name: '营养分析报告' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '米饭' })).toBeInTheDocument()
    expect(screen.getByText('100g · 130.0 kcal')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '鸡胸肉' })).toBeInTheDocument()
    expect(screen.getByText('120g · 198.0 kcal')).toBeInTheDocument()
    expect(screen.queryByText(/Rice, white/)).not.toBeInTheDocument()
    expect(screen.getByText('合计 328.0 kcal')).toBeInTheDocument()
  })

  it('does not present an all-unmatched meal as a complete zero-calorie report', async () => {
    const user = userEvent.setup()
    const request = vi.fn(async () => new Response(JSON.stringify({
      thread_id: '11111111-1111-4111-8111-111111111111', status: 'completed', revision: 1,
      report: {
        items: [], unaccounted_items: ['目录外菜品'], is_partial: true,
        totals: { energy_kcal: '0.0', protein_g: '0.0', fat_g: '0.0', carbohydrate_g: '0.0' },
      },
    }), { status: 201 }))
    renderPage(request)

    await user.type(screen.getByLabelText('餐食描述'), '目录外菜品 100 克')
    await user.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByText('无法生成营养报告')).toBeInTheDocument()
    expect(screen.getByText(/未匹配菜品：目录外菜品。/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '营养分析报告' })).not.toBeInTheDocument()
    expect(screen.queryByText('合计 0.0 kcal')).not.toBeInTheDocument()
  })

  it('requires confirmation before closing the stream, cache, and thread after deletion', async () => {
    const user = userEvent.setup()
    const snapshotBody = {
        thread_id: '11111111-1111-4111-8111-111111111111', status: 'completed', revision: 1,
        report: { items: [], totals: { energy_kcal: '130.0', protein_g: '2.7', fat_g: '0.3', carbohydrate_g: '28.2' }, disclaimer: '普通饮食参考，不替代医疗建议。' },
    }
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') return new Response(JSON.stringify({ thread_id: snapshotBody.thread_id, status: 'deletion_pending', due_at: '2026-08-30T00:00:00Z' }), { status: 202 })
      return new Response(JSON.stringify(snapshotBody), { status: path === '/agent/threads' ? 201 : 200 })
    })
    renderPage(request)
    await user.type(screen.getByLabelText('餐食描述'), '米饭 100 克')
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    await user.click(await screen.findByRole('button', { name: '删除这次分析' }))
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('数据将在 24 小时内删除。', { exact: false })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认删除' }))
    expect(await screen.findByText('删除请求已提交：分析、事件流和本地缓存已关闭，数据将在 24 小时内清理。')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '营养分析报告' })).not.toBeInTheDocument()
    expect(request).toHaveBeenLastCalledWith('/agent/threads/11111111-1111-4111-8111-111111111111', { method: 'DELETE' })
  })

  it('presents one complete clarification batch without selecting a candidate by default', async () => {
    const user = userEvent.setup()
    const request = vi.fn(async () => new Response(JSON.stringify({
      thread_id: '11111111-1111-4111-8111-111111111111', status: 'waiting', revision: 1,
      report: {
        understood_items: [{ item_id: 'rice-1', name: '米饭', grams: null }],
        questions: [{
          item_id: 'rice-1', field: 'food', message: '请选择米饭对应的食物。',
          candidates: [
            { item_id: 'rice-1', food_id: '11111111-1111-4111-8111-111111111111', catalog_version: 'fdc-v1', label: '熟米饭' },
            { item_id: 'rice-1', food_id: '22222222-2222-4222-8222-222222222222', catalog_version: 'fdc-v1', label: '生米饭' },
          ],
        }],
        unaccounted_items: [], is_partial: false, waiting_input: true,
      },
    }), { status: 201 }))
    renderPage(request)

    await user.type(screen.getByLabelText('餐食描述'), '米饭')
    await user.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByRole('heading', { name: '需要补充的信息' })).toBeInTheDocument()
    expect(screen.getByText('已理解的项目')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '熟米饭' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '生米饭' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('localizes known catalog candidate labels while preserving unknown labels', async () => {
    const user = userEvent.setup()
    const request = vi.fn(async () => new Response(JSON.stringify({
      thread_id: '11111111-1111-4111-8111-111111111111', status: 'waiting', revision: 1,
      report: {
        questions: [{
          item_id: 'rice-1', field: 'food', message: '请选择候选食物。',
          candidates: [
            { item_id: 'rice-1', food_id: '11111111-1111-4111-8111-111111111111', catalog_version: 'fdc-v1', label: 'Rice, white, long-grain, regular, cooked, enriched（cooked）' },
            { item_id: 'rice-1', food_id: '22222222-2222-4222-8222-222222222222', catalog_version: 'fdc-v1', label: 'Custom pantry label' },
          ],
        }],
        unaccounted_items: [], is_partial: false, waiting_input: true,
      },
    }), { status: 201 }))
    renderPage(request)

    await user.type(screen.getByLabelText('餐食描述'), '米饭')
    await user.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByRole('button', { name: '米饭' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Custom pantry label' })).toHaveAttribute('aria-pressed', 'false')
  })
})
