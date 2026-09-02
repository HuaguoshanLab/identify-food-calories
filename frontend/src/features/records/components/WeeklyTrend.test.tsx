import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { WeeklyTrend } from './WeeklyTrend'

const week = Array.from({ length: 7 }, (_, index) => ({
  consumed_local_date: `2026-08-${String(27 + index).padStart(2, '0')}`,
  totals: { energy_kcal: String((index + 1) * 100), protein_g: '0', fat_g: '0', carbohydrate_g: '0' },
  meal_count: index,
}))

describe('WeeklyTrend', () => {
  it('为固定七日 SVG 提供图像语义、键盘点与相同数据表', () => {
    render(<WeeklyTrend week={week} />)

    expect(screen.getByRole('img', { name: '近七日能量趋势' })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: '近七日能量数据表' })).toBeInTheDocument()
    const point = screen.getByRole('button', { name: /8月27日.*100 kcal/ })
    point.focus()
    fireEvent.keyDown(point, { key: 'ArrowRight' })
    expect(screen.getByRole('button', { name: /8月28日.*200 kcal/ })).toHaveFocus()
  })
})
