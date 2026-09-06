import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { DashboardTimezoneConflictError, confirmDashboardTimeZone } from '../api/client'
import { dashboardQueryKeys, getDashboardHistory, getDashboardOverview } from '../api/dashboard'
import { getWeeklyReview, refreshWeeklyReview, weeklyReviewQueryKeys } from '../api/weeklyReview'
import { HistoryMealList } from './HistoryMealList'
import { TodaySummaryCard } from './TodaySummaryCard'
import { WeeklyTrend } from './WeeklyTrend'
import { WeeklyReview } from './WeeklyReview'

function browserTimeZone(): string | null {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  return timeZone || null
}

export function RecordsPage() {
  const { request } = useAuth()
  const confirmationStarted = useRef(false)
  const timeZone = browserTimeZone()
  const queryClient = useQueryClient()
  const confirmation = useMutation({
    mutationFn: () => timeZone ? confirmDashboardTimeZone(request, timeZone) : Promise.reject(new Error('browser time zone is unavailable')),
    retry: false,
  })

  useEffect(() => {
    if (timeZone && !confirmationStarted.current) {
      confirmationStarted.current = true
      confirmation.mutate()
    }
  }, [timeZone, confirmation])

  const dashboardEnabled = confirmation.isSuccess
  const overview = useQuery({ queryKey: dashboardQueryKeys.overview(), queryFn: () => getDashboardOverview(request), enabled: dashboardEnabled, retry: false })
  const weeklyReview = useQuery({ queryKey: weeklyReviewQueryKeys.current(), queryFn: () => getWeeklyReview(request), enabled: dashboardEnabled, retry: false })
  const refreshReview = useMutation({ mutationFn: () => refreshWeeklyReview(request), onSuccess: (review) => { queryClient.setQueryData(weeklyReviewQueryKeys.current(), review) } })
  const history = useInfiniteQuery({ queryKey: dashboardQueryKeys.history(null), initialPageParam: null as string | null, queryFn: ({ pageParam }) => getDashboardHistory(request, pageParam), getNextPageParam: (page) => page.next_cursor, enabled: dashboardEnabled, retry: false })
  const historyPage = { groups: history.data?.pages.flatMap((page) => page.groups) ?? [], next_cursor: history.data?.pages.at(-1)?.next_cursor ?? null }
  const confirmationFailed = !timeZone || confirmation.isError
  const confirmationConflict = confirmation.error instanceof DashboardTimezoneConflictError

  return <section className="mx-auto w-full max-w-xl space-y-3 pb-4">
    <div><p className="text-[13px] leading-5 text-muted-foreground">查看你已确认保存的餐食。</p></div>
    {!confirmationFailed && !dashboardEnabled ? <p className="animate-pulse text-sm text-muted-foreground motion-reduce:animate-none">正在确认统计口径…</p> : null}
    {confirmationFailed ? <Alert variant="destructive"><AlertTitle>{confirmationConflict ? '统计时区不一致' : '暂时无法确认统计时区'}</AlertTitle><AlertDescription><p>{confirmationConflict ? '当前浏览器时区与已确认的统计时区不一致。请使用已确认的浏览器设置后重试。' : '暂时无法确认统计时区。请检查浏览器设置后重试。'}</p>{timeZone ? <Button className="mt-3" onClick={() => confirmation.mutate()} type="button" variant="outline">重新尝试</Button> : null}</AlertDescription></Alert> : null}
    {dashboardEnabled && overview.isLoading ? <p className="animate-pulse text-sm text-muted-foreground motion-reduce:animate-none">正在加载今日摘要…</p> : null}
    {dashboardEnabled && overview.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载记录。请检查网络后重新加载记录。</AlertDescription></Alert> : null}
    {dashboardEnabled && overview.data ? <><TodaySummaryCard overview={overview.data} /><WeeklyTrend week={overview.data.week} /></> : null}
    {dashboardEnabled && history.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载记录。请检查网络后重新加载记录。</AlertDescription></Alert> : null}
    {dashboardEnabled && !history.isLoading && !history.isError ? <HistoryMealList isLoadingMore={history.isFetchingNextPage} onLoadMore={() => { void history.fetchNextPage() }} page={historyPage} /> : null}
    {dashboardEnabled && weeklyReview.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载周复盘。请检查网络后重试。</AlertDescription></Alert> : null}
    {dashboardEnabled && weeklyReview.data ? <WeeklyReview isRefreshing={refreshReview.isPending} onRefresh={() => refreshReview.mutate()} review={weeklyReview.data} /> : null}
  </section>
}
