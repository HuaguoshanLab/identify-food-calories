import { zodResolver } from '@hookform/resolvers/zod'
import { useRef, useState } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'

import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { AlertDialog, AlertDialogContent } from '@/components/ui/AlertDialog'

import {
  CatalogApiError,
  type CatalogDraft,
  type CatalogDraftFormValues,
  catalogDraftFormSchema,
  createCatalogDraft,
  patchCatalogDraft,
} from './api'

type CatalogDraftPageProps = Readonly<{
  accessToken: string | undefined
  onSessionExpired: () => void
}>

const initialValues: CatalogDraftFormValues = {
  canonical_name: '', aliases: '', energy_kcal_per_100g: '', protein_g_per_100g: '', fat_g_per_100g: '', carbohydrate_g_per_100g: '',
  source_name: '', source_url: '', authorization_status: 'pending', reason: '',
}

function FieldPreview({ label, value }: Readonly<{ label: string, value: string | number }>) {
  return <div className="grid grid-cols-[9rem_1fr] gap-4 border-b py-2 text-sm"><dt className="text-muted-foreground">{label}</dt><dd>{value}</dd></div>
}

function ServerConfirmedDraft({ draft }: Readonly<{ draft: CatalogDraft }>) {
  return <section aria-label="服务器确认的草稿字段" className="rounded-lg border bg-card p-4">
    <h2 className="text-xl font-semibold">服务器确认的草稿</h2>
    <p className="mt-2 text-sm text-muted-foreground">仅显示公开目录字段；原始 JSON 和敏感数据不会进入管理界面。</p>
    <dl className="mt-4"><FieldPreview label="菜品名称" value={draft.canonical_name} /><FieldPreview label="别名" value={draft.aliases.join('、')} /><FieldPreview label="每 100g 能量" value={draft.energy_kcal_per_100g} /><FieldPreview label="来源" value={draft.source_name} /><FieldPreview label="授权状态" value={draft.authorization_status} /></dl>
  </section>
}

function UnauthorizedPage() {
  return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">无后台访问权限</h1><p className="mt-4 text-base">你的当前账号没有管理权限。请使用管理员账号登录。</p></main>
}

export function CatalogDraftPage({ accessToken, onSessionExpired }: CatalogDraftPageProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [draft, setDraft] = useState<CatalogDraft>()
  const [error, setError] = useState('')
  const [securityState, setSecurityState] = useState<'expired' | 'forbidden'>()
  const [submitting, setSubmitting] = useState(false)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const form = useForm<CatalogDraftFormValues>({ defaultValues: initialValues, resolver: zodResolver(catalogDraftFormSchema) })

  if (securityState === 'forbidden') return <UnauthorizedPage />
  if (securityState === 'expired' || !accessToken) return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">登录已失效，请重新登录。</h1></main>
  const token = accessToken

  async function confirm() {
    setSubmitting(true)
    setError('')
    try {
      const idempotencyKey = crypto.randomUUID()
      const next = draft
        ? await patchCatalogDraft(token, draft, form.getValues(), idempotencyKey)
        : await createCatalogDraft(token, form.getValues(), idempotencyKey)
      setDraft(next)
      setDialogOpen(false)
    } catch (requestError) {
      if (requestError instanceof CatalogApiError && requestError.status === 401) {
        onSessionExpired()
        setSecurityState('expired')
      } else if (requestError instanceof CatalogApiError && requestError.status === 403) {
        setSecurityState('forbidden')
      } else if (requestError instanceof CatalogApiError && requestError.status === 409) {
        setDialogOpen(false)
        setError('此草稿已被其他管理员更新。请查看最新差异后重新确认。')
      } else {
        setError('暂时无法保存目录草稿，请稍后重试。')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="mx-auto max-w-5xl space-y-6 p-8"><header><h1 className="text-[28px] font-semibold leading-9">营养目录草稿</h1><p className="mt-2 text-base text-muted-foreground">创建或编辑草稿前先核对字段；后端仍是唯一授权与审计真相。</p></header>
    {error ? <p aria-live="polite" className="rounded-md border p-4 text-sm" role="alert">{error}</p> : null}
    {draft ? <><p aria-live="polite">草稿已保存，当前 revision 为 {draft.revision}。</p><ServerConfirmedDraft draft={draft} /></> : null}
    <form className="grid gap-4 rounded-lg border bg-card p-6 md:grid-cols-2" onSubmit={form.handleSubmit(() => setDialogOpen(true), () => setError('请检查表单中标记的字段。'))}>
      <FormField error={form.formState.errors.canonical_name?.message} label="菜品名称" registration={form.register('canonical_name')} />
      <FormField error={form.formState.errors.aliases?.message} label="别名" registration={form.register('aliases')} />
      <FormField error={form.formState.errors.energy_kcal_per_100g?.message} label="每 100g 能量（kcal）" registration={form.register('energy_kcal_per_100g')} type="number" />
      <FormField error={form.formState.errors.protein_g_per_100g?.message} label="每 100g 蛋白质（g）" registration={form.register('protein_g_per_100g')} type="number" />
      <FormField error={form.formState.errors.fat_g_per_100g?.message} label="每 100g 脂肪（g）" registration={form.register('fat_g_per_100g')} type="number" />
      <FormField error={form.formState.errors.carbohydrate_g_per_100g?.message} label="每 100g 碳水（g）" registration={form.register('carbohydrate_g_per_100g')} type="number" />
      <FormField error={form.formState.errors.source_name?.message} label="来源名称" registration={form.register('source_name')} />
      <FormField error={form.formState.errors.source_url?.message} label="来源链接" registration={form.register('source_url')} type="url" />
      <label className="grid gap-2 text-sm" htmlFor="authorization-status">授权状态<select className="h-10 rounded-md border bg-background px-3" id="authorization-status" {...form.register('authorization_status')}><option value="pending">待确认</option><option value="authorized">已授权</option><option value="revoked">已撤销</option></select></label>
      <div className="md:col-span-2"><FormField error={form.formState.errors.reason?.message} label="变更原因" registration={form.register('reason')} /></div>
      <div className="md:col-span-2"><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground" type="submit">预览并确认</button></div>
    </form>
    <AlertDialog.Root onOpenChange={setDialogOpen} open={dialogOpen}><AlertDialogContent aria-labelledby="catalog-dialog-title" initialFocus={cancelRef}><AlertDialog.Title className="text-xl font-semibold" id="catalog-dialog-title">确认{draft ? '更新' : '创建'}营养目录草稿？</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-muted-foreground">请核对可读字段和变更原因。确认后会由后端执行 RBAC、revision 与审计校验。</AlertDialog.Description><dl className="mt-4"><FieldPreview label="菜品名称" value={form.getValues('canonical_name')} /><FieldPreview label="授权状态" value={form.getValues('authorization_status')} /><FieldPreview label="变更原因" value={form.getValues('reason')} /></dl><div className="mt-6 flex justify-end gap-3"><AlertDialog.Close className="h-10 rounded-md border px-4" ref={cancelRef} type="button">取消</AlertDialog.Close><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={submitting} onClick={() => void confirm()} type="button">{submitting ? '正在提交…' : `确认${draft ? '更新' : '创建'}草稿`}</button></div></AlertDialogContent></AlertDialog.Root>
  </main>
}

export function AdminCatalogDraftPage() {
  const { accessToken, clearSession } = useAdminAuth()
  return <CatalogDraftPage accessToken={accessToken} onSessionExpired={clearSession} />
}

function FormField({ error, label, registration, type = 'text' }: Readonly<{ error: string | undefined, label: string, registration: UseFormRegisterReturn, type?: string }>) {
  const id = `catalog-${registration.name.replaceAll('_', '-')}`
  const errorId = `${id}-error`
  return <label className="grid gap-2 text-sm" htmlFor={id}>{label}<input aria-describedby={error ? errorId : undefined} aria-invalid={Boolean(error)} className="h-10 rounded-md border bg-background px-3" id={id} step={type === 'number' ? 'any' : undefined} type={type} {...registration} />{error ? <span className="text-sm" id={errorId} role="alert">{error}</span> : null}</label>
}
