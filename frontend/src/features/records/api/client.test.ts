import { describe, expect, it, vi } from 'vitest'

import { confirmMealRecord } from './client'

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
    id: '3f8ba163-ddf2-4b58-b5b4-455937c19f7d', position: 0, display_name: '白米饭', grams: '100.0',
    energy_kcal: '130.0', protein_g: '2.6', fat_g: '0.3', carbohydrate_g: '25.9', is_estimated: false,
  }],
}

describe('confirmMealRecord', () => {
  it('提交浏览器 IANA 时区，并严格解析服务器返回的本地日期归属', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(record), { status: 201 }))

    const saved = await confirmMealRecord(request, 'c4683f51-5b02-49a2-898c-d9e30b0f1c72', 'save-7c879dfe-73c2-48d5-ae91-9c0d4eb55bea')

    expect(JSON.parse(String(request.mock.calls[0][1]?.body))).toEqual({
      thread_id: 'c4683f51-5b02-49a2-898c-d9e30b0f1c72',
      command_key: 'save-7c879dfe-73c2-48d5-ae91-9c0d4eb55bea',
      time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
    expect(saved.consumed_local_date).toBe('2026-09-04')
  })
})
