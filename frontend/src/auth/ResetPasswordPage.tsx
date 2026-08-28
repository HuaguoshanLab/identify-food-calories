import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { AuthApiError, resetPassword, verifyRecoveryCode } from './api'
import { AuthEntryPage } from './PublicPages'
import { resetPasswordSchema, type ResetPasswordValues } from './schemas'

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string>()
  const form = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema) })

  async function onSubmit(values: ResetPasswordValues) {
    setFormError(undefined)
    try {
      // Verification and reset remain separate public API transitions; the context stays HttpOnly.
      await verifyRecoveryCode(values.code)
      await resetPassword({ code: values.code, newPassword: values.password })
      navigate('/login', { replace: true, state: { message: '密码已更新，请重新登录。' } })
    } catch (error) {
      const code = error instanceof AuthApiError ? error.code : 'UNKNOWN_ERROR'
      setFormError(code === 'INVALID_RECOVERY_CODE' ? '验证码不正确，请重新输入。' : '恢复信息已失效，请重新开始。')
    }
  }

  return (
    <AuthEntryPage progress="步骤 2/2" title="重置密码" description="输入邮箱收到的验证码并设置新密码。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? <Alert variant="destructive"><AlertDescription>{formError}</AlertDescription></Alert> : null}
        <div className="grid gap-2">
          <Label htmlFor="recovery-code" className="text-base">6 位邮箱验证码</Label>
          <Input id="recovery-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} disabled={form.formState.isSubmitting} aria-describedby={form.formState.errors.code ? 'recovery-code-error' : undefined} aria-invalid={Boolean(form.formState.errors.code)} className="h-11 text-base" {...form.register('code')} />
          {form.formState.errors.code ? <p id="recovery-code-error" className="text-sm text-destructive">{form.formState.errors.code.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="recovery-password" className="text-base">新密码</Label>
          <Input id="recovery-password" type="password" autoComplete="new-password" disabled={form.formState.isSubmitting} aria-describedby={form.formState.errors.password ? 'recovery-password-error' : undefined} aria-invalid={Boolean(form.formState.errors.password)} className="h-11 text-base" {...form.register('password')} />
          {form.formState.errors.password ? <p id="recovery-password-error" className="text-sm text-destructive">{form.formState.errors.password.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="recovery-confirm-password" className="text-base">确认新密码</Label>
          <Input id="recovery-confirm-password" type="password" autoComplete="new-password" disabled={form.formState.isSubmitting} aria-describedby={form.formState.errors.confirmPassword ? 'recovery-confirm-password-error' : undefined} aria-invalid={Boolean(form.formState.errors.confirmPassword)} className="h-11 text-base" {...form.register('confirmPassword')} />
          {form.formState.errors.confirmPassword ? <p id="recovery-confirm-password-error" className="text-sm text-destructive">{form.formState.errors.confirmPassword.message}</p> : null}
        </div>
        <Button disabled={form.formState.isSubmitting} className="h-11 w-full cursor-pointer text-base font-semibold" type="submit">更新密码</Button>
        <Link className="w-fit text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/forgot-password">重新申请重置</Link>
      </form>
    </AuthEntryPage>
  )
}
