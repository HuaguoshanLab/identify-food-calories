import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { DashboardOverview } from '../api/dashboard'

function formatEnergy(value: string): string { const number = Number(value); return Number.isFinite(number) ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: Number.isInteger(number) ? 0 : 1 }).format(number) : value }
function macroState(value: string, range: { lower: string; upper: string }): string { const numeric = Number(value); return numeric < Number(range.lower) ? '偏低' : numeric > Number(range.upper) ? '偏高' : '适中' }

type SummaryOverview = { today: DashboardOverview['today']; target_eligibility?: DashboardOverview['target_eligibility'] }

export function TodaySummaryCard({ overview }: { overview: SummaryOverview }) {
  const { today, target_eligibility: eligibility } = overview
  const nutrients = [
    ['蛋白质', 'protein_g'], ['脂肪', 'fat_g'], ['碳水', 'carbohydrate_g'],
  ] as const
  return <Card className="gap-3 border-primary/15 bg-accent/60 py-5 shadow-none" aria-labelledby="today-summary-title">
    <CardHeader className="flex flex-row items-center justify-between gap-2">
      <CardTitle className="text-[13px] font-medium text-muted-foreground" id="today-summary-title">今日已记录摄入</CardTitle>
      <p className="text-xs tabular-nums text-muted-foreground">{today.meal_count} 餐</p>
    </CardHeader>
    <CardContent>
      <p className="mb-5 tabular-nums text-[44px] font-semibold leading-[52px] tracking-tight">{formatEnergy(today.totals.energy_kcal)} <span className="text-sm font-normal tracking-normal text-muted-foreground">kcal</span></p>
      <dl aria-label="已记录营养素" className="grid grid-cols-3 border-t border-primary/15 pt-4">
        {nutrients.map(([label, key], index) => {
          const state = eligibility?.eligible ? macroState(today.totals[key], eligibility.target[key]) : null
          return <div className={`min-w-0 ${index ? 'border-l border-primary/10 pl-3' : ''}`} key={key}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums">{formatEnergy(today.totals[key])}<span className="ml-1 text-xs font-normal text-muted-foreground">g</span></dd>
            {state ? <dd aria-label={`${label}目标状态：${state}`} className="mt-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground"><span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${state === '适中' ? 'bg-primary' : 'bg-warning'}`} />{state}</dd> : null}
          </div>
        })}
      </dl>
      {!eligibility?.eligible ? <p className="mt-3 text-xs leading-5 text-muted-foreground">尚未获得可用的营养目标</p> : null}
    </CardContent>
  </Card>
}
