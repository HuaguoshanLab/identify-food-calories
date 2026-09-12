import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'

import type { RunFilterValues, AdminRun, AdminRunMetrics } from './api'
import { readRun, readRunMetrics, readRuns, RunsApiError } from './api'
import { RunDetailDrawer } from './RunDetailDrawer'

type RunsPageProps = Readonly<{ accessToken: string | undefined, initialFilters?: RunFilterValues, onSessionExpired: () => void }>
type LoadState = 'loading' | 'ready' | 'expired' | 'forbidden' | 'error'
const pageSize = 50

function defaultFilters(): RunFilterValues {
  const occurredBefore = new Date()
  return { occurred_after: new Date(occurredBefore.getTime() - 24 * 60 * 60 * 1000).toISOString(), occurred_before: occurredBefore.toISOString() }
}

function filtersFromSearch(searchParams: URLSearchParams): RunFilterValues {
  const occurredAfter = searchParams.get('occurred_after')
  const occurredBefore = searchParams.get('occurred_before')
  if (!occurredAfter || !occurredBefore || Number.isNaN(Date.parse(occurredAfter)) || Number.isNaN(Date.parse(occurredBefore))) return defaultFilters()
  return { occurred_after: occurredAfter, occurred_before: occurredBefore }
}

function formatDuration(value: number | null) { return value === null ? '—' : `${value} ms` }
function utcDateValue(value: string | undefined) { return value?.slice(0, 10) ?? '' }
function utcDateTime(value: string, boundary: 'start' | 'end') { return `${value}T${boundary === 'start' ? '00:00:00.000' : '23:59:59.999'}Z` }

function MetricsCard({ label, value }: Readonly<{ label: string, value: string | number }>) {
  return <section className="rounded-lg border bg-card p-4"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold admin-numeric">{value}</p></section>
}

export function RunsPage({ accessToken, initialFilters, onSessionExpired }: RunsPageProps) {
  const [filters, setFilters] = useState<RunFilterValues>(() => initialFilters ?? defaultFilters())
  const [metrics, setMetrics] = useState<AdminRunMetrics>()
  const [runs, setRuns] = useState<AdminRun[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageCursors, setPageCursors] = useState<Record<number, string | undefined>>({ 1: undefined })
  const [paging, setPaging] = useState(false)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [selectedRun, setSelectedRun] = useState<AdminRun>()
  const [detailOpen, setDetailOpen] = useState(false)
  const mainRef = useRef<HTMLElement>(null)
  const requestKey = useMemo(() => JSON.stringify(filters), [filters])

  function secureFailure(requestError: unknown) {
    if (!(requestError instanceof RunsApiError)) return false
    if (requestError.status === 401 || requestError.status === 403) {
      onSessionExpired()
      setMetrics(undefined); setRuns([]); setNextCursor(null); setCurrentPage(1); setPageCursors({ 1: undefined }); setSelectedRun(undefined)
      setState(requestError.status === 403 ? 'forbidden' : 'expired')
      return true
    }
    return false
  }

  useEffect(() => {
    let active = true
    if (!accessToken) { setState('expired'); return () => { active = false } }
    setState('loading'); setError(''); setDetailOpen(false); setCurrentPage(1); setPageCursors({ 1: undefined })
    void Promise.all([readRunMetrics(accessToken, filters), readRuns(accessToken, filters)]).then(([nextMetrics, page]) => {
      if (!active) return
      setMetrics(nextMetrics); setRuns(page.items); setNextCursor(page.next_cursor); setState('ready')
    }).catch((requestError: unknown) => {
      if (!active || secureFailure(requestError)) return
      setRuns([]); setMetrics(undefined); setNextCursor(null); setError('暂时无法读取运行诊断，请稍后重试。'); setState('error')
    })
    return () => { active = false }
  // Query data is scoped to exactly this serialised allowlist filter object.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, requestKey])

  function resetPagination() {
    setNextCursor(null); setCurrentPage(1); setPageCursors({ 1: undefined })
  }

  function changeFilter(field: keyof RunFilterValues, value: string) {
    resetPagination()
    setFilters((previous) => ({ ...previous, [field]: value || undefined }))
  }

  function changeDateFilter(field: 'occurred_after' | 'occurred_before', value: string) {
    resetPagination()
    setFilters((previous) => {
      const nextValue = value ? utcDateTime(value, field === 'occurred_after' ? 'start' : 'end') : undefined
      const otherField = field === 'occurred_after' ? 'occurred_before' : 'occurred_after'
      const otherValue = previous[otherField]
      if (nextValue && otherValue && (field === 'occurred_after' ? nextValue > otherValue : nextValue < otherValue)) {
        return { ...previous, [field]: nextValue, [otherField]: utcDateTime(value, field === 'occurred_after' ? 'end' : 'start') }
      }
      return { ...previous, [field]: nextValue }
    })
  }

  async function loadPage(targetPage: number, cursor: string | undefined) {
    if (!accessToken || paging || targetPage < 1) return
    setPaging(true); setError('')
    try {
      const nextPage = await readRuns(accessToken, filters, cursor)
      setRuns(nextPage.items); setNextCursor(nextPage.next_cursor); setCurrentPage(targetPage); setPageCursors((previous) => ({ ...previous, [targetPage]: cursor, [targetPage + 1]: nextPage.next_cursor ?? undefined })); setDetailOpen(false)
    } catch (requestError) {
      if (!secureFailure(requestError)) setError('暂时无法读取下一页运行。')
    } finally {
      setPaging(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil((metrics?.terminal_count ?? 0) / pageSize))

  async function openDetail(runId: string) {
    if (!accessToken) return
    try { setSelectedRun(await readRun(accessToken, runId)); setDetailOpen(true) } catch (requestError) { if (!secureFailure(requestError)) setError('暂时无法读取运行详情。') }
  }

  if (state === 'forbidden') return <main className="mx-auto max-w-2xl p-8"><h1>无后台访问权限</h1></main>
  if (state === 'expired') return <main className="mx-auto max-w-2xl p-8"><h1>登录已失效，请重新登录。</h1></main>
  return <><a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:p-3" href="#runs-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a>
    <main id="runs-main" ref={mainRef} tabIndex={-1} className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:gap-6 lg:space-y-0 lg:overflow-hidden lg:p-8">
      {error ? <p className="rounded-md border p-4" role="alert">{error}</p> : null}
      {metrics ? <section aria-label="运行指标" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricsCard label="终态运行数" value={metrics.terminal_count} /><MetricsCard label="失败率" value={`${Math.round(Number(metrics.failure_ratio) * 100)}%`} /><MetricsCard label="P50 / P95 耗时" value={`${formatDuration(metrics.p50_elapsed_ms)} / ${formatDuration(metrics.p95_elapsed_ms)}`} /><MetricsCard label="总估算费用" value={`$${metrics.total_cost_usd}`} /></section> : null}
      <section aria-label="运行筛选" className="rounded-lg border bg-card p-4"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><label className="grid gap-1 text-sm">UTC 起始<input aria-label="UTC 起始" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeDateFilter('occurred_after', event.target.value)} type="date" value={utcDateValue(filters.occurred_after)} /></label><label className="grid gap-1 text-sm">UTC 结束<input aria-label="UTC 结束" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeDateFilter('occurred_before', event.target.value)} type="date" value={utcDateValue(filters.occurred_before)} /></label><label className="grid gap-1 text-sm">运行状态<select aria-label="运行状态" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('status', event.target.value)} value={filters.status ?? ''}><option value="">全部终态</option><option value="completed">完成</option><option value="failed">失败</option><option value="limit_reached">达到限制</option></select></label><label className="grid gap-1 text-sm">图版本<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('graph_version', event.target.value)} value={filters.graph_version ?? ''} /></label><label className="grid gap-1 text-sm">模型（provider:model）<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('model', event.target.value)} value={filters.model ?? ''} /></label><label className="grid gap-1 text-sm">失败节点<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('failure_node', event.target.value)} value={filters.failure_node ?? ''} /></label><label className="grid gap-1 text-sm">失败码<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('failure_code', event.target.value)} value={filters.failure_code ?? ''} /></label></div></section>
      {state === 'loading' ? <p aria-busy="true" aria-live="polite">正在读取运行诊断…</p> : <section aria-label="终态运行" className="min-w-0 rounded-lg border bg-card lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-hidden"><div aria-label="终态运行表格" className="min-h-0 overflow-auto lg:flex-1" role="region" tabIndex={0}><table aria-busy={paging} aria-label="终态运行列表" className="w-full min-w-[48rem] text-left text-sm"><thead className="sticky top-0 z-10 border-y bg-slate-50 text-xs text-muted-foreground shadow-[0_1px_0_var(--border)]"><tr><th className="p-3" aria-sort="descending">状态</th><th className="p-3">完成时间（UTC）</th><th className="p-3">图版本</th><th className="p-3">模型</th><th className="p-3">耗时</th><th className="p-3">失败码</th><th className="p-3"><span className="sr-only">详情</span></th></tr></thead><tbody>{runs.map((run) => <tr className="border-b hover:bg-muted/20" key={run.id}><td className="p-3">{run.status}</td><td className="p-3 admin-numeric">{new Date(run.finished_at).toISOString()}</td><td className="p-3">{run.graph_version}</td><td className="p-3">{run.model_provider && run.model_version ? `${run.model_provider}:${run.model_version}` : '—'}</td><td className="p-3 admin-numeric">{run.elapsed_ms} ms</td><td className="p-3">{run.failure_code ?? '—'}</td><td className="p-3"><button className="rounded-md border px-3 py-2" onClick={() => void openDetail(run.id)} type="button">查看运行详情</button></td></tr>)}</tbody></table>{runs.length === 0 ? <p className="p-6 text-sm text-muted-foreground">该筛选范围内没有终态运行。</p> : null}</div><div className="flex flex-wrap items-center justify-end gap-4 border-t px-5 py-4 text-xs text-muted-foreground"><span>{metrics ? `共 ${metrics.terminal_count} 条` : '共 — 条'}</span><nav aria-label="运行分页" className="flex items-center gap-2"><button aria-label="上一页" className="rounded border p-1.5 disabled:opacity-30" disabled={currentPage <= 1 || paging || state !== 'ready'} onClick={() => void loadPage(currentPage - 1, pageCursors[currentPage - 1])} type="button"><ChevronLeft size={15} /></button><span aria-current="page" className="admin-numeric rounded border border-blue-300 px-2.5 py-1 text-blue-600">{currentPage}</span><span>/ {totalPages}</span><button aria-label="下一页" className="rounded border p-1.5 disabled:opacity-30" disabled={!nextCursor || paging || state !== 'ready'} onClick={() => void loadPage(currentPage + 1, nextCursor ?? undefined)} type="button"><ChevronRight size={15} /></button></nav></div></section>}
    </main><RunDetailDrawer onClose={() => setDetailOpen(false)} run={detailOpen ? selectedRun : undefined} /></>
}

export function AdminRunsPage() {
  // Route assembly owns the runtime-only token; this component never persists it.
  const { accessToken, clearSession } = useAdminAuth()
  const [searchParams] = useSearchParams()
  const initialFilters = useMemo(() => filtersFromSearch(searchParams), [searchParams])
  return <RunsPage accessToken={accessToken} initialFilters={initialFilters} key={JSON.stringify(initialFilters)} onSessionExpired={clearSession} />
}
