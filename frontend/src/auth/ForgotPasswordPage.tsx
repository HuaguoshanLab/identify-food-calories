import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { AuthApiError, requestPasswordRecovery } from './api'
import { AuthEntryPage } from './PublicPages'
import { forgotPasswordSchema, type ForgotPasswordValues } from './schemas'

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string>()
  const form = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema) })

  async function onSubmit(values: ForgotPasswordValues) {
    setFormError(undefined)
    try {
      await requestPasswordRecovery(values.email)
      navigate('/reset-password', { replace: true })
    } catch (error) {
      setFormError(error instanceof AuthApiError && error.code === 'CSRF_ORIGIN_INVALID'
        ? '请求来源无效，请刷新后重试。'
        : '服务暂时不可用，请稍后再试。')
    }
  }

  return (
    <AuthEntryPage progress="步骤 1/2" title="忘记密码" description="输入邮箱以申请重置验证码。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? <Alert variant="destructive"><AlertDescription>{formError}</AlertDescription></Alert> : null}
        <div className="grid gap-2">
          <Label htmlFor="forgot-email" className="text-base">邮箱</Label>
          <Input id="forgot-email" type="email" inputMode="email" autoComplete="email" disabled={form.formState.isSubmitting} aria-describedby={form.formState.errors.email ? 'forgot-email-error' : undefined} aria-invalid={Boolean(form.formState.errors.email)} className="h-11 text-base" {...form.register('email')} />
          {form.formState.errors.email ? <p id="forgot-email-error" className="text-sm text-destructive">{form.formState.errors.email.message}</p> : null}
        </div>
        <Button disabled={form.formState.isSubmitting} className="h-11 w-full cursor-pointer text-base font-semibold" type="submit">发送重置验证码</Button>
        <Link className="w-fit text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/login">返回登录</Link>
      </form>
    </AuthEntryPage>
  )
}
