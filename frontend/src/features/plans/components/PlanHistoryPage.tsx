import { useInfiniteQuery } from '@tanstack/react-query'
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
    <h2 className="text-xl font-semibold">按日期查看</h2>
    <p className="text-sm text-muted-foreground">按计划日期保存。餐单是饮食参考，不代表已经摄入。</p>
    {history.isPending ? <p role="status">正在读取历史计划…</p> : null}
    {history.isError ? <Alert variant="destructive"><AlertTitle>无法读取历史计划</AlertTitle><Button className="h-11" variant="outline" onClick={() => void history.refetch()}>重试</Button></Alert> : null}
    {history.data?.pages[0]?.items.length === 0 ? <p>还没有保存的计划。生成成功后会自动出现在这里。</p> : null}
    <div className="space-y-3">{history.data?.pages.flatMap((page) => page.items).map((plan) => <Link className="block rounded-lg border border-border p-4 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" key={plan.id} to={`${routePaths.planDetail}?id=${plan.id}`}><p className="font-semibold tabular-nums">{plan.plan_date} 三餐计划</p><p className="mt-1 text-sm text-muted-foreground">第 {plan.current_version} 版 · {plan.time_zone}</p></Link>)}</div>
    {history.hasNextPage ? <Button className="h-11 w-full" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()} variant="outline">加载更早计划</Button> : null}
    <Link className="flex min-h-11 items-center underline" to={routePaths.plans}>返回今日计划</Link>
  </section>
}
