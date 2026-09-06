import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { routePaths } from '@/routePaths'
import { deleteSavedPlan, getSavedPlan, planArchiveKeys } from '../api/archive'
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
    <h2 className="text-base font-semibold leading-6">保存的计划</h2>
    {detail.isPending ? <p role="status">正在读取计划…</p> : null}
    {detail.isError ? <Alert variant="destructive"><AlertTitle>计划不存在、已删除或暂时无法读取</AlertTitle><Button className="h-11" onClick={() => void detail.refetch()} variant="outline">重试</Button></Alert> : null}
    {plan ? <>
      <p className="rounded-xl border border-border bg-card p-4 font-semibold tabular-nums shadow-sm">{plan.plan_date} · 第 {plan.version} / {plan.current_version} 版</p>
      <p className="text-sm text-muted-foreground">已保存 · {plan.time_zone} · 历史版本仅供查看</p>
      <div className="flex gap-2"><Button className="h-11 flex-1" disabled={plan.version <= 1} onClick={() => setParams({ id, version: String(plan.version - 1) })} variant="outline">上一版</Button><Button className="h-11 flex-1" disabled={plan.version >= plan.current_version} onClick={() => setParams({ id, version: String(plan.version + 1) })} variant="outline">下一版</Button></div>
      <PlanOverview report={plan.report} />
      {relaxation ? <Alert><AlertTitle>此版本已放宽部分营养目标</AlertTitle><p>{relaxation.reason}</p></Alert> : null}
      <section aria-label="保存的三餐" className="space-y-3"><h2 className="text-base font-semibold leading-6">三餐内容</h2>{plan.report.meals.map((meal) => <MealCard key={meal.slot} meal={meal} />)}</section>
      <p className="text-sm text-muted-foreground">{plan.report.disclaimer} 计划不计入实际摄入。</p>
      <Button className="h-11 w-full" onClick={() => setConfirming(true)} variant="destructive">删除这天的计划</Button>
      <AlertDialog open={confirming} onOpenChange={setConfirming}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>删除整份计划？</AlertDialogTitle><AlertDialogDescription>将删除 {plan.plan_date} 的全部餐单版本，无法恢复。已确认的实际餐食记录不受影响。</AlertDialogDescription></AlertDialogHeader>{deletion.isError ? <p role="alert">删除失败，请重试。</p> : null}<AlertDialogFooter><AlertDialogCancel disabled={deletion.isPending}>取消</AlertDialogCancel><Button className="h-11" disabled={deletion.isPending} onClick={() => deletion.mutate()} variant="destructive">{deletion.isPending ? '正在删除…' : '确认删除'}</Button></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </> : null}
    <Link className="flex min-h-11 items-center underline" to={routePaths.planHistory}>返回历史计划</Link>
  </section>
}
