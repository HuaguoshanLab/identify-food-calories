import { z } from 'zod'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { useAdminAuth } from './AdminAuthProvider'

const credentialsSchema = z.object({
  email: z.string().trim().email('请输入有效邮箱地址。').max(320),
  password: z.string().min(12, '密码至少需要 12 个字符。').max(128),
}).strict()

const accessTokenSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal('bearer'),
  expires_in: z.number().int().positive(),
}).strict()

const currentUserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  email_verified_at: z.string().datetime({ offset: true }).nullable(),
  is_active: z.boolean(),
  role: z.string(),
}).strict()

function safeReturnTo(value: string | null) {
  return value?.startsWith('/admin/') && !value.startsWith('//') ? value : '/admin/overview'
}

async function requestJson(path: string, init: RequestInit) {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!response.ok) throw new Error('request failed')
  return response.json()
}

/**
 * Login only establishes a short-lived browser session. The nested route guard
 * probes DB-RBAC before rendering any administrative navigation or data.
 */
export function AdminLoginPage() {
  const { establishSession } = useAdminAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [errors, setErrors] = useState<Partial<Record<'email' | 'password', string>>>({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(formData: FormData) {
    const parsed = credentialsSchema.safeParse({ email: formData.get('email'), password: formData.get('password') })
    if (!parsed.success) {
      const fields = parsed.error.flatten().fieldErrors
      setErrors({ email: fields.email?.[0], password: fields.password?.[0] })
      return
    }
    setErrors({})
    setError('')
    setSubmitting(true)
    try {
      const access = accessTokenSchema.parse(await requestJson('/auth/login', {
        body: JSON.stringify(parsed.data), method: 'POST',
      }))
      const identity = currentUserSchema.parse(await requestJson('/users/me', {
        headers: { Authorization: `Bearer ${access.access_token}` }, method: 'GET',
      }))
      if (!identity.is_active) {
        setError('账号尚不可登录。')
        return
      }
      // `/users/me` proves an active identity only; the guard's DB-RBAC probe owns admin UX.
      establishSession({ accessToken: access.access_token, identity: { id: identity.id } })
      navigate(safeReturnTo(searchParams.get('returnTo')), { replace: true })
    } catch {
      setError('邮箱或密码不正确，或账号尚不可登录。')
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="admin-runtime-root mx-auto grid max-w-md content-center gap-6" aria-labelledby="admin-login-title">
    <header><p className="text-sm text-muted-foreground">饮食健康智能 Agent</p><h1 className="mt-2 text-[28px] font-semibold leading-9" id="admin-login-title">后台登录</h1><p className="mt-2 text-sm text-muted-foreground">请使用已获授权的管理员账号。后台授权始终由服务器确认。</p></header>
    <form className="grid gap-4 rounded-lg border bg-card p-6" noValidate onSubmit={(event) => { event.preventDefault(); void submit(new FormData(event.currentTarget)) }}>
      {error ? <p className="rounded-md border p-3 text-sm" role="alert">{error}</p> : null}
      <label className="grid gap-2 text-sm" htmlFor="admin-login-email">邮箱<input aria-describedby={errors.email ? 'admin-login-email-error' : undefined} aria-invalid={Boolean(errors.email)} autoComplete="email" className="h-10 rounded-md border bg-background px-3" id="admin-login-email" name="email" type="email" /></label>
      {errors.email ? <p id="admin-login-email-error" role="alert" className="text-sm">{errors.email}</p> : null}
      <label className="grid gap-2 text-sm" htmlFor="admin-login-password">密码<input aria-describedby={errors.password ? 'admin-login-password-error' : undefined} aria-invalid={Boolean(errors.password)} autoComplete="current-password" className="h-10 rounded-md border bg-background px-3" id="admin-login-password" name="password" type="password" /></label>
      {errors.password ? <p id="admin-login-password-error" role="alert" className="text-sm">{errors.password}</p> : null}
      <button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={submitting} type="submit">{submitting ? '正在登录…' : '登录后台'}</button>
    </form>
  </main>
}
