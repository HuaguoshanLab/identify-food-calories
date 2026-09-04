import { describe, expect, it, vi } from 'vitest'

import { getDashboardHistory } from './dashboard'

describe('getDashboardHistory', () => {
  it('接受 FastAPI history 的 RFC 3339 时间戳和省略的末页 cursor', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      groups: [{
        consumed_local_date: '2026-09-04', meal_count: 1,
        totals: { energy_kcal: '130.000000', protein_g: '2.600000', fat_g: '0.300000', carbohydrate_g: '25.900000' },
        items: [{
          id: 'f2d9dbfc-2149-4d0e-bb36-b9d0cdb750f2', consumed_at: '2026-09-04T02:00:00Z',
          totals: { energy_kcal: '130.000000', protein_g: '2.600000', fat_g: '0.300000', carbohydrate_g: '25.900000' },
        }],
      }],
    }), { status: 200 }))

    const page = await getDashboardHistory(request, null)

    expect(request).toHaveBeenCalledWith('/dashboard/history')
    expect(page.groups[0]?.items[0]?.consumed_at).toBe('2026-09-04T02:00:00Z')
    expect(page.next_cursor).toBeNull()
  })
})
