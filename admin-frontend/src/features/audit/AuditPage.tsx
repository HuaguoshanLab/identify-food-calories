import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'

import { AuditApiError, readAudit, type AdminAuditEvent, type AuditFilterValues } from './api'

type AuditPageProps = Readonly<{ accessToken: string | undefined, onSessionExpired: () => void }>
type LoadState = 'loading' | 'ready' | 'expired' | 'forbidden' | 'error'
const safeDiffFields = new Set(['enabled', 'provider', 'model_alias', 'version', 'canonical_name', 'aliases', 'energy_kcal_per_100g', 'protein_g_per_100g', 'fat_g_per_100g', 'carbohydrate_g_per_100g', 'source_name', 'source_url', 'authorization_status', 'eligibility'])

function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }).format(new Date(value)) }
function utcDateValue(value: string | undefined) { return value?.slice(0, 10) ?? '' }
function utcDateTime(value: string, boundary: 'start' | 'end') { return `${value}T${boundary === 'start' ? '00:00:00.000' : '23:59:59.999'}Z` }
function diffs(event: AdminAuditEvent) {
  return [...new Set([...Object.keys(event.before), ...Object.keys(event.after)])].filter((field) => safeDiffFields.has(field)).map((field) => ({ field, before: String(event.before[field] ?? '—'), after: String(event.after[field] ?? '—') }))
}

export function AuditPage({ accessToken, onSessionExpired }: AuditPageProps) {
  const [filters, setFilters] = useState<AuditFilterValues>({})
  const [events, setEvents] = useState<AdminAuditEvent[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageCursors, setPageCursors] = useState<Record<number, string | undefined>>({ 1: undefined })
  const [paging, setPaging] = useState(false)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const mainRef = useRef<HTMLElement>(null)
  const requestKey = useMemo(() => JSON.stringify(filters), [filters])

  function secureFailure(requestError: unknown) {
    if (!(requestError instanceof AuditApiError)) return false
    if (requestError.status === 401 || requestError.status === 403) { onSessionExpired(); setEvents([]); setNextCursor(null); setCurrentPage(1); setPageCursors({ 1: undefined }); setState(requestError.status === 403 ? 'forbidden' : 'expired'); return true }
    return false
  }

  useEffect(() => {
    let active = true
    if (!accessToken) { setState('expired'); return () => { active = false } }
    setState('loading'); setError(''); setCurrentPage(1); setPageCursors({ 1: undefined })
    void readAudit(accessToken, filters).then((page) => { if (active) { setEvents(page.items); setNextCursor(page.next_cursor); setState('ready') } }).catch((requestError: unknown) => { if (!active || secureFailure(requestError)) return; setEvents([]); setNextCursor(null); setError('暂时无法读取操作审计，请稍后重试。'); setState('error') })
    return () => { active = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, requestKey])

  function resetPagination() { setNextCursor(null); setCurrentPage(1); setPageCursors({ 1: undefined }) }
  function changeFilter(field: keyof AuditFilterValues, value: string) { resetPagination(); setFilters((previous) => ({ ...previous, [field]: value || undefined })) }
  function changeDateFilter(field: 'occurred_after' | 'occurred_before', value: string) {
    resetPagination()
    setFilters((previous) => {
      const nextValue = value ? utcDateTime(value, field === 'occurred_after' ? 'start' : 'end') : undefined
      const otherField = field === 'occurred_after' ? 'occurred_before' : 'occurred_after'
      const otherValue = previous[otherField]
      if (nextValue && otherValue && (field === 'occurred_after' ? nextValue > otherValue : nextValue < otherValue)) return { ...previous, [field]: nextValue, [otherField]: utcDateTime(value, field === 'occurred_after' ? 'end' : 'start') }
      return { ...previous, [field]: nextValue }
    })
  }
  async function loadPage(targetPage: number, cursor: string | undefined) {
    if (!accessToken || paging || targetPage < 1) return
    setPaging(true); setError('')
    try {
      const page = await readAudit(accessToken, filters, cursor)
      setEvents(page.items); setNextCursor(page.next_cursor); setCurrentPage(targetPage); setPageCursors((previous) => ({ ...previous, [targetPage]: cursor, [targetPage + 1]: page.next_cursor ?? undefined }))
    } catch (requestError) {
      if (!secureFailure(requestError)) setError('暂时无法读取审计分页。')
    } finally { setPaging(false) }
  }

  if (state === 'forbidden') return <main className="mx-auto max-w-2xl p-8"><h1>无后台访问权限</h1></main>
  if (state === 'expired') return <main className="mx-auto max-w-2xl p-8"><h1>登录已失效，请重新登录。</h1></main>
  return <><a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:p-3" href="#audit-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a><main id="audit-main" ref={mainRef} tabIndex={-1} className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:gap-6 lg:space-y-0 lg:overflow-hidden lg:p-8">{error ? <p className="rounded-md border p-4" role="alert">{error}</p> : null}<section aria-label="审计筛选" className="rounded-lg border bg-card p-4"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><label className="grid gap-1 text-sm">UTC 起始<input aria-label="UTC 起始" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeDateFilter('occurred_after', event.target.value)} type="date" value={utcDateValue(filters.occurred_after)} /></label><label className="grid gap-1 text-sm">UTC 结束<input aria-label="UTC 结束" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeDateFilter('occurred_before', event.target.value)} type="date" value={utcDateValue(filters.occurred_before)} /></label><label className="grid gap-1 text-sm">操作动作<input aria-label="操作动作" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('action', event.target.value)} value={filters.action ?? ''} /></label><label className="grid gap-1 text-sm">对象类型<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('object_type', event.target.value)} value={filters.object_type ?? ''} /></label><label className="grid gap-1 text-sm">对象标识<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('object_id', event.target.value)} value={filters.object_id ?? ''} /></label><label className="grid gap-1 text-sm">操作者<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('actor', event.target.value)} value={filters.actor ?? ''} /></label><label className="grid gap-1 text-sm">原因<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('reason', event.target.value)} value={filters.reason ?? ''} /></label></div></section>{state === 'loading' ? <p aria-busy="true" aria-live="polite">正在读取操作审计…</p> : <section aria-label="操作审计" className="min-w-0 rounded-lg border bg-card lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-hidden"><div aria-label="操作审计表格" className="min-h-0 overflow-auto lg:flex-1" role="region" tabIndex={0}><table aria-busy={paging} aria-label="操作审计时间线" className="w-full min-w-[62rem] text-left text-sm"><thead className="sticky top-0 z-10 border-y bg-slate-50 text-xs text-muted-foreground shadow-[0_1px_0_var(--border)]"><tr><th className="p-3">时间（UTC）</th><th className="p-3">操作者</th><th className="p-3">动作</th><th className="p-3">对象</th><th className="p-3">原因</th><th className="p-3">字段差异</th><th className="p-3">版本</th></tr></thead><tbody>{events.map((event) => <tr className="border-b align-top hover:bg-muted/20" key={event.id}><td className="p-3 whitespace-nowrap">{formatDate(event.occurred_at)}</td><td className="p-3">{event.actor_identifier}</td><td className="p-3">{event.action}</td><td className="p-3">{event.object_type}:{event.object_id}</td><td className="p-3">{event.reason}</td><td className="p-3">{diffs(event).length === 0 ? '—' : <ul>{diffs(event).map((diff) => <li key={diff.field}><span>{diff.field}</span>: {diff.before} → {diff.after}</li>)}</ul>}</td><td className="p-3">{event.related_version ?? '—'}</td></tr>)}</tbody></table>{events.length === 0 ? <p className="p-6 text-sm text-muted-foreground">该筛选范围内没有审计记录。</p> : null}</div><div className="flex flex-wrap items-center justify-end gap-4 border-t px-5 py-4 text-xs text-muted-foreground"><span>第 {currentPage} 页</span><nav aria-label="操作审计分页" className="flex items-center gap-2"><button aria-label="上一页" className="rounded border p-1.5 disabled:opacity-30" disabled={currentPage <= 1 || paging || state !== 'ready'} onClick={() => void loadPage(currentPage - 1, pageCursors[currentPage - 1])} type="button"><ChevronLeft size={15} /></button><span aria-current="page" className="admin-numeric rounded border border-blue-300 px-2.5 py-1 text-blue-600">{currentPage}</span><button aria-label="下一页" className="rounded border p-1.5 disabled:opacity-30" disabled={!nextCursor || paging || state !== 'ready'} onClick={() => void loadPage(currentPage + 1, nextCursor ?? undefined)} type="button"><ChevronRight size={15} /></button></nav></div></section>}</main></>
}

export function AdminAuditPage() {
  const { accessToken, clearSession } = useAdminAuth()
  return <AuditPage accessToken={accessToken} onSessionExpired={clearSession} />
}
