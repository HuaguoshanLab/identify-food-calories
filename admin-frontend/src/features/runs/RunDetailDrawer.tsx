import { useEffect } from 'react'

import type { AdminRun } from './api'

type RunDetailDrawerProps = Readonly<{
  run: AdminRun | undefined
  onClose: () => void
}>

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }).format(new Date(value))
}

/** The drawer intentionally maps only already allowlisted run DTO fields. */
export function RunDetailDrawer({ run, onClose }: RunDetailDrawerProps) {
  useEffect(() => {
    if (!run) return undefined
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [onClose, run])
  if (!run) return null
  return <div aria-labelledby="run-detail-title" aria-modal="true" className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose} role="dialog">
    <section className="h-full w-full max-w-xl overflow-y-auto bg-card p-6 shadow-xl sm:w-[32rem]" onClick={(event) => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold" id="run-detail-title">运行详情</h2><p className="mt-1 text-sm text-muted-foreground">仅展示服务端白名单的诊断证据。</p></div><button aria-label="关闭运行详情" className="rounded-md border px-3 py-2" onClick={onClose} type="button">关闭</button></div>
      <dl className="mt-6 grid grid-cols-[minmax(8rem,1fr)_minmax(0,2fr)] gap-x-4 gap-y-3 text-sm">
        <dt className="text-muted-foreground">状态</dt><dd>{run.status}</dd><dt className="text-muted-foreground">图版本</dt><dd>{run.graph_version}</dd>
        <dt className="text-muted-foreground">模型</dt><dd>{run.model_provider && run.model_version ? `${run.model_provider}:${run.model_version}` : '—'}</dd>
        <dt className="text-muted-foreground">完成时间（UTC）</dt><dd>{formatDate(run.finished_at)}</dd><dt className="text-muted-foreground">耗时</dt><dd className="admin-numeric">{run.elapsed_ms} ms</dd>
        <dt className="text-muted-foreground">图步骤 / 模型调用 / 工具调用</dt><dd className="admin-numeric">{run.graph_steps} / {run.model_calls} / {run.tool_calls}</dd>
        <dt className="text-muted-foreground">估算费用</dt><dd className="admin-numeric">${run.estimated_cost_usd}</dd><dt className="text-muted-foreground">失败码</dt><dd>{run.failure_code ?? '—'}</dd>
      </dl>
      <section aria-label="调用证据" className="mt-8"><h3 className="font-medium">调用证据</h3>{run.invocations.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">无可展示的调用证据。</p> : <ul className="mt-3 space-y-3">{run.invocations.map((invocation) => <li className="rounded-md border p-3 text-sm" key={`${invocation.node_name}-${invocation.attempt}`}><strong>{invocation.node_name}</strong><p className="mt-1">{invocation.status} · 第 {invocation.attempt} 次 · <span className="admin-numeric">${invocation.cost_usd}</span></p><p className="mt-1 text-muted-foreground">失败码：{invocation.failure_code ?? '—'} · 安全摘要：{invocation.safe_result_digest ?? '—'}</p></li>)}</ul>}</section>
    </section>
  </div>
}
