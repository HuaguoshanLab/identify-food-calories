import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { dashboardQueryKeys, getDashboardHistory, getDashboardOverview } from '../api/dashboard'
import { getWeeklyReview, refreshWeeklyReview, weeklyReviewQueryKeys } from '../api/weeklyReview'
import { HistoryMealList } from './HistoryMealList'
import { TodaySummaryCard } from './TodaySummaryCard'
import { WeeklyTrend } from './WeeklyTrend'
import { WeeklyReview } from './WeeklyReview'

function startOfWeek(): string { const current = new Date(); current.setDate(current.getDate() - ((current.getDay() + 6) % 7)); return current.toISOString().slice(0, 10) }

export function RecordsPage() {
  const { request } = useAuth(); const headingRef = useRef<HTMLHeadingElement>(null); const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone; const weekStart = startOfWeek()
  const overview = useQuery({ queryKey: dashboardQueryKeys.overview(timeZone, weekStart), queryFn: () => getDashboardOverview(request, weekStart), retry: false })
  const queryClient = useQueryClient()
  const weeklyReview = useQuery({ queryKey: weeklyReviewQueryKeys.detail(timeZone, weekStart), queryFn: () => getWeeklyReview(request, weekStart), retry: false })
  const refreshReview = useMutation({ mutationFn: () => refreshWeeklyReview(request, weekStart), onSuccess: (review) => { queryClient.setQueryData(weeklyReviewQueryKeys.detail(timeZone, weekStart), review) } })
  const history = useInfiniteQuery({ queryKey: dashboardQueryKeys.history(timeZone, null), initialPageParam: null as string | null, queryFn: ({ pageParam }) => getDashboardHistory(request, pageParam), getNextPageParam: (page) => page.next_cursor, retry: false })
  useEffect(() => { headingRef.current?.focus() }, [])
  const historyPage = { groups: history.data?.pages.flatMap((page) => page.groups) ?? [], next_cursor: history.data?.pages.at(-1)?.next_cursor ?? null }
  return <section className="mx-auto w-full max-w-xl space-y-6 pb-4"><div><h1 className="text-[28px] font-bold leading-9 tracking-tight" ref={headingRef} tabIndex={-1}>记录</h1><p className="mt-2 text-[15px] leading-6 text-muted-foreground">查看你已确认保存的餐食。</p></div>{overview.isLoading ? <p className="animate-pulse text-sm text-muted-foreground motion-reduce:animate-none">正在加载今日摘要…</p> : null}{overview.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载记录。请检查网络后重新加载记录。</AlertDescription></Alert> : null}{overview.data ? <><TodaySummaryCard overview={overview.data} /><WeeklyTrend week={overview.data.week} /></> : null}{history.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载记录。请检查网络后重新加载记录。</AlertDescription></Alert> : null}{!history.isLoading && !history.isError ? <HistoryMealList isLoadingMore={history.isFetchingNextPage} onLoadMore={() => { void history.fetchNextPage() }} page={historyPage} /> : null}{weeklyReview.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载周复盘。请检查网络后重试。</AlertDescription></Alert> : null}{weeklyReview.data ? <WeeklyReview isRefreshing={refreshReview.isPending} onRefresh={() => refreshReview.mutate()} review={weeklyReview.data} /> : null}</section>
}
