export type PlanMetricState = 'low' | 'in_range' | 'high'

const wholeNumber = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 })

/** Safe planning DTOs are decimal strings; presentation rounds only after the backend has validated them. */
export function formatPlanNumber(value: string): string {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? wholeNumber.format(numeric) : value
}

export function formatPlanRange(lower: string, upper: string, unit: string): string {
  return `目标：${formatPlanNumber(lower)}–${formatPlanNumber(upper)} ${unit}`
}

export function formatPlanValue(value: string, unit: string): string {
  return `计划：${formatPlanNumber(value)} ${unit}`
}

export function planMetricStateCopy(state: PlanMetricState) {
  return {
    low: { label: '偏低', description: '计划值低于目标区间。' },
    in_range: { label: '适中', description: '计划值在目标区间内。' },
    high: { label: '偏高', description: '计划值高于目标区间。' },
  }[state]
}
