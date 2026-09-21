import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, ChartNoAxesCombined, Trash2 } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { routePaths } from '@/routePaths'
import { deleteSavedPlan, getSavedPlan, planArchiveKeys } from '../api/archive'
import { formatPlanNumber } from '../format'
import { MealCard } from './MealCard'
import { PlanOverview } from './PlanOverview'

export function SavedPlanPage() {
  const [params, setParams] = useSearchParams()
  const id = params.get('id') ?? ''
  const version = params.get('version')
  const { request } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const detail = useQuery({ queryKey: planArchiveKeys.detail(id, version), queryFn: () => getSavedPlan(request, id, version) })
  const deletion = useMutation({ mutationFn: () => deleteSavedPlan(request, id), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: planArchiveKeys.all }); navigate(routePaths.planHistory, { replace: true }) } })
  const plan = detail.data
  const relaxation = plan?.report.adjustment?.relaxation ?? plan?.report.relaxation
  return <section className="space-y-4">
    {detail.isPending ? <p role="status">正在读取计划…</p> : null}
    {detail.isError ? <Alert variant="destructive"><AlertTitle>计划不存在、已删除或暂时无法读取</AlertTitle><Button className="h-11" onClick={() => void detail.refetch()} variant="outline">重试</Button></Alert> : null}
    {plan ? <>
      <header className="overflow-hidden rounded-2xl border border-primary/15 bg-accent/50">
        <div className="flex items-start gap-3 p-4">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-card/80 text-primary"><CalendarDays aria-hidden="true" className="size-5" /></span>
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-semibold tabular-nums leading-7"><time dateTime={plan.plan_date}>{plan.plan_date}</time></h2>
            <p className="mt-1 text-sm text-muted-foreground">三餐计划 · {formatPlanNumber(plan.totals.energy_kcal)} kcal</p>
          </div>
          <span className="shrink-0 rounded-full bg-card/80 px-2.5 py-1 text-xs font-medium text-primary">{plan.version === plan.current_version ? '最新版' : '历史版'}</span>
        </div>
        <nav aria-label="餐单版本" className="flex min-h-14 items-center justify-between gap-2 border-t border-primary/10 px-3 py-1">
          {plan.current_version > 1 ? <Button aria-label="上一版" className="h-11 gap-1 px-2 text-sm" disabled={plan.version <= 1} onClick={() => setParams({ id, version: String(plan.version - 1) })} variant="ghost"><ChevronLeft aria-hidden="true" className="size-4" />上一版</Button> : null}
          <p aria-live="polite" className="flex-1 text-center text-sm tabular-nums text-muted-foreground">第 {plan.version} / {plan.current_version} 版</p>
          {plan.current_version > 1 ? <Button aria-label="下一版" className="h-11 gap-1 px-2 text-sm" disabled={plan.version >= plan.current_version} onClick={() => setParams({ id, version: String(plan.version + 1) })} variant="ghost">下一版<ChevronRight aria-hidden="true" className="size-4" /></Button> : null}
        </nav>
      </header>
      {relaxation ? <Alert><AlertTitle>此版本已放宽部分营养目标</AlertTitle><p>{relaxation.reason}</p></Alert> : null}
      <section aria-label="保存的三餐" className="space-y-3"><h2 className="sr-only">三餐内容</h2>{plan.report.meals.map((meal) => <MealCard key={meal.slot} meal={meal} />)}</section>
      <details className="group rounded-2xl border border-border/60 bg-card">
        <summary className="flex min-h-14 cursor-pointer list-none items-center gap-2 px-4 py-3 font-medium [&::-webkit-details-marker]:hidden"><ChartNoAxesCombined aria-hidden="true" className="size-5 text-primary" /><span className="flex-1">营养与目标</span><ChevronDown aria-hidden="true" className="size-4 text-muted-foreground transition-transform group-open:rotate-180" /></summary>
        <div className="border-t border-border/60 p-3"><PlanOverview report={plan.report} /></div>
      </details>
      <footer className="space-y-3 pt-2">
        <p className="text-center text-xs leading-5 text-muted-foreground">{plan.report.disclaimer}<br />计划不计入实际摄入。</p>
        <div className="flex justify-center border-t border-border/60 pt-2"><Button className="h-11 gap-2 text-sm text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => setConfirming(true)} variant="ghost"><Trash2 aria-hidden="true" className="size-4" />删除这天的计划</Button></div>
      </footer>
      <AlertDialog open={confirming} onOpenChange={setConfirming}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>删除整份计划？</AlertDialogTitle><AlertDialogDescription>将删除 {plan.plan_date} 的全部餐单版本，无法恢复。已确认的实际餐食记录不受影响。</AlertDialogDescription></AlertDialogHeader>{deletion.isError ? <p role="alert">删除失败，请重试。</p> : null}<AlertDialogFooter><AlertDialogCancel disabled={deletion.isPending}>取消</AlertDialogCancel><Button className="h-11" disabled={deletion.isPending} onClick={() => deletion.mutate()} variant="destructive">{deletion.isPending ? '正在删除…' : '确认删除'}</Button></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </> : null}
  </section>
}
