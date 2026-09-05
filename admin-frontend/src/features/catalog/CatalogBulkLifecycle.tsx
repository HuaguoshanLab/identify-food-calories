import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'

import { CatalogApiError, type CatalogDraft, type CatalogLifecyclePreview, lifecycleReasonSchema, readCatalogLifecyclePreview, submitCatalogLifecycleCommand } from './api'
import { CatalogDialog } from './CatalogDialog'

type Entry = { draft: CatalogDraft; preview?: CatalogLifecyclePreview; status: 'loading' | 'ready' | 'blocked' | 'running' | 'success' | 'failed'; message: string; key: string }
const labels = { canonical_name: '菜品名称', aliases: '别名', energy_kcal_per_100g: '能量', protein_g_per_100g: '蛋白质', fat_g_per_100g: '脂肪', carbohydrate_g_per_100g: '碳水', source_name: '来源', source_url: '来源链接', authorization_status: '授权状态' }

export function CatalogBulkLifecycle({ accessToken, drafts, action, onClose, onSecurityError, onChanged }: Readonly<{
  accessToken: string; drafts: CatalogDraft[]; action: 'review' | 'publish'
  onClose: () => void; onSecurityError: (error: unknown) => boolean; onChanged: () => void
}>) {
  const [entries, setEntries] = useState<Entry[]>(() => drafts.map(draft => ({ draft, status: 'loading', message: '正在核对…', key: crypto.randomUUID() })))
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [started, setStarted] = useState(false)
  const inFlight = useRef(false)
  const alive = useRef(true)
  const reasonSnapshot = useRef('')
  const security = useRef(onSecurityError)
  security.current = onSecurityError
  const form = useForm<{ reason: string }>({ resolver: zodResolver(lifecycleReasonSchema), defaultValues: { reason: '' } })

  useEffect(() => {
    alive.current = true
    let active = true
    const controller = new AbortController()
    void (async () => {
      for (const draft of drafts) {
        if (!active) break
        let patch: Partial<Entry>
        try {
          const preview = await readCatalogLifecyclePreview(accessToken, draft.id, AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]))
          if (!active) return
          if (preview.draft.id !== draft.id || preview.draft.revision !== draft.revision) {
            patch = { status: 'blocked', message: '草稿已变化，请关闭后刷新列表重新选择。' }
          } else if (action === 'publish' && preview.draft.authorization_status !== 'authorized') {
            patch = { preview, status: 'blocked', message: '未授权：请先编辑、保存并审核。' }
          } else if (preview.publication?.draft_revision === preview.draft.revision) {
            patch = { preview, status: 'blocked', message: preview.publication.eligibility === 'eligible' ? '当前版本已发布，跳过。' : '当前版本已失格，请编辑为新草稿后重新审核发布。' }
          } else {
            patch = { preview, status: 'ready', message: '待确认' }
          }
        } catch (cause) {
          if (!active) return
          if (security.current(cause)) return
          patch = { status: 'blocked', message: '无法核对，请关闭后重新选择重试。' }
        }
        setEntries(current => current.map(entry => entry.draft.id === draft.id ? { ...entry, ...patch } : entry))
      }
      if (active) setLoading(false)
    })()
    return () => { active = false; alive.current = false; controller.abort() }
  }, [accessToken, drafts, action])

  async function submit({ reason }: { reason: string }) {
    if (inFlight.current || loading) return
    inFlight.current = true
    setBusy(true)
    setStarted(true)
    // Freeze both the reason and each command key across uncertain-result retries.
    if (!reasonSnapshot.current) reasonSnapshot.current = reason
    try {
      for (const entry of entries) {
        if (!alive.current) break
        if (!entry.preview || !['ready', 'failed'].includes(entry.status)) continue
        const update = (status: Entry['status'], message: string) => {
          if (alive.current) setEntries(current => current.map(item => item.draft.id === entry.draft.id ? { ...item, status, message } : item))
        }
        update('running', '正在提交…')
        try {
          const result = await submitCatalogLifecycleCommand(accessToken, entry.preview, action, reasonSnapshot.current, entry.key, AbortSignal.timeout(20_000))
          if (result.draft_id !== entry.draft.id || result.draft_revision !== entry.preview.draft.revision) throw new Error('Unexpected command result')
          update('success', `${action === 'review' ? '审核' : '发布'}成功 · v${result.draft_revision} · 已记录审计`)
        } catch (cause) {
          if (!alive.current) break
          if (security.current(cause)) break
          if (cause instanceof CatalogApiError && [404, 409, 422].includes(cause.status)) {
            update('blocked', action === 'review' ? '审核失败：可能已审核、草稿已变化或不存在；请核对，已审核的可直接发布。' : '发布失败：请确认已授权、已审核且草稿未变化。')
          } else {
            update('failed', '结果未确认，可用原操作重试。')
          }
        }
      }
    } finally {
      inFlight.current = false
      if (alive.current) { setBusy(false); onChanged() }
    }
  }

  const success = entries.filter(entry => entry.status === 'success').length
  const blocked = entries.filter(entry => entry.status === 'blocked').length
  const failed = entries.filter(entry => entry.status === 'failed').length
  const pending = entries.filter(entry => ['ready', 'running', 'loading'].includes(entry.status)).length
  const actionable = entries.filter(entry => entry.status === 'ready' || entry.status === 'failed').length
  const title = action === 'review' ? '批量审核' : '批量发布'

  return <CatalogDialog title={title} description={`已选择 ${drafts.length} 条菜品，逐项执行并保留审计记录。`} busy={busy} onClose={onClose} footer={<>
    <button className="h-9 rounded-md border px-4 text-sm disabled:opacity-50" disabled={busy} onClick={onClose} type="button">{started ? '完成' : '取消'}</button>
    <button className="h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50" disabled={loading || busy || !actionable} form="catalog-bulk-form" type="submit">{busy ? '正在执行…' : started ? `重试未确认项（${actionable}）` : `确认${title}（${actionable}）`}</button>
  </>}>
    <form className="space-y-4" id="catalog-bulk-form" onSubmit={form.handleSubmit(submit)}>
      <p className="text-sm text-muted-foreground">{action === 'review' ? '审核不会在客户端生效；完成后仍需批量发布。' : '只发布已授权且已审核的当前草稿；新分析和新餐单使用发布版本，历史已确认餐食不变。'} 部分失败不会撤销已成功的操作。执行时请勿刷新或关闭页面。</p>
      <label className="block text-sm" htmlFor="catalog-bulk-reason">批量操作原因</label>
      <input className="h-9 w-full rounded-md border bg-card px-3 text-sm" id="catalog-bulk-reason" readOnly={started} aria-invalid={Boolean(form.formState.errors.reason)} {...form.register('reason')} placeholder="统一写入每条菜品的审计记录" />
      {form.formState.errors.reason && <p role="alert" className="text-sm text-red-700">{form.formState.errors.reason.message}</p>}
      <p role="status" className="rounded-md bg-muted/40 p-3 text-sm">{loading ? '正在核对所选菜品…' : `成功 ${success} 条 · 跳过/失败 ${blocked} 条 · 结果未确认 ${failed} 条 · 待处理 ${pending} 条`}</p>
      <ul className="divide-y rounded-md border" aria-label="批量操作结果">{entries.map(entry => <li className="space-y-2 p-3 text-sm" key={entry.draft.id}>
        <div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{entry.draft.canonical_name} · v{entry.draft.revision}</span><span className={entry.status === 'success' ? 'text-emerald-700' : ['blocked', 'failed'].includes(entry.status) ? 'text-amber-800' : 'text-muted-foreground'}>{entry.message}</span></div>
        {entry.preview && <details className="text-xs text-muted-foreground"><summary className="w-fit cursor-pointer">查看差异与影响</summary><p className="my-2">{entry.preview.impact.description}</p><dl className="space-y-1">{entry.preview.field_diffs.map(diff => <div className="flex flex-wrap gap-2 break-all" key={diff.field}><dt>{labels[diff.field]}</dt><dd>{diff.before ?? '—'} → {diff.after ?? '—'}</dd></div>)}</dl></details>}
      </li>)}</ul>
    </form>
  </CatalogDialog>
}
