import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'

import { AlertDialog, AlertDialogContent } from '@/components/ui/AlertDialog'
import { useAdminAuth } from '@/auth/AdminAuthProvider'

import {
  RuntimeConfigApiError,
  type RuntimeConfig,
  type RuntimeConfigFormValues,
  readRuntimeConfig,
  runtimeConfigFormSchema,
  saveRuntimeConfig,
} from './api'

type RuntimeConfigSummaryPageProps = Readonly<{
  accessToken: string | undefined
  onSessionExpired: () => void
}>

const emptyValues: RuntimeConfigFormValues = {
  provider: 'deepseek', model_alias: 'deepseek-v4-flash', enabled: true,
  single_call_cap_usd: '0', period_cap_usd: '0', input_usd_per_m: '0', output_usd_per_m: '0', reason: '',
}

function toFormValues(config: RuntimeConfig): RuntimeConfigFormValues {
  return {
    provider: config.provider, model_alias: config.model_alias, enabled: config.enabled,
    single_call_cap_usd: config.single_call_cap_usd, period_cap_usd: config.period_cap_usd,
    input_usd_per_m: config.input_usd_per_m, output_usd_per_m: config.output_usd_per_m, reason: '',
  }
}

function ForbiddenPage() {
  return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">无后台访问权限</h1><p className="mt-4">你的当前账号没有管理权限。请使用管理员账号登录。</p></main>
}

function Field({ label, value }: Readonly<{ label: string, value: string | number }>) {
  return <div className="grid grid-cols-[12rem_1fr] gap-4 border-b py-2 text-sm"><dt className="text-muted-foreground">{label}</dt><dd className="admin-numeric">{value}</dd></div>
}

function ConfigDetails({ config }: Readonly<{ config: RuntimeConfig }>) {
  return <section aria-label="当前运行配置" className="rounded-lg border bg-card p-5">
    <h1 className="text-[28px] font-semibold leading-9">配置版本 v{config.version}</h1>
    <p className="mt-2 text-sm text-muted-foreground">仅显示可审计的非密钥策略。密钥与服务端点只来自服务端环境，永不进入此页面。</p>
    <dl className="mt-5">
      <Field label="Provider" value={config.provider} /><Field label="模型别名" value={config.model_alias} />
      <Field label="状态" value={config.enabled ? '已启用' : '已停用'} /><Field label="单次调用上限（USD）" value={config.single_call_cap_usd} />
      <Field label="周期上限（USD）" value={config.period_cap_usd} /><Field label="输入价格（USD / 百万 token）" value={config.input_usd_per_m} />
      <Field label="输出价格（USD / 百万 token）" value={config.output_usd_per_m} />
    </dl>
  </section>
}

export function RuntimeConfigSummaryPage({ accessToken, onSessionExpired }: RuntimeConfigSummaryPageProps) {
  const [config, setConfig] = useState<RuntimeConfig>()
  const [state, setState] = useState<'loading' | 'ready' | 'forbidden' | 'expired' | 'empty'>('loading')
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const mainRef = useRef<HTMLElement>(null)
  const form = useForm<RuntimeConfigFormValues>({ defaultValues: emptyValues, resolver: zodResolver(runtimeConfigFormSchema) })

  function secureFailure(requestError: unknown) {
    if (!(requestError instanceof RuntimeConfigApiError)) return false
    if (requestError.status === 401) {
      onSessionExpired()
      setConfig(undefined)
      setState('expired')
      return true
    }
    if (requestError.status === 403) {
      onSessionExpired()
      setConfig(undefined)
      setState('forbidden')
      return true
    }
    return false
  }

  useEffect(() => {
    let active = true
    if (!accessToken) {
      setState('expired')
      return () => { active = false }
    }
    void readRuntimeConfig(accessToken).then((next) => {
      if (!active) return
      setConfig(next)
      form.reset(toFormValues(next))
      setState('ready')
    }).catch((requestError: unknown) => {
      if (!active) return
      if (secureFailure(requestError)) return
      if (requestError instanceof RuntimeConfigApiError && requestError.status === 404) {
        setState('empty')
        return
      }
      setError('暂时无法读取当前运行配置，请稍后重试。')
      setState('empty')
    })
    return () => { active = false }
  // The token is runtime-only; changing it requires a fresh RBAC-backed read.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken])

  if (state === 'forbidden') return <ForbiddenPage />
  if (state === 'expired') return <main className="mx-auto max-w-2xl p-8"><h1 className="text-[28px] font-semibold leading-9">登录已失效，请重新登录。</h1></main>
  if (state === 'loading') return <main aria-busy="true" className="admin-runtime-root">正在读取当前运行配置…</main>
  const token = accessToken

  function openDialog() {
    setError('')
    setDialogOpen(true)
  }

  async function submit() {
    if (!token || !config) return
    setSubmitting(true)
    setError('')
    try {
      const next = await saveRuntimeConfig(token, form.getValues(), crypto.randomUUID(), config.version)
      setConfig(next)
      form.reset(toFormValues(next))
      setDialogOpen(false)
    } catch (requestError) {
      if (secureFailure(requestError)) setDialogOpen(false)
      else if (requestError instanceof RuntimeConfigApiError && requestError.status === 409) {
        setError('配置已被其他管理员更新；你的编辑仍保留，请重新核对后再确认。')
      } else setError('暂时无法保存未来运行配置，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return <>
    <a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:p-3" href="#runtime-config-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a>
    <main id="runtime-config-main" ref={mainRef} tabIndex={-1} className="mx-auto max-w-5xl space-y-6 p-8">
      {error ? <p aria-live="polite" className="rounded-md border p-4 text-sm" role="alert">{error}</p> : null}
      {config ? <ConfigDetails config={config} /> : <section className="rounded-lg border bg-card p-5"><h1 className="text-[28px] font-semibold">尚无运行配置</h1><p className="mt-2 text-muted-foreground">尚未写入可调用策略；可在确认后创建未来使用的非密钥版本。</p></section>}
      <button className="h-10 rounded-md bg-primary px-4 text-primary-foreground" onClick={openDialog} type="button">变更未来配置</button>
    </main>
    <AlertDialog.Root onOpenChange={setDialogOpen} open={dialogOpen}><AlertDialogContent aria-labelledby="runtime-config-dialog-title" initialFocus={cancelRef}>
      <AlertDialog.Title className="text-xl font-semibold" id="runtime-config-dialog-title">确认变更未来运行配置？</AlertDialog.Title>
      <AlertDialog.Description className="mt-2 text-sm text-muted-foreground">此操作只创建未来调用使用的新策略版本；不会暴露密钥、端点或影响已经准入的运行。</AlertDialog.Description>
      <fieldset className="mt-4 grid gap-3 rounded-md border p-4"><legend className="px-1 text-sm font-medium">未来调用策略</legend>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...form.register('enabled')} />启用新的运行配置</label>
        <ConfigNumberField label="单次调用上限（USD）" registration={form.register('single_call_cap_usd')} />
        <ConfigNumberField label="周期上限（USD）" registration={form.register('period_cap_usd')} />
        <ConfigNumberField label="输入价格（USD / 百万 token）" registration={form.register('input_usd_per_m')} />
        <ConfigNumberField label="输出价格（USD / 百万 token）" registration={form.register('output_usd_per_m')} />
      </fieldset>
      <label className="mt-4 grid gap-2 text-sm" htmlFor="runtime-config-reason">变更原因<textarea className="min-h-24 rounded-md border bg-background p-3" id="runtime-config-reason" {...form.register('reason')} /></label>
      {form.formState.errors.reason?.message ? <p className="mt-1 text-sm" role="alert">{form.formState.errors.reason.message}</p> : null}
      <div className="mt-6 flex justify-end gap-3"><AlertDialog.Close className="h-10 rounded-md border px-4" ref={cancelRef} type="button">取消</AlertDialog.Close><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={submitting} onClick={form.handleSubmit(() => void submit())} type="button">{submitting ? '正在保存…' : '确认保存未来配置'}</button></div>
    </AlertDialogContent></AlertDialog.Root>
  </>
}

export function AdminRuntimeConfigSummaryPage() {
  const { accessToken, clearSession } = useAdminAuth()
  return <RuntimeConfigSummaryPage accessToken={accessToken} onSessionExpired={clearSession} />
}

function ConfigNumberField({ label, registration }: Readonly<{ label: string, registration: UseFormRegisterReturn }>) {
  const id = `runtime-config-${registration.name.replaceAll('_', '-')}`
  return <label className="grid gap-1 text-sm" htmlFor={id}>{label}<input className="h-10 rounded-md border bg-background px-3" id={id} inputMode="decimal" type="text" {...registration} /></label>
}
