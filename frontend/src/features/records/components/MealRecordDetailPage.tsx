import { mealSlotLabels } from '../api/mealMetadata'
import { ChevronDown, Pencil } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { getMealRecord, type MealRecord } from '../api/client'
import { formatNutrition } from '../format'

const mealDate = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })

export function MealRecordDetailPage() {
  const { recordId = '' } = useParams()
  const { request } = useAuth()
  const [record, setRecord] = useState<MealRecord>()
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void getMealRecord(request, recordId).then((value) => { if (active) setRecord(value) }).catch(() => { if (active) setError('这条记录不存在或无法访问。') })
    return () => { active = false }
  }, [recordId, request])
  if (error) return <Alert variant="destructive"><AlertTitle>无法查看记录</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>
  if (!record) return <p className="text-sm text-muted-foreground">正在加载记录…</p>
  return <section className="space-y-5">
    <div className="rounded-xl border border-primary/15 bg-accent/40 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0"><p className="font-semibold">{record.meal_slot ? mealSlotLabels[record.meal_slot] : '未分类'}</p><p className="mt-1 text-xs text-muted-foreground">{mealDate.format(new Date(record.consumed_at))}</p></div>
        <Link aria-label="编辑餐食记录" className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-primary hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring" to={`/app/records/${record.id}/edit`}><Pencil aria-hidden="true" className="size-4" />编辑</Link>
      </div>
      <div className="py-6"><p className="mb-1 text-xs text-muted-foreground">本餐热量</p><p className="tabular-nums"><span className="text-4xl font-semibold tracking-tight">{formatNutrition(record.energy_kcal)}</span><span className="ml-2 text-sm text-muted-foreground">kcal</span></p></div>
      <dl className="grid grid-cols-3 gap-2 border-t border-primary/15 pt-4">
        {[['蛋白质', record.protein_g], ['脂肪', record.fat_g], ['碳水', record.carbohydrate_g]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-base font-semibold tabular-nums">{formatNutrition(value)}<span className="ml-1 text-xs font-normal text-muted-foreground">g</span></dd></div>)}
      </dl>
    </div>
    <section aria-label="食物明细" className="space-y-3">
      <div className="flex items-center justify-between"><h2 className="text-base font-semibold">食物明细</h2><span className="text-xs text-muted-foreground">{record.items.length} 项</span></div>
      <div className="divide-y divide-border rounded-xl border border-border bg-card px-4">
        {record.items.map((item) => <div className="py-4" key={item.id}>
          <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="break-words text-sm font-semibold">{item.display_name}</h3><p className="mt-1 text-xs tabular-nums text-muted-foreground">{formatNutrition(item.grams)} g</p></div><p className="shrink-0 text-sm font-semibold tabular-nums">{formatNutrition(item.energy_kcal)} <span className="text-xs font-normal text-muted-foreground">kcal</span></p></div>
          <p className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs tabular-nums text-muted-foreground"><span>蛋白质 {formatNutrition(item.protein_g)}g</span><span>脂肪 {formatNutrition(item.fat_g)}g</span><span>碳水 {formatNutrition(item.carbohydrate_g)}g</span></p>
        </div>)}
        {!record.items.length ? <p className="py-4 text-sm text-muted-foreground">暂无食物明细</p> : null}
      </div>
    </section>
    <details className="group text-xs text-muted-foreground">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between rounded-lg focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">记录信息<ChevronDown aria-hidden="true" className="size-4 transition-transform group-open:rotate-180" /></summary>
      <dl className="space-y-3 break-words rounded-lg bg-muted/50 p-3"><div><dt>目录版本</dt><dd className="mt-1">{record.nutrition_catalog_version}</dd></div><div><dt>计算版本</dt><dd className="mt-1">{record.calculation_version}</dd></div><div><dt>更新时间</dt><dd className="mt-1">{new Date(record.updated_at).toLocaleString('zh-CN')}</dd></div></dl>
    </details>
  </section>
}
