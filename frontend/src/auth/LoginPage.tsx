import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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
  const { login, logoutWarning } = useAuth()
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
        {logoutWarning ? <Alert><AlertDescription>{logoutWarning}</AlertDescription></Alert> : null}
        {formError ? <Alert variant="destructive"><AlertDescription>{formError}</AlertDescription></Alert> : null}
        {success ? <p role="status" aria-live="polite" className="text-sm text-muted-foreground">{success}</p> : null}
        <div className="grid gap-2">
          <Label htmlFor="login-email" className="text-base">邮箱</Label>
          <Input
            id="login-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            aria-describedby={form.formState.errors.email ? 'login-email-error' : undefined}
            aria-invalid={Boolean(form.formState.errors.email)}
            disabled={submitting}
            className="h-11 text-base"
            {...form.register('email')}
          />
          {form.formState.errors.email ? <p id="login-email-error" className="text-sm text-destructive">{form.formState.errors.email.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="login-password" className="text-base">密码</Label>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            aria-describedby={form.formState.errors.password ? 'login-password-error' : undefined}
            aria-invalid={Boolean(form.formState.errors.password)}
            disabled={submitting}
            className="h-11 text-base"
            {...form.register('password')}
          />
          {form.formState.errors.password ? <p id="login-password-error" className="text-sm text-destructive">{form.formState.errors.password.message}</p> : null}
        </div>
        <Button disabled={submitting} className="h-11 w-full cursor-pointer text-base font-semibold" type="submit">
          登录并继续{submitting ? '…' : ''}
        </Button>
        <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <Link className="text-foreground underline underline-offset-4 hover:text-primary" to="/forgot-password">忘记密码？</Link>
          <Link className="text-foreground underline underline-offset-4 hover:text-primary" to="/register">创建账号</Link>
        </div>
      </form>
    </AuthEntryPage>
  )
}
