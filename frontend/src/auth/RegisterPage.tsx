import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { AuthApiError, registerAccount } from './api'
import { AuthEntryPage } from './PublicPages'
import { registerSchema, type RegisterValues } from './schemas'

function registrationErrorMessage(error: unknown) {
  if (error instanceof AuthApiError && error.code === 'NETWORK_ERROR') {
    return '暂时无法连接服务，请检查网络后重试。'
  }
  return '服务暂时不可用，请稍后再试。'
}

export function RegisterPage() {
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string>()
  const form = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })

  async function onSubmit(values: RegisterValues) {
    setFormError(undefined)
    try {
      await registerAccount({ email: values.email, password: values.password })
      navigate('/register/verify', { replace: true })
    } catch (error) {
      setFormError(registrationErrorMessage(error))
    }
  }

  const submitting = form.formState.isSubmitting

  return (
    <AuthEntryPage title="创建账号" description="使用邮箱创建你的饮食健康档案。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        <p className="text-sm text-muted-foreground">步骤 1/2</p>
        {formError ? <Alert variant="destructive"><AlertDescription>{formError}</AlertDescription></Alert> : null}
        <div className="grid gap-2">
          <Label htmlFor="register-email" className="text-base">邮箱</Label>
          <Input id="register-email" type="email" inputMode="email" autoComplete="email" disabled={submitting} aria-describedby={form.formState.errors.email ? 'register-email-error' : undefined} aria-invalid={Boolean(form.formState.errors.email)} className="h-11 text-base" {...form.register('email')} />
          {form.formState.errors.email ? <p id="register-email-error" className="text-sm text-destructive">{form.formState.errors.email.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="register-password" className="text-base">密码</Label>
          <Input id="register-password" type="password" autoComplete="new-password" disabled={submitting} aria-describedby={form.formState.errors.password ? 'register-password-error' : 'register-password-help'} aria-invalid={Boolean(form.formState.errors.password)} className="h-11 text-base" {...form.register('password')} />
          <p id="register-password-help" className="text-sm text-muted-foreground">密码长度为 12 至 128 个字符。</p>
          {form.formState.errors.password ? <p id="register-password-error" className="text-sm text-destructive">{form.formState.errors.password.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="register-confirm-password" className="text-base">确认密码</Label>
          <Input id="register-confirm-password" type="password" autoComplete="new-password" disabled={submitting} aria-describedby={form.formState.errors.confirmPassword ? 'register-confirm-password-error' : undefined} aria-invalid={Boolean(form.formState.errors.confirmPassword)} className="h-11 text-base" {...form.register('confirmPassword')} />
          {form.formState.errors.confirmPassword ? <p id="register-confirm-password-error" className="text-sm text-destructive">{form.formState.errors.confirmPassword.message}</p> : null}
        </div>
        <Button disabled={submitting} className="h-11 w-full cursor-pointer text-base font-semibold" type="submit">
          发送验证码{submitting ? '…' : ''}
        </Button>
        <Link className="w-fit text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/login">返回登录</Link>
      </form>
    </AuthEntryPage>
  )
}
