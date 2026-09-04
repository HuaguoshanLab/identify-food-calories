import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAdminAuth } from '@/auth/AdminAuthProvider'

import { OverviewApiError, readOverviewMetrics, recentTerminalWindow } from './api'

type OverviewProps = Readonly<{ accessToken: string | undefined, onSessionExpired: () => void }>

function runLink(window: Readonly<{ occurred_after: string, occurred_before: string }>) {
  return `/admin/runs?${new URLSearchParams(window)}`
}

function MetricCard({ label, value, href }: Readonly<{ label: string, value: string | number, href: string }>) {
  return <Link aria-label={label} className="rounded-lg border bg-card p-4 transition-colors hover:bg-muted motion-reduce:transition-none" to={href}><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold admin-numeric">{value}</p><span className="mt-3 inline-block text-sm">查看运行审计</span></Link>
}

export function AdminOverviewPage({ accessToken, onSessionExpired }: OverviewProps) {
  // Freeze the server request window for this mounted overview; recomputing it
  // during render would continuously invalidate the query and mismatch its links.
  const [window] = useState(recentTerminalWindow)
  const query = useQuery({
    enabled: Boolean(accessToken),
    queryFn: () => readOverviewMetrics(accessToken as string, window),
    queryKey: ['admin', 'overview', 'terminal-metrics', window],
  })
  const error = query.error
  useEffect(() => {
    if (error instanceof OverviewApiError && (error.status === 401 || error.status === 403)) onSessionExpired()
  }, [error, onSessionExpired])
  if (!accessToken || (error instanceof OverviewApiError && error.status === 403)) return <section className="p-6"><h2 className="text-[28px] font-semibold">无后台访问权限</h2><p className="mt-2">你的当前账号没有管理权限。请使用管理员账号登录。</p></section>
  if (error instanceof OverviewApiError && error.status === 401) return <section className="p-6"><h2 className="text-[28px] font-semibold">登录已失效，请重新登录。</h2></section>
  const href = runLink(query.data ? { occurred_after: query.data.from, occurred_before: query.data.to } : window)
  return <section className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8" aria-labelledby="overview-title"><header><h2 className="text-[28px] font-semibold" id="overview-title">运行概览</h2><p className="mt-1 text-sm text-muted-foreground">近 24 小时（UTC） · 仅终态运行 · 服务端计算</p></header>{query.isLoading ? <p aria-busy="true" aria-live="polite">正在读取运行概览…</p> : null}{query.isError && !(error instanceof OverviewApiError && [401, 403].includes(error.status)) ? <p className="rounded-md border p-4" role="alert">暂时无法读取运行概览，请稍后重试。</p> : null}{query.data ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><MetricCard href={href} label="总终态运行数" value={query.data.terminal_count} /><MetricCard href={href} label="失败率" value={`${Math.round(Number(query.data.failure_ratio) * 100)}%`} /><MetricCard href={href} label="P50 / P95 耗时" value={`${query.data.p50_elapsed_ms ?? '—'} / ${query.data.p95_elapsed_ms ?? '—'} ms`} /><MetricCard href={href} label="总估算费用" value={`$${query.data.total_cost_usd}`} /></div> : null}<Link className="inline-flex h-10 items-center rounded-md border px-4" to={href}>查看运行审计</Link></section>
}

export function AdminOverviewRoute() {
  const { accessToken, clearSession } = useAdminAuth()
  return <AdminOverviewPage accessToken={accessToken} onSessionExpired={clearSession} />
}
