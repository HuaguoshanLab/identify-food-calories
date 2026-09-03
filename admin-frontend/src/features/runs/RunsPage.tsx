import { useEffect, useMemo, useRef, useState } from 'react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'

import type { RunFilterValues, AdminRun, AdminRunMetrics } from './api'
import { readRun, readRunMetrics, readRuns, RunsApiError } from './api'
import { RunDetailDrawer } from './RunDetailDrawer'

type RunsPageProps = Readonly<{ accessToken: string | undefined, onSessionExpired: () => void }>
type LoadState = 'loading' | 'ready' | 'expired' | 'forbidden' | 'error'

function defaultFilters(): RunFilterValues {
  const occurredBefore = new Date()
  return { occurred_after: new Date(occurredBefore.getTime() - 24 * 60 * 60 * 1000).toISOString(), occurred_before: occurredBefore.toISOString() }
}

function formatDuration(value: number | null) { return value === null ? '—' : `${value} ms` }

function MetricsCard({ label, value }: Readonly<{ label: string, value: string | number }>) {
  return <section className="rounded-lg border bg-card p-4"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold admin-numeric">{value}</p></section>
}

export function RunsPage({ accessToken, onSessionExpired }: RunsPageProps) {
  const [filters, setFilters] = useState<RunFilterValues>(defaultFilters)
  const [metrics, setMetrics] = useState<AdminRunMetrics>()
  const [runs, setRuns] = useState<AdminRun[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
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
      setMetrics(undefined); setRuns([]); setNextCursor(null); setSelectedRun(undefined)
      setState(requestError.status === 403 ? 'forbidden' : 'expired')
      return true
    }
    return false
  }

  useEffect(() => {
    let active = true
    if (!accessToken) { setState('expired'); return () => { active = false } }
    setState('loading'); setError(''); setDetailOpen(false)
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

  function changeFilter(field: keyof RunFilterValues, value: string) {
    setNextCursor(null)
    setFilters((previous) => ({ ...previous, [field]: value || undefined }))
  }

  async function loadNextPage() {
    if (!accessToken || !nextCursor) return
    try {
      const page = await readRuns(accessToken, filters, nextCursor)
      setRuns(page.items); setNextCursor(page.next_cursor)
    } catch (requestError) {
      if (!secureFailure(requestError)) setError('暂时无法读取下一页运行。')
    }
  }

  async function openDetail(runId: string) {
    if (!accessToken) return
    try { setSelectedRun(await readRun(accessToken, runId)); setDetailOpen(true) } catch (requestError) { if (!secureFailure(requestError)) setError('暂时无法读取运行详情。') }
  }

  if (state === 'forbidden') return <main className="mx-auto max-w-2xl p-8"><h1>无后台访问权限</h1></main>
  if (state === 'expired') return <main className="mx-auto max-w-2xl p-8"><h1>登录已失效，请重新登录。</h1></main>
  return <><a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:p-3" href="#runs-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a>
    <main id="runs-main" ref={mainRef} tabIndex={-1} className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header><h1 className="text-[28px] font-semibold">运行诊断</h1><p className="mt-1 text-sm text-muted-foreground">仅展示终态运行的最小化服务端账本证据；所有时间均为 UTC。</p></header>
      {error ? <p className="rounded-md border p-4" role="alert">{error}</p> : null}
      {metrics ? <section aria-label="运行指标" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricsCard label="终态运行数" value={metrics.terminal_count} /><MetricsCard label="失败率" value={`${Math.round(Number(metrics.failure_ratio) * 100)}%`} /><MetricsCard label="P50 / P95 耗时" value={`${formatDuration(metrics.p50_elapsed_ms)} / ${formatDuration(metrics.p95_elapsed_ms)}`} /><MetricsCard label="总估算费用" value={`$${metrics.total_cost_usd}`} /></section> : null}
      <section aria-label="运行筛选" className="rounded-lg border bg-card p-4"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><label className="grid gap-1 text-sm">UTC 起始<input aria-label="UTC 起始" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('occurred_after', event.target.value)} value={filters.occurred_after ?? ''} /></label><label className="grid gap-1 text-sm">UTC 结束<input aria-label="UTC 结束" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('occurred_before', event.target.value)} value={filters.occurred_before ?? ''} /></label><label className="grid gap-1 text-sm">运行状态<select aria-label="运行状态" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('status', event.target.value)} value={filters.status ?? ''}><option value="">全部终态</option><option value="completed">完成</option><option value="failed">失败</option><option value="limit_reached">达到限制</option></select></label><label className="grid gap-1 text-sm">图版本<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('graph_version', event.target.value)} value={filters.graph_version ?? ''} /></label><label className="grid gap-1 text-sm">模型（provider:model）<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('model', event.target.value)} value={filters.model ?? ''} /></label><label className="grid gap-1 text-sm">失败节点<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('failure_node', event.target.value)} value={filters.failure_node ?? ''} /></label><label className="grid gap-1 text-sm">失败码<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('failure_code', event.target.value)} value={filters.failure_code ?? ''} /></label></div></section>
      {state === 'loading' ? <p aria-busy="true" aria-live="polite">正在读取运行诊断…</p> : <section className="overflow-x-auto rounded-lg border bg-card"><table aria-label="终态运行列表" className="w-full min-w-[48rem] text-left text-sm"><thead><tr className="border-b"><th className="p-3" aria-sort="descending">状态</th><th className="p-3">完成时间（UTC）</th><th className="p-3">图版本</th><th className="p-3">模型</th><th className="p-3">耗时</th><th className="p-3">失败码</th><th className="p-3"><span className="sr-only">详情</span></th></tr></thead><tbody>{runs.map((run) => <tr className="border-b" key={run.id}><td className="p-3">{run.status}</td><td className="p-3 admin-numeric">{new Date(run.finished_at).toISOString()}</td><td className="p-3">{run.graph_version}</td><td className="p-3">{run.model_provider && run.model_version ? `${run.model_provider}:${run.model_version}` : '—'}</td><td className="p-3 admin-numeric">{run.elapsed_ms} ms</td><td className="p-3">{run.failure_code ?? '—'}</td><td className="p-3"><button className="rounded-md border px-3 py-2" onClick={() => void openDetail(run.id)} type="button">查看运行详情</button></td></tr>)}</tbody></table>{runs.length === 0 ? <p className="p-6 text-sm text-muted-foreground">该筛选范围内没有终态运行。</p> : null}</section>}
      <div><button className="rounded-md border px-4 py-2 disabled:opacity-50" disabled={!nextCursor || state !== 'ready'} onClick={() => void loadNextPage()} type="button">下一页</button></div>
    </main><RunDetailDrawer onClose={() => setDetailOpen(false)} run={detailOpen ? selectedRun : undefined} /></>
}

export function AdminRunsPage() {
  // Route assembly owns the runtime-only token; this component never persists it.
  const { accessToken, clearSession } = useAdminAuth()
  return <RunsPage accessToken={accessToken} onSessionExpired={clearSession} />
}
