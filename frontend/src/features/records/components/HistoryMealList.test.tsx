import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { HistoryMealList } from './HistoryMealList'

const page = {
  groups: [{
    consumed_local_date: '2026-09-01',
    totals: { energy_kcal: '500', protein_g: '20', fat_g: '10', carbohydrate_g: '65' },
    meal_count: 1,
    items: [{ id: '2f08b92e-4a88-4af3-ae0f-cc9f9251f201', consumed_at: '2026-09-01T12:00:00Z', totals: { energy_kcal: '500', protein_g: '20', fat_g: '10', carbohydrate_g: '65' } }],
  }],
  next_cursor: 'opaque-next-cursor',
} as const

describe('HistoryMealList', () => {
  it('按服务端 local-date 分组并只将 opaque cursor 交给加载更多回调', () => {
    const loadMore = vi.fn()
    render(<HistoryMealList isLoadingMore={false} onLoadMore={loadMore} page={page} />)

    expect(screen.getByRole('heading', { name: '历史记录' })).toBeInTheDocument()
    expect(screen.getByText('2026年9月1日')).toBeInTheDocument()
    screen.getByRole('button', { name: '加载更多记录' }).click()
    expect(loadMore).toHaveBeenCalledWith('opaque-next-cursor')
  })

  it('没有历史时呈现真实空态', () => {
    render(<HistoryMealList isLoadingMore={false} onLoadMore={vi.fn()} page={{ groups: [], next_cursor: null }} />)
    expect(screen.getByText('还没有已保存的餐食')).toBeInTheDocument()
  })
})
