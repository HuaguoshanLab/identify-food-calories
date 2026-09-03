import { useEffect, useMemo, useRef, useState } from 'react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'

import { AuditApiError, readAudit, type AdminAuditEvent, type AuditFilterValues } from './api'

type AuditPageProps = Readonly<{ accessToken: string | undefined, onSessionExpired: () => void }>
type LoadState = 'loading' | 'ready' | 'expired' | 'forbidden' | 'error'
const safeDiffFields = new Set(['enabled', 'provider', 'model_alias', 'version', 'canonical_name', 'aliases', 'energy_kcal_per_100g', 'protein_g_per_100g', 'fat_g_per_100g', 'carbohydrate_g_per_100g', 'source_name', 'source_url', 'authorization_status', 'eligibility'])

function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }).format(new Date(value)) }
function diffs(event: AdminAuditEvent) {
  return [...new Set([...Object.keys(event.before), ...Object.keys(event.after)])].filter((field) => safeDiffFields.has(field)).map((field) => ({ field, before: String(event.before[field] ?? '—'), after: String(event.after[field] ?? '—') }))
}

export function AuditPage({ accessToken, onSessionExpired }: AuditPageProps) {
  const [filters, setFilters] = useState<AuditFilterValues>({})
  const [events, setEvents] = useState<AdminAuditEvent[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const mainRef = useRef<HTMLElement>(null)
  const requestKey = useMemo(() => JSON.stringify(filters), [filters])

  function secureFailure(requestError: unknown) {
    if (!(requestError instanceof AuditApiError)) return false
    if (requestError.status === 401 || requestError.status === 403) { onSessionExpired(); setEvents([]); setNextCursor(null); setState(requestError.status === 403 ? 'forbidden' : 'expired'); return true }
    return false
  }

  useEffect(() => {
    let active = true
    if (!accessToken) { setState('expired'); return () => { active = false } }
    setState('loading'); setError('')
    void readAudit(accessToken, filters).then((page) => { if (active) { setEvents(page.items); setNextCursor(page.next_cursor); setState('ready') } }).catch((requestError: unknown) => { if (!active || secureFailure(requestError)) return; setEvents([]); setNextCursor(null); setError('暂时无法读取操作审计，请稍后重试。'); setState('error') })
    return () => { active = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, requestKey])

  function changeFilter(field: keyof AuditFilterValues, value: string) { setNextCursor(null); setFilters((previous) => ({ ...previous, [field]: value || undefined })) }
  async function loadNextPage() { if (!accessToken || !nextCursor) return; try { const page = await readAudit(accessToken, filters, nextCursor); setEvents(page.items); setNextCursor(page.next_cursor) } catch (requestError) { if (!secureFailure(requestError)) setError('暂时无法读取下一页审计记录。') } }

  if (state === 'forbidden') return <main className="mx-auto max-w-2xl p-8"><h1>无后台访问权限</h1></main>
  if (state === 'expired') return <main className="mx-auto max-w-2xl p-8"><h1>登录已失效，请重新登录。</h1></main>
  return <><a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:p-3" href="#audit-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a><main id="audit-main" ref={mainRef} tabIndex={-1} className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"><header><h1 className="text-[28px] font-semibold">操作审计</h1><p className="mt-1 text-sm text-muted-foreground">只读服务器审计证据；不会把浏览器输入或目录响应伪造成审计记录。</p></header>{error ? <p className="rounded-md border p-4" role="alert">{error}</p> : null}<section aria-label="审计筛选" className="rounded-lg border bg-card p-4"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><label className="grid gap-1 text-sm">UTC 起始<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('occurred_after', event.target.value)} value={filters.occurred_after ?? ''} /></label><label className="grid gap-1 text-sm">UTC 结束<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('occurred_before', event.target.value)} value={filters.occurred_before ?? ''} /></label><label className="grid gap-1 text-sm">操作动作<input aria-label="操作动作" className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('action', event.target.value)} value={filters.action ?? ''} /></label><label className="grid gap-1 text-sm">对象类型<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('object_type', event.target.value)} value={filters.object_type ?? ''} /></label><label className="grid gap-1 text-sm">对象标识<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('object_id', event.target.value)} value={filters.object_id ?? ''} /></label><label className="grid gap-1 text-sm">操作者<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('actor', event.target.value)} value={filters.actor ?? ''} /></label><label className="grid gap-1 text-sm">原因<input className="h-10 rounded-md border bg-background px-3" onChange={(event) => changeFilter('reason', event.target.value)} value={filters.reason ?? ''} /></label></div></section>{state === 'loading' ? <p aria-busy="true" aria-live="polite">正在读取操作审计…</p> : <section className="overflow-x-auto rounded-lg border bg-card"><table aria-label="操作审计时间线" className="w-full min-w-[62rem] text-left text-sm"><thead><tr className="border-b"><th className="p-3">时间（UTC）</th><th className="p-3">操作者</th><th className="p-3">动作</th><th className="p-3">对象</th><th className="p-3">原因</th><th className="p-3">字段差异</th><th className="p-3">版本</th></tr></thead><tbody>{events.map((event) => <tr className="border-b align-top" key={event.id}><td className="p-3 whitespace-nowrap">{formatDate(event.occurred_at)}</td><td className="p-3">{event.actor_identifier}</td><td className="p-3">{event.action}</td><td className="p-3">{event.object_type}:{event.object_id}</td><td className="p-3">{event.reason}</td><td className="p-3">{diffs(event).length === 0 ? '—' : <ul>{diffs(event).map((diff) => <li key={diff.field}><span>{diff.field}</span>: {diff.before} → {diff.after}</li>)}</ul>}</td><td className="p-3">{event.related_version ?? '—'}</td></tr>)}</tbody></table>{events.length === 0 ? <p className="p-6 text-sm text-muted-foreground">该筛选范围内没有审计记录。</p> : null}</section>}<button className="rounded-md border px-4 py-2 disabled:opacity-50" disabled={!nextCursor || state !== 'ready'} onClick={() => void loadNextPage()} type="button">下一页</button></main></>
}

export function AdminAuditPage() {
  const { accessToken, clearSession } = useAdminAuth()
  return <AuditPage accessToken={accessToken} onSessionExpired={clearSession} />
}
