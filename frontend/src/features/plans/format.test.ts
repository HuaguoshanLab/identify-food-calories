import { describe, expect, it } from 'vitest'

import { formatPlanRange, formatPlanValue, planMetricStateCopy } from './format'

describe('diet-plan presentation formatters', () => {
  it('uses whole-number Chinese grammar for target ranges and planned values', () => {
    expect(formatPlanRange('1800.0', '2000.0', 'kcal')).toBe('目标：1,800–2,000 kcal')
    expect(formatPlanValue('1920.4', 'kcal')).toBe('计划：1,920 kcal')
    expect(formatPlanRange('200.1', '250.9', 'g')).toBe('目标：200–251 g')
  })

  it('keeps range states textual rather than implying clinical precision through color', () => {
    expect(planMetricStateCopy('low')).toEqual({ label: '偏低', description: '计划值低于目标区间。' })
    expect(planMetricStateCopy('in_range')).toEqual({ label: '适中', description: '计划值在目标区间内。' })
    expect(planMetricStateCopy('high')).toEqual({ label: '偏高', description: '计划值高于目标区间。' })
  })
})
