import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'

import { CatalogApiError, type CatalogLifecyclePreview, lifecycleReasonSchema, readCatalogLifecyclePreview, submitCatalogLifecycleCommand } from './api'

const fieldLabels = { canonical_name: '菜品名称', aliases: '别名', energy_kcal_per_100g: '能量', protein_g_per_100g: '蛋白质', fat_g_per_100g: '脂肪', carbohydrate_g_per_100g: '碳水', source_name: '来源', source_url: '来源链接', authorization_status: '授权状态' }

export function CatalogRowLifecycle({ accessToken, draftId, action, onClose, onSuccess, onSecurityError, onBusyChange }: Readonly<{
  accessToken: string; draftId: string; action: 'review' | 'publish'; onClose: () => void
  onSuccess: (message: string) => void; onSecurityError: (error: unknown) => boolean; onBusyChange: (busy: boolean) => void
}>) {
  const [preview, setPreview] = useState<CatalogLifecyclePreview>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [reload, setReload] = useState(0)
  const inFlight = useRef(false)
  const command = useRef<{ fingerprint: string; key: string } | undefined>(undefined)
  const security = useRef(onSecurityError)
  security.current = onSecurityError
  const form = useForm<{ reason: string }>({ resolver: zodResolver(lifecycleReasonSchema), defaultValues: { reason: '' } })

  useEffect(() => {
    let active = true
    setLoading(true)
    setPreview(undefined)
    setError('')
    void readCatalogLifecyclePreview(accessToken, draftId).then((result) => {
      if (active) setPreview(result)
    }).catch((cause: unknown) => {
      if (active && !security.current(cause)) setError('无法读取当前草稿，请重试。')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [accessToken, draftId, reload])

  const alreadyPublished = action === 'publish' && preview?.publication?.draft_revision === preview?.draft.revision
  const unauthorized = action === 'publish' && preview && preview.draft.authorization_status !== 'authorized'

  async function submit({ reason }: { reason: string }) {
    if (!preview || loading || inFlight.current || alreadyPublished || unauthorized) return
    inFlight.current = true
    setSubmitting(true)
    onBusyChange(true)
    setError('')
    // A lost response must not create a second command when the same input is retried.
    const fingerprint = JSON.stringify([draftId, preview.draft.revision, action, reason])
    if (command.current?.fingerprint !== fingerprint) command.current = { fingerprint, key: crypto.randomUUID() }
    try {
      const result = await submitCatalogLifecycleCommand(accessToken, preview, action, reason, command.current.key)
      onSuccess(`“${preview.draft.canonical_name}”${action === 'review' ? '已审核草稿' : '已发布版本'} v${result.draft_revision}，操作已记录。`)
    } catch (cause) {
      if (onSecurityError(cause)) return
      if (cause instanceof CatalogApiError && cause.status === 409) {
        setError(action === 'review' ? '审核未完成：当前版本可能已审核或已发生变更。请核对状态，已审核的草稿可直接发布。' : '发布未完成：请确认当前草稿已授权、已审核且未被修改。')
      } else {
        setError('未能确认操作结果。可重试同一操作，请勿重复创建版本。')
      }
    } finally {
      inFlight.current = false
      setSubmitting(false)
      onBusyChange(false)
    }
  }

  return <section aria-label={action === 'review' ? '审核草稿确认' : '发布版本确认'} className="space-y-4 whitespace-normal">
    {preview && <h3 className="font-medium">{preview.draft.canonical_name} · 草稿 v{preview.draft.revision}</h3>}
    {loading && <p role="status">正在核对当前草稿…</p>}
    {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
    {preview && <>
      <p className="text-sm text-muted-foreground">{action === 'review' ? '审核后可继续发布；审核本身不会让客户端生效。' : preview.impact.description}</p>
      {alreadyPublished && <p role="status">{preview.publication?.eligibility === 'eligible' ? '当前草稿版本已经发布，无需重复发布。' : '此版本已发布但已失格；请编辑为新草稿后重新审核发布。'}</p>}
      {unauthorized && <p role="alert" className="text-sm text-amber-800">请先编辑菜品，将授权状态设为“已授权”并保存、审核。</p>}
      <details className="text-xs text-muted-foreground"><summary className="w-fit cursor-pointer">查看字段差异（可选）</summary><dl className="mt-2 grid gap-2">{preview.field_diffs.map((diff) => <div className="flex flex-wrap gap-2 break-all" key={diff.field}><dt>{fieldLabels[diff.field]}</dt><dd>{diff.before ?? '—'} → {diff.after ?? '—'}</dd></div>)}</dl></details>
      {!alreadyPublished && !unauthorized && <form className="grid gap-3" onSubmit={form.handleSubmit(submit)}>
        <div className="min-w-0"><label className="mb-2 block text-sm" htmlFor={`row-reason-${draftId}`}>操作原因</label><input className="h-9 w-full rounded-md border bg-card px-3 text-sm" id={`row-reason-${draftId}`} placeholder="填写操作原因（写入审计记录）" disabled={submitting} aria-invalid={Boolean(form.formState.errors.reason)} aria-describedby={form.formState.errors.reason ? `row-error-${draftId}` : undefined} {...form.register('reason')} />{form.formState.errors.reason && <p className="mt-1 text-xs text-red-700" id={`row-error-${draftId}`} role="alert">{form.formState.errors.reason.message}</p>}</div>
        <button className="h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50" disabled={submitting || loading} type="submit">{submitting ? '正在提交…' : action === 'review' ? '确认审核草稿' : '确认发布版本'}</button>
      </form>}
    </>}
    <div className="flex gap-4 text-sm"><button className="text-muted-foreground hover:underline disabled:opacity-50" disabled={submitting} onClick={onClose} type="button">取消</button>{!loading && <button className="text-blue-600 hover:underline disabled:opacity-50" disabled={submitting} onClick={() => setReload((value) => value + 1)} type="button">重新核对状态</button>}</div>
  </section>
}
