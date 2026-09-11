import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'

import { AuditTimeline } from '@/features/audit/AuditTimeline'
import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { AlertDialog, AlertDialogContent } from '@/components/ui/AlertDialog'

import {
  CatalogApiError,
  type CatalogLifecycleAction,
  type CatalogEmbeddingStatus,
  type CatalogLifecyclePreview,
  lifecycleReasonSchema,
  listCatalogAuditEvents,
  readCatalogEmbeddingStatus,
  readCatalogLifecyclePreview,
  retryCatalogEmbeddingJobs,
  submitCatalogLifecycleCommand,
} from './api'

const fieldLabels = {
  canonical_name: '菜品名称', aliases: '别名', energy_kcal_per_100g: '每 100g 能量', protein_g_per_100g: '每 100g 蛋白质',
  fat_g_per_100g: '每 100g 脂肪', carbohydrate_g_per_100g: '每 100g 碳水', source_name: '来源名称',
  source_url: '来源链接', authorization_status: '授权状态',
} as const

const actionCopy = {
  review: { button: '审核目录草稿', title: '审核营养目录草稿？', confirm: '确认审核草稿', consequence: '审核会冻结当前草稿 revision 的证据，供后续发布核对。' },
  publish: { button: '发布营养目录版本', title: '发布营养目录版本？', confirm: '确认发布版本', consequence: '发布后，新分析和新餐单将使用此不可变版本；历史已确认餐食不会被改写。' },
  disqualify: { button: '立即失格', title: '确认立即失格？', confirm: '确认立即失格', consequence: '仅阻止后续分析和新餐单使用该条目，不重算或删除历史餐食快照。' },
} as const

type LifecycleForm = { reason: string }
type DialogAction = CatalogLifecycleAction | 'retry_embeddings'

const embeddingStatusCopy = {
  pending: '等待处理', processing: '正在处理', partial_failure: '部分失败', failed: '处理失败', ready: '已就绪',
} as const

function UnauthorizedPage() {
  return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">无后台访问权限</h1><p className="mt-4 text-base">你的当前账号没有管理权限。请使用管理员账号登录。</p></main>
}

function FieldDiffPreview({ preview }: Readonly<{ preview: CatalogLifecyclePreview }>) {
  return <section aria-label="发布前字段差异" className="rounded-lg border bg-card p-4">
    <h2 className="text-xl font-semibold">发布前字段差异</h2>
    <p className="mt-1 text-sm text-muted-foreground">由服务端基于当前目录状态计算，浏览器不生成可信 diff。</p>
    <div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><caption className="sr-only">当前值与拟发布值的字段差异</caption><thead><tr className="border-b"><th className="p-2" scope="col">字段</th><th className="p-2" scope="col">当前值</th><th className="p-2" scope="col">拟发布值</th><th className="p-2" scope="col">变更</th></tr></thead><tbody>{preview.field_diffs.map((diff) => <tr className="border-b" key={diff.field}><th className="p-2 font-normal" scope="row">{fieldLabels[diff.field]}</th><td className="p-2">{diff.before ?? '—'}</td><td className="p-2">{diff.after ?? '—'}</td><td className="p-2">{diff.change === 'added' ? '已新增' : diff.change === 'removed' ? '已移除' : diff.change === 'unchanged' ? '无变更' : '已修改'}</td></tr>)}</tbody></table></div>
    <p className="mt-4 text-sm font-medium">受影响菜品数量：{preview.impact.affected_catalog_items}</p>
    <p className="mt-1 text-sm text-muted-foreground">{preview.impact.description}</p>
  </section>
}

function EmbeddingStatusPanel({ status, onRetry, onRefresh, disabled }: Readonly<{ status: CatalogEmbeddingStatus, onRetry: () => void, onRefresh: () => void, disabled: boolean }>) {
  const retryableCount = status.jobs.filter((job) => job.status === 'failed' && job.attempt_count < job.max_attempts).length
  return <section aria-label="嵌入构建状态" className="rounded-lg border bg-card p-4">
    <h2 className="text-xl font-semibold">嵌入构建状态</h2>
    <p className="mt-1 text-sm text-muted-foreground">{embeddingStatusCopy[status.status]}：等待 {status.pending_count}，处理中 {status.processing_count}，失败 {status.failed_count}，完成 {status.completed_count}。</p>
    <div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><caption className="sr-only">嵌入作业安全状态</caption><thead><tr className="border-b"><th className="p-2" scope="col">作业状态</th><th className="p-2" scope="col">尝试次数</th><th className="p-2" scope="col">安全失败码</th></tr></thead><tbody>{status.jobs.map((job) => <tr className="border-b" key={job.id}><td className="p-2">{job.status === 'leased' ? '处理中' : job.status === 'completed' ? '已完成' : job.status === 'failed' ? '失败' : '等待处理'}</td><td className="p-2">{job.attempt_count} / {job.max_attempts}</td><td className="p-2">{job.last_error_code ?? '—'}</td></tr>)}</tbody></table></div>
    <div className="mt-4 flex flex-wrap gap-3"><button className="h-10 rounded-md border px-4 disabled:opacity-50" disabled={disabled} onClick={onRefresh} type="button">刷新嵌入构建状态</button>{retryableCount ? <button className="h-10 rounded-md border px-4 disabled:opacity-50" disabled={disabled} onClick={onRetry} type="button">重试 {retryableCount} 个可恢复任务</button> : null}</div>
  </section>
}

export function CatalogLifecyclePage({ accessToken, draftId, onSessionExpired }: Readonly<{ accessToken: string | undefined, draftId: string, onSessionExpired: () => void }>) {
  const [preview, setPreview] = useState<CatalogLifecyclePreview>()
  const [embeddingStatus, setEmbeddingStatus] = useState<CatalogEmbeddingStatus>()
  const [events, setEvents] = useState<Awaited<ReturnType<typeof listCatalogAuditEvents>>['items']>([])
  const [securityState, setSecurityState] = useState<'expired' | 'forbidden'>()
  const [notice, setNotice] = useState('')
  const [dialogAction, setDialogAction] = useState<DialogAction>()
  const [submitting, setSubmitting] = useState(false)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const form = useForm<LifecycleForm>({ defaultValues: { reason: '' }, resolver: zodResolver(lifecycleReasonSchema) })

  const handleSecurityError = (error: unknown) => {
    if (!(error instanceof CatalogApiError)) return false
    if (error.status === 401) {
      onSessionExpired()
      setSecurityState('expired')
      return true
    }
    if (error.status === 403) {
      setSecurityState('forbidden')
      return true
    }
    return false
  }

  async function loadProjection() {
    if (!accessToken) return
    try {
      // Authorize and validate the projection first, so a stale/ordinary session never reads audit evidence.
      const nextPreview = await readCatalogLifecyclePreview(accessToken, draftId)
      const audit = await listCatalogAuditEvents(accessToken)
      setPreview(nextPreview)
      setEvents(audit.items.filter((event) => event.object_id === draftId || event.object_id === nextPreview.publication?.id))
      if (nextPreview.publication) {
        try {
          setEmbeddingStatus(await readCatalogEmbeddingStatus(accessToken, nextPreview.publication.id))
        } catch (error) {
          setEmbeddingStatus(undefined)
          if (!handleSecurityError(error)) setNotice('暂时无法加载嵌入构建状态，请稍后重试。')
        }
      } else setEmbeddingStatus(undefined)
    } catch (error) {
      if (!handleSecurityError(error)) setNotice('暂时无法加载目录生命周期信息，请稍后重试。')
    }
  }

  useEffect(() => { void loadProjection() }, [accessToken, draftId])
  useEffect(() => {
    if (!dialogAction) return
    // Base UI owns the trap; explicitly restore the cancel-first safety contract once it opens.
    const frame = requestAnimationFrame(() => cancelRef.current?.focus())
    return () => cancelAnimationFrame(frame)
  }, [dialogAction])

  if (securityState === 'forbidden') return <UnauthorizedPage />
  if (securityState === 'expired' || !accessToken) return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">登录已失效，请重新登录。</h1></main>
  const token = accessToken
  const selectedCopy = dialogAction && dialogAction !== 'retry_embeddings' ? actionCopy[dialogAction] : undefined
  const canDisqualify = preview?.publication?.eligibility === 'eligible'

  async function submit(action: CatalogLifecycleAction) {
    if (!preview) return
    setSubmitting(true)
    setNotice('')
    try {
      const publication = await submitCatalogLifecycleCommand(token, preview, action, form.getValues('reason'), crypto.randomUUID())
      setDialogAction(undefined)
      form.reset()
      await loadProjection()
      setNotice(action === 'publish' ? `已发布版本 v${publication.draft_revision}，操作已记录。` : action === 'disqualify' ? '已立即失格，操作已记录。' : `已审核草稿 v${publication.draft_revision}，操作已记录。`)
    } catch (error) {
      if (handleSecurityError(error)) {
        setDialogAction(undefined)
      } else if (error instanceof CatalogApiError && error.status === 409) {
        await loadProjection()
        setNotice('此草稿已被其他管理员更新。请查看最新差异后重新确认。')
      } else {
        setNotice('暂时无法执行目录生命周期操作，请稍后重试。')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function submitEmbeddingRetry() {
    if (!preview?.publication || submitting) return
    setSubmitting(true)
    setNotice('')
    try {
      const result = await retryCatalogEmbeddingJobs(token, preview.publication.id, form.getValues('reason'), crypto.randomUUID())
      setEmbeddingStatus(result)
      setDialogAction(undefined)
      form.reset()
      setNotice(`已重新排队 ${result.reset_count} 个可恢复任务，操作已记录。`)
    } catch (error) {
      if (handleSecurityError(error)) {
        setDialogAction(undefined)
      } else if (error instanceof CatalogApiError && error.status === 409) {
        await loadProjection()
        setNotice('嵌入任务状态已变化。请查看最新状态后重新确认。')
      } else {
        setNotice('暂时无法重新排队嵌入任务，请稍后重试。')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function refreshEmbeddingStatus() {
    if (!preview?.publication || submitting) return
    try {
      setEmbeddingStatus(await readCatalogEmbeddingStatus(token, preview.publication.id))
    } catch (error) {
      if (!handleSecurityError(error)) setNotice('暂时无法刷新嵌入构建状态，请稍后重试。')
    }
  }

  function submitSelectedLifecycle() {
    if (dialogAction && dialogAction !== 'retry_embeddings') void submit(dialogAction)
  }

  return <main className="mx-auto max-w-6xl space-y-6 p-8"><header><h1 className="text-[28px] font-semibold leading-9">营养目录审核与发布</h1><p className="mt-2 text-base text-muted-foreground">高风险命令始终需要服务端 diff、非空理由与确认；后端 RBAC 是唯一授权真相。</p></header>
    {notice ? <p aria-live="polite" className="rounded-md border p-4 text-sm" role="status">{notice}</p> : null}
    {preview ? <><FieldDiffPreview preview={preview} />{embeddingStatus ? <EmbeddingStatusPanel disabled={submitting} onRefresh={() => void refreshEmbeddingStatus()} onRetry={() => setDialogAction('retry_embeddings')} status={embeddingStatus} /> : null}<section aria-label="目录生命周期操作" className="flex flex-wrap gap-3"><button className="h-10 rounded-md border px-4 disabled:opacity-50" onClick={() => setDialogAction('review')} type="button">{actionCopy.review.button}</button><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" onClick={() => setDialogAction('publish')} type="button">{actionCopy.publish.button}</button><button className="h-10 rounded-md border px-4 disabled:opacity-50" disabled={!canDisqualify} onClick={() => setDialogAction('disqualify')} type="button">{actionCopy.disqualify.button}</button></section><AuditTimeline events={events} /></> : <p aria-live="polite" className="rounded-md border p-4 text-sm">正在读取服务端目录生命周期投影…</p>}
    <AlertDialog.Root onOpenChange={(open) => { if (!open && !submitting) setDialogAction(undefined) }} open={Boolean(dialogAction)}><AlertDialogContent aria-labelledby="catalog-lifecycle-dialog-title" className="max-h-[calc(100dvh-2rem)] max-w-4xl overflow-y-auto" initialFocus={cancelRef}>{dialogAction === 'retry_embeddings' ? <><AlertDialog.Title className="text-xl font-semibold" id="catalog-lifecycle-dialog-title">重新排队可恢复的嵌入任务？</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-muted-foreground">这会以一个 publication 级命令重新排队仍有剩余尝试次数的失败任务；后端会记录理由和审计结果。</AlertDialog.Description><form className="mt-4 grid gap-2" onSubmit={form.handleSubmit(() => void submitEmbeddingRetry())}><label className="text-sm" htmlFor="catalog-lifecycle-reason">变更原因</label><textarea aria-describedby={form.formState.errors.reason ? 'catalog-lifecycle-reason-error' : undefined} aria-invalid={Boolean(form.formState.errors.reason)} className="min-h-24 rounded-md border bg-background p-3" id="catalog-lifecycle-reason" {...form.register('reason')} />{form.formState.errors.reason ? <p id="catalog-lifecycle-reason-error" role="alert">{form.formState.errors.reason.message}</p> : null}<div className="mt-4 flex justify-end gap-3"><AlertDialog.Close className="h-10 rounded-md border px-4" disabled={submitting} ref={cancelRef} type="button">取消</AlertDialog.Close><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={submitting} type="submit">{submitting ? '正在提交…' : '确认重新排队'}</button></div></form></> : selectedCopy ? <><AlertDialog.Title className="text-xl font-semibold" id="catalog-lifecycle-dialog-title">{selectedCopy.title}</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-muted-foreground">{selectedCopy.consequence}</AlertDialog.Description>{preview ? <div className="mt-4"><FieldDiffPreview preview={preview} /></div> : null}<form className="mt-4 grid gap-2" onSubmit={form.handleSubmit(submitSelectedLifecycle)}><label className="text-sm" htmlFor="catalog-lifecycle-reason">变更原因</label><textarea aria-describedby={form.formState.errors.reason ? 'catalog-lifecycle-reason-error' : undefined} aria-invalid={Boolean(form.formState.errors.reason)} className="min-h-24 rounded-md border bg-background p-3" id="catalog-lifecycle-reason" {...form.register('reason')} />{form.formState.errors.reason ? <p id="catalog-lifecycle-reason-error" role="alert">{form.formState.errors.reason.message}</p> : null}<div className="mt-4 flex justify-end gap-3"><AlertDialog.Close className="h-10 rounded-md border px-4" disabled={submitting} ref={cancelRef} type="button">取消</AlertDialog.Close><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={submitting} type="submit">{submitting ? '正在提交…' : selectedCopy.confirm}</button></div></form></> : null}</AlertDialogContent></AlertDialog.Root>
  </main>
}

/** Route assembly keeps the lifecycle page on the same runtime-only admin session boundary. */
export function AdminCatalogLifecyclePage() {
  const { draftId } = useParams()
  const { accessToken, clearSession } = useAdminAuth()
  if (!draftId || !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(draftId)) {
    return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">目录草稿不存在</h1><p className="mt-4 text-base">请从已保存草稿进入审核与发布页面。</p></main>
  }
  return <CatalogLifecyclePage accessToken={accessToken} draftId={draftId} onSessionExpired={clearSession} />
}
