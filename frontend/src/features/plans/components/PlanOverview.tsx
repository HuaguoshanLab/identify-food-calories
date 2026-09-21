import { Card, CardContent } from '@/components/ui/card'
import { formatPlanNumber, formatTargetGap } from '../format'
import type { PlanReport } from './PlanPage'

const macros = [
  { field: 'protein_g', label: '蛋白质', factor: 4, color: 'var(--macro-protein)' },
  { field: 'fat_g', label: '脂肪', factor: 9, color: 'var(--macro-fat)' },
  { field: 'carbohydrate_g', label: '碳水', factor: 4, color: 'var(--macro-carbs)' },
] as const
const metrics = [['energy_kcal', '能量'], ['protein_g', '蛋白质'], ['fat_g', '脂肪'], ['carbohydrate_g', '碳水']] as const

export function PlanOverview({ report }: { report: PlanReport }) {
  const totals = Object.fromEntries(metrics.map(([field]) => [field, report.meals.reduce((sum, meal) => sum + Number(meal.nutrients[field]), 0)])) as Record<(typeof metrics)[number][0], number>
  const allInRange = metrics.every(([field]) => formatTargetGap(totals[field], report.target[field].lower, report.target[field].upper, '').inRange)
  const energy = formatPlanNumber(String(totals.energy_kcal))
  const range = report.target.energy_kcal
  // 环形面积仅表示三大营养素的估算供能比例；中心热量始终使用后端餐单能量合计。
  const macroEnergy = macros.reduce((sum, macro) => sum + totals[macro.field] * macro.factor, 0)
  const shares = macros.map((macro) => ({ ...macro, share: macroEnergy > 0 ? totals[macro.field] * macro.factor / macroEnergy * 100 : 0 }))
  const segments = shares.map((macro, index) => ({
    ...macro,
    offset: shares.slice(0, index).reduce((sum, previous) => sum + previous.share, 0),
  }))

  return <section aria-labelledby="plan-overview-title" className="space-y-3">
    <h2 className="text-base font-semibold leading-6" id="plan-overview-title">每日目标概览</h2>
    <Card>
      <CardContent className="space-y-5">
        <p className={allInRange ? 'text-sm text-primary' : 'text-sm text-destructive'}>
          {allInRange ? '全部指标在目标范围内' : '部分指标未达到原目标，请查看差距'}
        </p>
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 tabular-nums">
          <p><span className="text-4xl font-bold tracking-tight">{energy}</span><span className="ml-1 text-base font-semibold text-muted-foreground">kcal</span></p>
          <p className="text-[13px] text-muted-foreground">（目标 {formatPlanNumber(range.lower)}–{formatPlanNumber(range.upper)} kcal）</p>
        </div>
        <div className="relative mx-auto size-48" role="img" aria-label={`计划总热量 ${energy} kcal；营养素估算供能占比：${segments.map((s) => `${s.label} ${s.share.toFixed(1)}%`).join('，')}`}>
          <svg aria-hidden="true" viewBox="0 0 200 200" className="size-full -rotate-90">
            <circle cx="100" cy="100" r="78" fill="none" stroke="var(--muted)" strokeWidth="28" />
            {segments.filter((s) => s.share > 0).map((s) => <circle key={s.field} cx="100" cy="100" r="78" fill="none" stroke={s.color} strokeWidth="28" pathLength="100" strokeDasharray={`${Math.max(0, s.share - Math.min(0.8, s.share / 2))} 100`} strokeDashoffset={-s.offset} />)}
          </svg>
          <div aria-hidden="true" className="absolute inset-0 flex flex-col items-center justify-center gap-1"><span className="text-sm font-medium text-muted-foreground">总热量</span><span className="text-2xl font-bold tabular-nums">{energy}</span><span className="text-sm text-muted-foreground">kcal</span></div>
        </div>
        <dl className="grid grid-cols-3 gap-2 text-center">{macros.map((macro) => {
          const target = report.target[macro.field]
          return <div key={macro.field}><dt className="flex items-center justify-center gap-1.5 text-sm font-semibold"><span aria-hidden="true" className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: macro.color }} />{macro.label}</dt><dd className="mt-1 text-sm font-semibold tabular-nums text-muted-foreground">{totals[macro.field].toFixed(1)}g</dd><dd className="mt-0.5 text-[12px] tabular-nums text-muted-foreground">（{formatPlanNumber(target.lower)}–{formatPlanNumber(target.upper)}g）</dd></div>
        })}</dl>
        <div className="space-y-2" aria-label="营养目标对照">
          <h3 className="text-sm font-semibold">目标与实际差距</h3>
          {metrics.map(([field, label]) => {
            const bounds = report.target[field]
            const unit = field === 'energy_kcal' ? 'kcal' : 'g'
            const gap = formatTargetGap(totals[field], bounds.lower, bounds.upper, unit)
            return <div key={field} className="border-t border-border pt-2 text-sm">
              <div className="flex flex-wrap justify-between gap-x-2 gap-y-1"><span className="font-medium">{label}</span><span className={gap.inRange ? 'text-primary' : 'text-destructive'}>{gap.label}</span></div>
              <p className="mt-1 text-xs tabular-nums text-muted-foreground">目标 {formatPlanNumber(bounds.lower)}–{formatPlanNumber(bounds.upper)} {unit} · 实际 {Number(totals[field].toFixed(1))} {unit}</p>
            </div>
          })}
        </div>
      </CardContent>
    </Card>
  </section>
}
