import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { weeklyReviewResponseSchema } from '../api/weeklyReview'
import { WeeklyReview } from './WeeklyReview'

const base = {
  week_start: '2026-08-31', week_end: '2026-09-06', coverage_days: 2, meal_count: 4,
  totals: { energy_kcal: '900', protein_g: '42', fat_g: '30', carbohydrate_g: '100' },
} as const

describe('WeeklyReview', () => {
  it('覆盖不足时只展示事实汇总，不显示建议或重新生成', () => {
    render(<WeeklyReview review={{ ...base, status: 'insufficient_coverage', suggestions: [] }} onRefresh={vi.fn()} isRefreshing={false} />)

    expect(screen.getByRole('heading', { name: '周复盘' })).toBeInTheDocument()
    expect(screen.getByText('已记录 2 天 · 4 餐')).toBeInTheDocument()
    expect(screen.getByText(/记录仍不足以生成建议/)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: '一般饮食参考' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重新生成' })).not.toBeInTheDocument()
  })

  it('安全弃权不显示建议或技术代码', () => {
    render(<WeeklyReview review={{ ...base, status: 'safety_abstain', suggestions: [] }} onRefresh={vi.fn()} isRefreshing={false} />)

    expect(screen.getByText(/暂不提供本周建议/)).toBeInTheDocument()
    expect(screen.queryByText(/PROVIDER_|WEEKLY_REVIEW_|prompt|facts/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: '一般饮食参考' })).not.toBeInTheDocument()
  })

  it('成功时展示最多三条一般饮食参考和固定免责声明', () => {
    render(<WeeklyReview review={{ ...base, status: 'success', suggestions: ['记录中可尝试增加不同食物种类。', '让三餐时间更规律。'] }} onRefresh={vi.fn()} isRefreshing={false} />)

    expect(screen.getByRole('list', { name: '一般饮食参考' })).toHaveTextContent('记录中可尝试增加不同食物种类。')
    expect(screen.getByText('仅基于已记录数据，供一般饮食参考，不构成医疗建议。')).toBeInTheDocument()
  })

  it('仅可重试服务失败提供重新生成操作', () => {
    const onRefresh = vi.fn()
    render(<WeeklyReview review={{ ...base, status: 'retryable_error', suggestions: [] }} onRefresh={onRefresh} isRefreshing={false} />)

    fireEvent.click(screen.getByRole('button', { name: '重新生成' }))
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('严格 DTO 拒绝额外字段和技术错误字段', () => {
    expect(weeklyReviewResponseSchema.safeParse({ ...base, status: 'safety_abstain', suggestions: [], provider_error: 'secret' }).success).toBe(false)
    expect(weeklyReviewResponseSchema.safeParse({ ...base, status: 'success', suggestions: ['一', '二', '三', '四'] }).success).toBe(false)
  })
})
