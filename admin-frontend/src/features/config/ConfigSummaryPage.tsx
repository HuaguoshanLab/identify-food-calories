import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'

import { AlertDialog, AlertDialogContent } from '@/components/ui/AlertDialog'
import { useAdminAuth } from '@/auth/AdminAuthProvider'

import {
  RuntimeConfigApiError,
  type ModelService,
  type RuntimeConfig,
  type RuntimeConfigFormValues,
  readRuntimeConfig,
  readModelServices,
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

const capabilityCopy = {
  text_reasoning: { title: '文字饮食理解', description: '理解用户输入的餐食文字、修改要求，并生成受约束的周复盘建议。营养数值不由模型决定。' },
  image_understanding: { title: '食物图片识别', description: '识别图片中的菜品、可见份量和置信度。识别结果仍要经过营养目录查询与确定性计算。' },
  food_similarity: { title: '相似菜品检索', description: '把单个规范化菜名转换成向量，辅助在营养目录中寻找候选菜品，不生成营养数值。' },
} as const

function ServiceCard({ service, config }: Readonly<{ service: ModelService, config?: RuntimeConfig }>) {
  const copy = capabilityCopy[service.capability]
  return <article className="rounded-lg border bg-card p-5" aria-label={copy.title}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-xl font-semibold">{copy.title}</h2><p className="mt-1 text-sm text-muted-foreground">{copy.description}</p></div>
      <span className="rounded-full border px-3 py-1 text-sm">{service.enabled && (service.capability !== 'text_reasoning' || config?.enabled) ? '已启用' : '未启用'}</span>
    </div>
    <dl className="mt-5">
      <Field label="模型服务商" value={service.provider_label} />
      <Field label="使用模型" value={service.model_label} />
      <Field label="单次最长等待" value={`${service.timeout_seconds} 秒`} />
      {service.output_token_cap ? <Field label="单次最大输出" value={`${service.output_token_cap} token`} /> : null}
      {service.pixel_cap ? <Field label="最大图片像素" value={service.pixel_cap.toLocaleString('zh-CN')} /> : null}
      {service.batch_cap ? <Field label="单批菜名上限" value={`${service.batch_cap} 条`} /> : null}
      {service.vector_dimension ? <Field label="向量维度" value={service.vector_dimension} /> : null}
    </dl>
    <p className="mt-4 text-xs text-muted-foreground">{service.configuration_source === 'admin_policy' ? '运行策略可在本页修改；密钥和接口地址仍由服务端环境管理。' : '此服务由服务端环境配置，本页仅展示安全摘要，不提供密钥或接口地址。'}</p>
    {service.capability === 'text_reasoning' && config ? <div className="mt-4 rounded-md bg-muted p-4 text-sm">
      <p className="font-medium">当前运行策略：第 {config.version} 版</p>
      <p className="mt-1 text-muted-foreground">费用估算单价：输入 ${config.input_usd_per_m} / 百万 token，输出 ${config.output_usd_per_m} / 百万 token。</p>
      <p className="mt-1 text-muted-foreground">预算配置值：单次 ${config.single_call_cap_usd}，周期 ${config.period_cap_usd}。当前代码尚未实现完整的文本模型周期扣费账本。</p>
    </div> : null}
  </article>
}

export function RuntimeConfigSummaryPage({ accessToken, onSessionExpired }: RuntimeConfigSummaryPageProps) {
  const [config, setConfig] = useState<RuntimeConfig>()
  const [services, setServices] = useState<ModelService[]>([])
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
    void Promise.all([readModelServices(accessToken), readRuntimeConfig(accessToken).catch((requestError: unknown) => {
      if (requestError instanceof RuntimeConfigApiError && requestError.status === 404) return undefined
      throw requestError
    })]).then(([inventory, next]) => {
      if (!active) return
      setServices(inventory.services)
      setConfig(next)
      if (next) form.reset(toFormValues(next))
      setState('ready')
    }).catch((requestError: unknown) => {
      if (!active) return
      if (secureFailure(requestError)) return
      setError('暂时无法读取模型服务配置，请稍后重试。')
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

  async function submit(values: RuntimeConfigFormValues) {
    if (!token) return
    const budgetFields = [
      values.single_call_cap_usd,
      values.period_cap_usd,
      values.input_usd_per_m,
      values.output_usd_per_m,
    ]
    if (budgetFields.some((value) => !Number.isFinite(Number(value)) || Number(value) <= 0)) {
      setError('所有预算与价格必须为正数，配置未保存。')
      return
    }
    if (!config && !values.enabled) {
      setError('创建首个运行配置时必须启用未来调用策略。')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const next = await saveRuntimeConfig(token, values, crypto.randomUUID(), config?.version ?? 0)
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
      <header><h1 className="text-[28px] font-semibold">模型服务配置</h1><p className="mt-2 text-sm text-muted-foreground">查看系统使用的三类 AI 服务。这里只展示可审计的安全配置，不显示密钥、接口地址或模型原始内容。</p></header>
      <section className="grid gap-4" aria-label="模型服务列表">{services.map((service) => <ServiceCard config={service.capability === 'text_reasoning' ? config : undefined} key={service.capability} service={service} />)}</section>
      {!config ? <section className="rounded-lg border bg-card p-5"><h2 className="text-xl font-semibold">文字模型尚无运行策略</h2><p className="mt-2 text-muted-foreground">创建首个策略后，新的文字分析任务才能进入模型调用流程。</p></section> : null}
      <button className="h-10 rounded-md bg-primary px-4 text-primary-foreground" onClick={openDialog} type="button">修改文字模型设置</button>
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
      <div className="mt-6 flex justify-end gap-3"><AlertDialog.Close className="h-10 rounded-md border px-4" ref={cancelRef} type="button">取消</AlertDialog.Close><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={submitting} onClick={form.handleSubmit((values) => void submit(values))} type="button">{submitting ? '正在保存…' : '确认保存未来配置'}</button></div>
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
