import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { confirmDashboardTimeZone } from '../api/client'
import { dashboardQueryKeys, getDashboardHistory, getDashboardOverview } from '../api/dashboard'
import { getWeeklyReview, refreshWeeklyReview, weeklyReviewQueryKeys } from '../api/weeklyReview'
import { HistoryMealList } from './HistoryMealList'
import { TodaySummaryCard } from './TodaySummaryCard'
import { WeeklyTrend } from './WeeklyTrend'
import { WeeklyReview } from './WeeklyReview'

type CalendarDate = { year: number; month: number; day: number }

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
}

function daysInMonth(year: number, month: number): number {
  return [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1] ?? 0
}

function weekday({ year, month, day }: CalendarDate): number {
  // Sakamoto's Gregorian calendar formula returns Sunday = 0 without consulting host time zone.
  const offsets = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
  const adjustedYear = month < 3 ? year - 1 : year
  return (adjustedYear + Math.floor(adjustedYear / 4) - Math.floor(adjustedYear / 100) + Math.floor(adjustedYear / 400) + (offsets[month - 1] ?? 0) + day) % 7
}

function subtractDays(date: CalendarDate, amount: number): CalendarDate {
  let { year, month, day } = date
  for (let remaining = amount; remaining > 0; remaining -= 1) {
    if (day > 1) day -= 1
    else {
      if (month === 1) { year -= 1; month = 12 } else month -= 1
      day = daysInMonth(year, month)
    }
  }
  return { year, month, day }
}

function formatCalendarDate({ year, month, day }: CalendarDate): string {
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

/** Derives a local calendar Monday from an instant, independently of the browser process timezone. */
export function deriveLocalWeekStart(instant: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(instant)
  const calendarPart = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value
  const year = Number(calendarPart('year'))
  const month = Number(calendarPart('month'))
  const day = Number(calendarPart('day'))
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) throw new Error('browser calendar is unavailable')

  const localDate = { year, month, day }
  return formatCalendarDate(subtractDays(localDate, (weekday(localDate) + 6) % 7))
}

function browserTimeZone(): string | null {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  return timeZone || null
}

export function RecordsPage() {
  const { request } = useAuth()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const confirmationStarted = useRef(false)
  const timeZone = browserTimeZone()
  const weekStart = timeZone ? deriveLocalWeekStart(new Date(), timeZone) : null
  const queryClient = useQueryClient()
  const confirmation = useMutation({
    mutationFn: () => timeZone ? confirmDashboardTimeZone(request, timeZone) : Promise.reject(new Error('browser time zone is unavailable')),
    retry: false,
  })

  useEffect(() => { headingRef.current?.focus() }, [])
  useEffect(() => {
    if (timeZone && !confirmationStarted.current) {
      confirmationStarted.current = true
      confirmation.mutate()
    }
  }, [timeZone, confirmation])

  const dashboardEnabled = confirmation.isSuccess && weekStart !== null
  const overview = useQuery({ queryKey: dashboardQueryKeys.overview(weekStart ?? ''), queryFn: () => getDashboardOverview(request, weekStart!), enabled: dashboardEnabled, retry: false })
  const weeklyReview = useQuery({ queryKey: weeklyReviewQueryKeys.detail(weekStart ?? ''), queryFn: () => getWeeklyReview(request, weekStart!), enabled: dashboardEnabled, retry: false })
  const refreshReview = useMutation({ mutationFn: () => refreshWeeklyReview(request, weekStart!), onSuccess: (review) => { if (weekStart) queryClient.setQueryData(weeklyReviewQueryKeys.detail(weekStart), review) } })
  const history = useInfiniteQuery({ queryKey: dashboardQueryKeys.history(null), initialPageParam: null as string | null, queryFn: ({ pageParam }) => getDashboardHistory(request, pageParam), getNextPageParam: (page) => page.next_cursor, enabled: dashboardEnabled, retry: false })
  const historyPage = { groups: history.data?.pages.flatMap((page) => page.groups) ?? [], next_cursor: history.data?.pages.at(-1)?.next_cursor ?? null }
  const confirmationFailed = !timeZone || !weekStart || confirmation.isError

  return <section className="mx-auto w-full max-w-xl space-y-6 pb-4">
    <div><h1 className="text-[28px] font-bold leading-9 tracking-tight" ref={headingRef} tabIndex={-1}>记录</h1><p className="mt-2 text-[15px] leading-6 text-muted-foreground">查看你已确认保存的餐食。</p></div>
    {!confirmationFailed && !dashboardEnabled ? <p className="animate-pulse text-sm text-muted-foreground motion-reduce:animate-none">正在确认统计口径…</p> : null}
    {confirmationFailed ? <Alert variant="destructive"><AlertTitle>暂时无法确认统计时区</AlertTitle><AlertDescription><p>暂时无法确认统计时区。请检查浏览器设置后重试。</p>{timeZone ? <Button className="mt-3" onClick={() => confirmation.mutate()} type="button" variant="outline">重新尝试</Button> : null}</AlertDescription></Alert> : null}
    {dashboardEnabled && overview.isLoading ? <p className="animate-pulse text-sm text-muted-foreground motion-reduce:animate-none">正在加载今日摘要…</p> : null}
    {dashboardEnabled && overview.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载记录。请检查网络后重新加载记录。</AlertDescription></Alert> : null}
    {dashboardEnabled && overview.data ? <><TodaySummaryCard overview={overview.data} /><WeeklyTrend week={overview.data.week} /></> : null}
    {dashboardEnabled && history.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载记录。请检查网络后重新加载记录。</AlertDescription></Alert> : null}
    {dashboardEnabled && !history.isLoading && !history.isError ? <HistoryMealList isLoadingMore={history.isFetchingNextPage} onLoadMore={() => { void history.fetchNextPage() }} page={historyPage} /> : null}
    {dashboardEnabled && weeklyReview.isError ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>暂时无法加载周复盘。请检查网络后重试。</AlertDescription></Alert> : null}
    {dashboardEnabled && weeklyReview.data ? <WeeklyReview isRefreshing={refreshReview.isPending} onRefresh={() => refreshReview.mutate()} review={weeklyReview.data} /> : null}
  </section>
}
