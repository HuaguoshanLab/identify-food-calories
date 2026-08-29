import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { AnalyzePage } from './AnalyzePage'

function renderPage(request: AuthContextValue['request'] = vi.fn(async () => new Response('{}', { status: 500 }))) {
  return render(<AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}><AnalyzePage /></AuthContext.Provider>)
}

describe('AnalyzePage', () => {
  it('uses a labelled text input and does not invent a report before an API response', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: '描述这餐吃了什么' })).toBeInTheDocument()
    expect(screen.getByLabelText('餐食描述')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '营养分析报告' })).not.toBeInTheDocument()
  })

  it('explains empty and too-long descriptions next to the input', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(screen.getByText('请先描述这餐吃了什么。')).toBeInTheDocument()
    await user.type(screen.getByLabelText('餐食描述'), 'a'.repeat(1001))
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(screen.getByText('描述最多可输入 1000 个字符。')).toBeInTheDocument()
  })

  it('renders only the authoritative completed snapshot', async () => {
    const user = userEvent.setup()
    const request = vi.fn(async () => new Response(JSON.stringify({
      thread_id: '11111111-1111-4111-8111-111111111111', status: 'completed', revision: 1,
      report: { items: [{ name: '米饭', grams: '100', energy_kcal: '130.0' }], totals: { energy_kcal: '130.0', protein_g: '2.7', fat_g: '0.3', carbohydrate_g: '28.2' }, disclaimer: '普通饮食参考，不替代医疗建议。' },
    }), { status: 201 }))
    renderPage(request)
    await user.type(screen.getByLabelText('餐食描述'), '米饭 100 克')
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(await screen.findByRole('heading', { name: '营养分析报告' })).toBeInTheDocument()
    expect(screen.getByText('合计 130.0 kcal')).toBeInTheDocument()
  })
})
