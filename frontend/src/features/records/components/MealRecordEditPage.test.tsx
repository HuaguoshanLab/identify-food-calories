import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext } from '@/auth/AuthContext'
import { MealRecordEditPage } from './MealRecordEditPage'

const id = 'f2d9dbfc-2149-4d0e-bb36-b9d0cdb750f2'
const record = { id, meal_slot: null, consumed_at: '2026-01-01T00:00:00Z', consumed_time_zone: 'UTC', consumed_local_date: '2026-01-01', local_date_source: 'submitted_time_zone', nutrition_catalog_version: 'v1', calculation_version: 'v1', energy_kcal: '130', protein_g: '2', fat_g: '1', carbohydrate_g: '28', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', items: [] }
function setup(fail = false) {
  const request = vi.fn(async (_path: string, init?: RequestInit) => new Response(JSON.stringify(record), { status: fail && init?.method === 'PATCH' ? 500 : 200 }))
  render(<QueryClientProvider client={new QueryClient()}><AuthContext.Provider value={{ request, login: vi.fn(), logout: vi.fn(), retryBootstrap: vi.fn(), status: 'authenticated' }}><MemoryRouter initialEntries={[`/app/records/${id}/edit`]}><Routes><Route path="/app/records/:recordId/edit" element={<MealRecordEditPage />} /><Route path="/app/records/:recordId" element={<p>详情已更新</p>} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>)
  return request
}

describe('餐食编辑', () => {
  it('旧记录显示未分类，补选早餐后改时间不覆盖餐次，提交包含时区', async () => {
    const user = userEvent.setup(); const request = setup()
    await waitFor(() => expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled())
    expect(screen.getByLabelText('餐次')).toHaveValue('')
    await user.selectOptions(screen.getByLabelText('餐次'), 'breakfast')
    const input = screen.getByLabelText('用餐时间')
    await user.clear(input); await user.type(input, '2026-01-02T20:00')
    expect(screen.getByLabelText('餐次')).toHaveValue('breakfast')
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(await screen.findByText('详情已更新')).toBeInTheDocument()
    const sent = request.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(JSON.parse(String(sent?.[1]?.body))).toEqual({ meal_slot: 'breakfast', consumed_at: new Date('2026-01-02T20:00').toISOString(), time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone })
  })
  it('未来时间不发送请求，保存失败保留用户填写内容', async () => {
    const user = userEvent.setup(); const request = setup(true)
    await waitFor(() => expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled())
    await user.selectOptions(screen.getByLabelText('餐次'), 'snack')
    const input = screen.getByLabelText('用餐时间')
    await user.clear(input); await user.type(input, '2099-01-01T12:00')
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请选择有效的当前或过去用餐时间')
    expect(request.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
    await user.clear(input); await user.type(input, '2026-01-01T12:00')
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(await screen.findByText('保存失败，请检查用餐时间或稍后重试。')).toBeInTheDocument()
    expect(screen.getByLabelText('餐次')).toHaveValue('snack')
    expect(input).toHaveValue('2026-01-01T12:00')
  })
})
