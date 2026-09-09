import { describe, expect, it, vi } from 'vitest'

import { DashboardTimezoneConflictError, confirmDashboardTimeZone, confirmMealRecord, updateMealRecord } from './client'

const record = {
  id: 'f2d9dbfc-2149-4d0e-bb36-b9d0cdb750f2',
  consumed_at: '2026-09-04T02:00:00+00:00',
  consumed_time_zone: 'Asia/Shanghai',
  consumed_local_date: '2026-09-04',
  local_date_source: 'submitted_time_zone',
  nutrition_catalog_version: 'admin-publication-v1',
  calculation_version: 'nutrition-calculation.v1',
  energy_kcal: '130.0',
  protein_g: '2.6',
  fat_g: '0.3',
  carbohydrate_g: '25.9',
  created_at: '2026-09-04T02:00:00+00:00',
  updated_at: '2026-09-04T02:00:00+00:00',
  items: [{
    id: '3f8ba163-ddf2-4b58-b5b4-455937c19f7d', position: 0, display_name: '白米饭', nutrition_catalog_version: 'admin-publication-v1', grams: '100.0',
    energy_kcal: '130.0', protein_g: '2.6', fat_g: '0.3', carbohydrate_g: '25.9', is_estimated: false,
  }],
}

describe('confirmMealRecord', () => {
  it('提交浏览器 IANA 时区，并严格解析服务器返回的本地日期归属', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(record), { status: 201 }))

    const saved = await confirmMealRecord(request, 'c4683f51-5b02-49a2-898c-d9e30b0f1c72', 'save-7c879dfe-73c2-48d5-ae91-9c0d4eb55bea', { mealSlot: 'breakfast', consumedAt: record.consumed_at })

    expect(JSON.parse(String(request.mock.calls[0][1]?.body))).toEqual({
      meal_slot: 'breakfast', consumed_at: record.consumed_at,
      thread_id: 'c4683f51-5b02-49a2-898c-d9e30b0f1c72',
      command_key: 'save-7c879dfe-73c2-48d5-ae91-9c0d4eb55bea',
      time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
    expect(saved.consumed_local_date).toBe('2026-09-04')
  })
})

describe('confirmDashboardTimeZone', () => {
  it('只向 records confirmation command 提交浏览器 IANA zone，并严格解析安全响应', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      dashboard_time_zone: 'Asia/Shanghai',
      confirmed_at: '2026-09-04T02:00:00Z',
    }), { status: 200 }))

    await expect(confirmDashboardTimeZone(request, 'Asia/Shanghai')).resolves.toEqual({
      dashboardTimeZone: 'Asia/Shanghai',
      confirmedAt: '2026-09-04T02:00:00Z',
    })
    expect(request).toHaveBeenCalledWith('/meal-records/dashboard-time-zone-confirmations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ time_zone: 'Asia/Shanghai' }),
    })
  })

  it('只把严格 200 视为确认成功；不同统计时区的 409 必须成为可分类冲突', async () => {
    const differentZone = vi.fn().mockResolvedValue(new Response(null, { status: 409 }))
    await expect(confirmDashboardTimeZone(differentZone, 'America/Los_Angeles')).rejects.toBeInstanceOf(DashboardTimezoneConflictError)

    const invalid = vi.fn().mockResolvedValue(new Response(null, { status: 400 }))
    await expect(confirmDashboardTimeZone(invalid, 'Not/AZone')).rejects.toThrow('dashboard time zone confirmation failed')

    const malformed = vi.fn().mockResolvedValue(new Response(JSON.stringify({ dashboard_time_zone: 'Asia/Shanghai' }), { status: 200 }))
    await expect(confirmDashboardTimeZone(malformed, 'Asia/Shanghai')).rejects.toThrow()

    const networkFailure = vi.fn().mockRejectedValue(new Error('network unavailable'))
    await expect(confirmDashboardTimeZone(networkFailure, 'Asia/Shanghai')).rejects.toThrow('network unavailable')
  })
})

 it('编辑提交餐次、用餐时间和 IANA 时区，旧记录保持未分类', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(record), { status: 200 }))
    const saved = await updateMealRecord(request, record.id, { mealSlot: 'breakfast', consumedAt: record.consumed_at })
    expect(JSON.parse(String(request.mock.calls[0][1]?.body))).toEqual({ meal_slot: 'breakfast', consumed_at: record.consumed_at, time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone })
    expect(saved.meal_slot).toBeNull()
  })
