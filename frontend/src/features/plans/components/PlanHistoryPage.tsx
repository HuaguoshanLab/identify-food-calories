import { useInfiniteQuery } from '@tanstack/react-query'
import { CalendarDays, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { routePaths } from '@/routePaths'
import { getPlanHistory, planArchiveKeys } from '../api/archive'

export function PlanHistoryPage() {
  const { request } = useAuth()
  const history = useInfiniteQuery({ queryKey: planArchiveKeys.history, queryFn: ({ pageParam }) => getPlanHistory(request, pageParam), initialPageParam: null as string | null, getNextPageParam: (page) => page.next_before ?? undefined })
  return <section className="space-y-4">
    <h2 className="text-base font-semibold leading-6">按日期查看</h2>
    {history.isPending ? <p role="status">正在读取历史计划…</p> : null}
    {history.isError ? <Alert variant="destructive"><AlertTitle>无法读取历史计划</AlertTitle><Button className="h-11" variant="outline" onClick={() => void history.refetch()}>重试</Button></Alert> : null}
    {history.data?.pages[0]?.items.length === 0 ? <p>还没有保存的计划。生成成功后会自动出现在这里。</p> : null}
    <div className="space-y-3">{history.data?.pages.flatMap((page) => page.items).map((plan) => <Link className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50" key={plan.id} to={`${routePaths.planDetail}?id=${plan.id}`}><span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted text-primary"><CalendarDays aria-hidden="true" className="size-5" /></span><div className="min-w-0 flex-1"><p className="font-semibold tabular-nums">{plan.plan_date} 三餐计划</p><p className="mt-1 break-words text-[13px] leading-5 text-muted-foreground">第 {plan.current_version} 版</p></div><ChevronRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" /></Link>)}</div>
    {history.hasNextPage ? <Button className="h-11 w-full" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()} variant="outline">加载更早计划</Button> : null}
  </section>
}
