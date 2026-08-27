import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'

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
    <AuthEntryPage title="重置密码" description="输入邮箱收到的验证码并设置新密码。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</div> : null}
        <div className="grid gap-2">
          <label htmlFor="recovery-code" className="font-medium">6 位邮箱验证码</label>
          <input id="recovery-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} aria-invalid={Boolean(form.formState.errors.code)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('code')} />
          {form.formState.errors.code ? <p className="text-sm text-red-700">{form.formState.errors.code.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <label htmlFor="recovery-password" className="font-medium">新密码</label>
          <input id="recovery-password" type="password" autoComplete="new-password" aria-invalid={Boolean(form.formState.errors.password)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('password')} />
          {form.formState.errors.password ? <p className="text-sm text-red-700">{form.formState.errors.password.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <label htmlFor="recovery-confirm-password" className="font-medium">确认新密码</label>
          <input id="recovery-confirm-password" type="password" autoComplete="new-password" aria-invalid={Boolean(form.formState.errors.confirmPassword)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('confirmPassword')} />
          {form.formState.errors.confirmPassword ? <p className="text-sm text-red-700">{form.formState.errors.confirmPassword.message}</p> : null}
        </div>
        <button disabled={form.formState.isSubmitting} className="min-h-11 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white disabled:opacity-50" type="submit">更新密码</button>
        <Link className="w-fit text-sm text-slate-700 underline hover:text-teal-700" to="/forgot-password">重新申请重置</Link>
      </form>
    </AuthEntryPage>
  )
}
