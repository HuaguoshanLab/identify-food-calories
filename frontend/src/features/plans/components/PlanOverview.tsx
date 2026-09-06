import { CircleCheck, CircleMinus, CirclePlus } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatPlanRange, formatPlanValue, planMetricStateCopy, type PlanMetricState } from '../format'
import type { PlanReport } from './PlanPage'

const metricDefinitions = [
  ['energy_kcal', '能量', 'kcal'],
  ['carbohydrate_g', '碳水', 'g'],
  ['protein_g', '蛋白质', 'g'],
  ['fat_g', '脂肪', 'g'],
] as const

function metricState(value: number, lower: string, upper: string): PlanMetricState {
  if (value < Number(lower)) return 'low'
  if (value > Number(upper)) return 'high'
  return 'in_range'
}

function metricIcon(state: PlanMetricState) {
  if (state === 'low') return CircleMinus
  if (state === 'high') return CirclePlus
  return CircleCheck
}

export function PlanOverview({ report }: { report: PlanReport }) {
  const totals = Object.fromEntries(metricDefinitions.map(([field]) => [
    field,
    report.meals.reduce((sum, meal) => sum + Number(meal.nutrients[field]), 0),
  ])) as Record<(typeof metricDefinitions)[number][0], number>

  return (
    <section aria-labelledby="plan-overview-title" className="space-y-3">
      <h2 className="text-base font-semibold leading-6" id="plan-overview-title">每日目标概览</h2>
      <Card>
        <CardHeader><CardTitle>目标范围与计划值</CardTitle></CardHeader>
        <CardContent className="grid gap-3">
          {metricDefinitions.map(([field, label, unit]) => {
            const range = report.target[field]
            const value = String(totals[field])
            const state = metricState(totals[field], range.lower, range.upper)
            const copy = planMetricStateCopy(state)
            const Icon = metricIcon(state)
            return <div className="space-y-1 rounded-md bg-muted/60 p-3" key={field}>
              <p className="text-sm font-semibold">{label}</p>
              <p className="mt-1 flex items-start gap-2 tabular-nums text-sm text-muted-foreground"><Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" /><span>{formatPlanRange(range.lower, range.upper, unit)} · {formatPlanValue(value, unit)} · {copy.label}</span></p>
              <p className="mt-1 text-[13px] leading-5 text-muted-foreground">{copy.description}</p>
            </div>
          })}
        </CardContent>
      </Card>
    </section>
  )
}
