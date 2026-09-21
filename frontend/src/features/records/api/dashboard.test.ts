import { describe, expect, it, vi } from 'vitest'

import { dashboardQueryKeys, getDashboardHistory, getDashboardOverview } from './dashboard'
import { getCompletedWeeklyReview, getWeeklyReview, weeklyReviewQueryKeys } from './weeklyReview'

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

describe('dashboard requests and cache keys', () => {
  it('current overview/default review 是服务端范围，cache key 不含浏览器日期或时区', async () => {
    const request = vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(path.startsWith('/dashboard/overview') ? {
      today: { consumed_local_date: '2026-09-07', totals: { energy_kcal: '0', protein_g: '0', fat_g: '0', carbohydrate_g: '0' }, meal_count: 0 },
      week: Array.from({ length: 7 }, (_, index) => ({
        consumed_local_date: `2026-09-${String(index + 7).padStart(2, '0')}`,
        totals: { energy_kcal: '0', protein_g: '0', fat_g: '0', carbohydrate_g: '0' }, meal_count: 0,
      })),
    } : {
      status: 'insufficient_coverage', week_start: '2026-09-07', week_end: '2026-09-13',
      coverage_days: 0, meal_count: 0,
      totals: { energy_kcal: '0', protein_g: '0', fat_g: '0', carbohydrate_g: '0' }, suggestions: [],
    }), { status: 200 })))

    await getDashboardOverview(request)
    await getWeeklyReview(request)

    expect(request).toHaveBeenCalledWith('/dashboard/overview')
    expect(request).toHaveBeenCalledWith('/dashboard/weekly-review')
    expect(dashboardQueryKeys.overview()).toEqual(['dashboard', 'overview', 'current'])
    expect(dashboardQueryKeys.history(null)).toEqual(['dashboard', 'history', null])
    expect(weeklyReviewQueryKeys.current()).toEqual(['dashboard', 'weekly-review', 'current'])
    expect(request.mock.calls.flatMap(([path]) => String(path).match(/(?:week_start|time_zone)/g) ?? [])).toEqual([])
  })

  it('已结束周只能通过独立 typed history 调用，不会改写 current request', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: 'insufficient_coverage', week_start: '2026-09-07', week_end: '2026-09-13',
      coverage_days: 0, meal_count: 0,
      totals: { energy_kcal: '0', protein_g: '0', fat_g: '0', carbohydrate_g: '0' }, suggestions: [],
    }), { status: 200 }))

    await getCompletedWeeklyReview(request, '2026-08-31')

    expect(request).toHaveBeenCalledWith('/dashboard/weekly-review?week_start=2026-08-31')
    expect(weeklyReviewQueryKeys.completed('2026-08-31')).toEqual(['dashboard', 'weekly-review', 'completed', '2026-08-31'])
  })
})


describe('dashboard target contract', () => {
  it('保留后端带策略和公式版本的有效营养目标', async () => {
    const day = { consumed_local_date: '2026-09-21', totals: { energy_kcal: '1082', protein_g: '125.6', fat_g: '46', carbohydrate_g: '43.6' }, meal_count: 3 }
    const eligibility = { eligible: true, target_version: 'target-policy.v1', target: {
      energy_kcal: { lower: '1339', upper: '1539' }, protein_g: { lower: '33', upper: '135' },
      fat_g: { lower: '30', upper: '60' }, carbohydrate_g: { lower: '151', upper: '250' },
      policy_version: 'target-policy.v1', formula_version: 'mifflin-st-jeor.v1',
    } }
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({ today: day, week: Array(7).fill(day), target_eligibility: eligibility })))
    const result = await getDashboardOverview(request)
    expect(result.target_eligibility).toEqual(eligibility)
  })
})
