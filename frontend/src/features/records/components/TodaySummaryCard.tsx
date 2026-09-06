import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { DashboardOverview } from '../api/dashboard'

function formatEnergy(value: string): string { const number = Number(value); return Number.isFinite(number) ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: Number.isInteger(number) ? 0 : 1 }).format(number) : value }
function macroState(value: string, range: { lower: string; upper: string }): string { const numeric = Number(value); return numeric < Number(range.lower) ? '偏低' : numeric > Number(range.upper) ? '偏高' : '适中' }

type SummaryOverview = { today: DashboardOverview['today']; target_eligibility?: DashboardOverview['target_eligibility'] }

export function TodaySummaryCard({ overview }: { overview: SummaryOverview }) {
  const { today, target_eligibility: eligibility } = overview
  const macros = eligibility?.eligible ? [['蛋白质', today.totals.protein_g, eligibility.target.protein_g], ['脂肪', today.totals.fat_g, eligibility.target.fat_g], ['碳水', today.totals.carbohydrate_g, eligibility.target.carbohydrate_g]] as const : null
  return <Card className="gap-2" aria-labelledby="today-summary-title"><CardHeader><CardTitle className="text-[13px] font-medium text-muted-foreground" id="today-summary-title">今日已记录摄入</CardTitle></CardHeader><CardContent className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-2"><p className="tabular-nums text-[36px] font-bold leading-[44px]">{formatEnergy(today.totals.energy_kcal)} <span className="text-[15px] font-medium text-muted-foreground">kcal</span></p><p className="tabular-nums text-sm text-muted-foreground">{today.meal_count} 餐</p></div>{macros ? <ul aria-label="宏量营养素相对目标状态" className="grid grid-cols-3 gap-2 text-center text-sm">{macros.map(([label, value, range]) => <li className="rounded-md bg-muted px-2 py-2" key={label}><span className="block text-muted-foreground">{label}</span><strong className="tabular-nums">{macroState(value, range)}</strong></li>)}</ul> : <p className="rounded-md bg-muted px-3 py-2 text-[13px] leading-5 text-muted-foreground">尚未获得可用的营养目标</p>}</CardContent></Card>
}
