import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'

import { AuthEntryPage } from './PublicPages'
import { forgotPasswordSchema, type ForgotPasswordValues } from './schemas'

export function ForgotPasswordPage() {
  const [formError, setFormError] = useState<string>()
  const form = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema) })

  function onSubmit() {
    // Password reset API is intentionally unavailable until the server recovery contract exists.
    setFormError('服务暂时不可用，请稍后再试。')
  }

  return (
    <AuthEntryPage title="忘记密码" description="输入邮箱以申请重置验证码。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</div> : null}
        <div className="grid gap-2">
          <label htmlFor="forgot-email" className="font-medium">邮箱</label>
          <input id="forgot-email" type="email" inputMode="email" autoComplete="email" aria-invalid={Boolean(form.formState.errors.email)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('email')} />
          {form.formState.errors.email ? <p className="text-sm text-red-700">{form.formState.errors.email.message}</p> : null}
        </div>
        <button className="min-h-11 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white" type="submit">发送重置验证码</button>
        <Link className="w-fit text-sm text-slate-700 underline hover:text-teal-700" to="/login">返回登录</Link>
      </form>
    </AuthEntryPage>
  )
}
