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

/** Compare against the nearest original range edge; this is display, not plan validation. */
export function formatTargetGap(actual: number, lower: string, upper: string, unit: string) {
  const low = Number(lower)
  const high = Number(upper)
  const epsilon = Number.EPSILON * Math.max(1, Math.abs(actual), Math.abs(low), Math.abs(high)) * 8
  if (actual >= low - epsilon && actual <= high + epsilon) return { inRange: true, label: '在目标范围内' }
  const below = actual < low
  const difference = Math.abs(actual - (below ? low : high))
  const amount = difference < 0.1 ? '不足 0.1' : String(Number(difference.toFixed(1)))
  return { inRange: false, label: `${below ? '低于下限' : '高于上限'} ${amount} ${unit}` }
}
