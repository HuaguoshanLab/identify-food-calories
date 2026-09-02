import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TodaySummaryCard } from './TodaySummaryCard'

const eligibleOverview = {
  today: {
    consumed_local_date: '2026-09-02',
    totals: { energy_kcal: '612.000', protein_g: '31.5', fat_g: '18', carbohydrate_g: '72' },
    meal_count: 2,
  },
  week: [],
  target_eligibility: {
    eligible: true,
    target_version: 'target-v1',
    protein_g: { minimum: '25', maximum: '40' },
    fat_g: { minimum: '10', maximum: '25' },
    carbohydrate_g: { minimum: '60', maximum: '90' },
  },
} as const

describe('TodaySummaryCard', () => {
  it('在同一首屏卡片按既定层级展示 overview 的事实总量和餐数', () => {
    render(<TodaySummaryCard overview={eligibleOverview} />)

    expect(screen.getByText('今日已记录摄入')).toBeInTheDocument()
    expect(screen.getByText('612 kcal')).toHaveClass('tabular-nums')
    expect(screen.getByText('2 餐')).toHaveClass('tabular-nums')
    expect(screen.getByText('蛋白质')).toBeInTheDocument()
    expect(screen.queryByText('612.0 kcal')).not.toBeInTheDocument()
  })

  it.each([
    { ...eligibleOverview, target_eligibility: { eligible: false } },
    { ...eligibleOverview, target_eligibility: undefined },
  ])('资格缺失或为 false 时保留事实且不虚构目标', (overview) => {
    render(<TodaySummaryCard overview={overview} />)

    expect(screen.getByText('612 kcal')).toBeInTheDocument()
    expect(screen.getByText('2 餐')).toBeInTheDocument()
    expect(screen.queryByText('蛋白质')).not.toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    expect(screen.getByText('尚未获得可用的营养目标')).toBeInTheDocument()
  })
})
