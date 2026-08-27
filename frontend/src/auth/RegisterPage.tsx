import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

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
        {formError ? <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</div> : null}
        <div className="grid gap-2">
          <label htmlFor="register-email" className="font-medium">邮箱</label>
          <input id="register-email" type="email" inputMode="email" autoComplete="email" disabled={submitting} aria-invalid={Boolean(form.formState.errors.email)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('email')} />
          {form.formState.errors.email ? <p className="text-sm text-red-700">{form.formState.errors.email.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <label htmlFor="register-password" className="font-medium">密码</label>
          <input id="register-password" type="password" autoComplete="new-password" disabled={submitting} aria-invalid={Boolean(form.formState.errors.password)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('password')} />
          <p className="text-sm text-slate-600">密码长度为 12 至 128 个字符。</p>
          {form.formState.errors.password ? <p className="text-sm text-red-700">{form.formState.errors.password.message}</p> : null}
        </div>
        <div className="grid gap-2">
          <label htmlFor="register-confirm-password" className="font-medium">确认密码</label>
          <input id="register-confirm-password" type="password" autoComplete="new-password" disabled={submitting} aria-invalid={Boolean(form.formState.errors.confirmPassword)} className="min-h-11 rounded-lg border border-slate-300 bg-white px-3" {...form.register('confirmPassword')} />
          {form.formState.errors.confirmPassword ? <p className="text-sm text-red-700">{form.formState.errors.confirmPassword.message}</p> : null}
        </div>
        <button disabled={submitting} className="min-h-11 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white disabled:opacity-50" type="submit">
          发送验证码{submitting ? '…' : ''}
        </button>
        <Link className="w-fit text-sm text-slate-700 underline hover:text-teal-700" to="/login">返回登录</Link>
      </form>
    </AuthEntryPage>
  )
}
