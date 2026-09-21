import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { PlanReport } from '../api/report'
import { formatTargetGap } from '../format'
import { PlanOverview } from './PlanOverview'

function report(): PlanReport {
  return {
    stage: 'complete', relaxation: undefined, adjustment: undefined, disclaimer: '普通饮食参考，不替代医疗建议。',
    target: { energy_kcal: { lower: '1800', upper: '2000' }, protein_g: { lower: '60', upper: '90' }, fat_g: { lower: '40', upper: '70' }, carbohydrate_g: { lower: '210', upper: '280' } },
    meals: (['breakfast', 'lunch', 'dinner'] as const).map((slot) => ({
      slot, display_name: '受控餐', portion_description: '按目标调整份量（原份量 200g）', portion_grams: '250',
      method_tags: ['蒸'], flavour_tags: ['清淡'], matched_preference_summaries: [], matched_exclusion_summaries: [],
      nutrients: { energy_kcal: '600', protein_g: '25', fat_g: '20', carbohydrate_g: '80' },
    })),
  }
}

describe('PlanOverview target comparison', () => {
  it('shows original targets, actual totals and in-range state', () => {
    render(<PlanOverview report={report()} />)
    expect(screen.getByText('全部指标在目标范围内')).toBeInTheDocument()
    const comparison = screen.getByLabelText('营养目标对照')
    expect(within(comparison).getByRole('row', { name: /能量/ })).toHaveTextContent('1,8001,800–2,000范围内')
    expect(within(comparison).getAllByText('范围内')).toHaveLength(4)
  })

  it('shows every deviation, including old saved plans without a relaxation marker', () => {
    const value = report()
    value.meals[0].nutrients = { energy_kcal: '500', protein_g: '50', fat_g: '20', carbohydrate_g: '40' }
    render(<PlanOverview report={value} />)
    expect(screen.getByText('部分指标未达到原目标，请查看差距')).toBeInTheDocument()
    expect(screen.getByText('低于下限 100 kcal')).toBeInTheDocument()
    expect(screen.getByText('高于上限 10 g')).toBeInTheDocument()
    expect(screen.getByText('低于下限 10 g')).toBeInTheDocument()
    expect(screen.queryByText('全部指标在目标范围内')).not.toBeInTheDocument()
  })

  it('does not label a genuine small gap as zero or floating-point noise as a gap', () => {
    expect(formatTargetGap(0.1 + 0.2, '0.3', '0.3', 'g').inRange).toBe(true)
    expect(formatTargetGap(59.99, '60', '90', 'g').label).toBe('低于下限 不足 0.1 g')
  })
})
