import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { AuthApiError } from './api'
import { useAuth } from './useAuth'
import { loginSchema, type LoginValues } from './schemas'
import { AuthEntryPage } from './PublicPages'
import { parseReturnTo } from './returnTo'

function loginErrorMessage(error: unknown) {
  if (!(error instanceof AuthApiError)) {
    return '服务暂时不可用，请稍后再试。'
  }

  if (error.code === 'AUTHENTICATION_FAILED' || error.code === 'INVALID_CREDENTIALS') {
    return '邮箱或密码不正确，请重新输入。'
  }
  if (error.code === 'RATE_LIMITED') {
    return '尝试次数过多，请稍后再试。'
  }
  if (error.code === 'NETWORK_ERROR') {
    return '暂时无法连接服务，请检查网络后重试。'
  }
  return '服务暂时不可用，请稍后再试。'
}

export function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [formError, setFormError] = useState<string>()
  const [success, setSuccess] = useState(
    location.state && typeof location.state === 'object' && 'message' in location.state
      ? String(location.state.message)
      : undefined,
  )
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
  })

  async function onSubmit(values: LoginValues) {
    setFormError(undefined)
    setSuccess(undefined)

    try {
      await login(values)
      navigate(parseReturnTo(new URLSearchParams(location.search).get('returnTo')), { replace: true })
    } catch (error) {
      setFormError(loginErrorMessage(error))
    }
  }

  const submitting = form.formState.isSubmitting

  return (
    <AuthEntryPage title="欢迎回来" description="登录后继续管理你的饮食与登录会话。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</div> : null}
        {success ? <p role="status" aria-live="polite" className="text-sm text-teal-800">{success}</p> : null}
        <div className="grid gap-2">
          <label htmlFor="login-email" className="font-medium">邮箱</label>
          <input
            id="login-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            aria-describedby={form.formState.errors.email ? 'login-email-error' : undefined}
            aria-invalid={Boolean(form.formState.errors.email)}
            disabled={submitting}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-3"
            {...form.register('email')}
          />
          {form.formState.errors.email ? <p id="login-email-error" className="text-sm text-red-700">{form.formState.errors.email.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <label htmlFor="login-password" className="font-medium">密码</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            aria-describedby={form.formState.errors.password ? 'login-password-error' : undefined}
            aria-invalid={Boolean(form.formState.errors.password)}
            disabled={submitting}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-3"
            {...form.register('password')}
          />
          {form.formState.errors.password ? <p id="login-password-error" className="text-sm text-red-700">{form.formState.errors.password.message}</p> : null}
        </div>
        <button disabled={submitting} className="min-h-11 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white disabled:opacity-50" type="submit">
          登录并继续{submitting ? '…' : ''}
        </button>
        <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <Link className="text-slate-700 underline hover:text-teal-700" to="/forgot-password">忘记密码？</Link>
          <Link className="text-slate-700 underline hover:text-teal-700" to="/register">创建账号</Link>
        </div>
      </form>
    </AuthEntryPage>
  )
}
