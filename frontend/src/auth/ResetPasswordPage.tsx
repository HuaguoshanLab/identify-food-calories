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

type RecoveryOperation = 'verify' | 'reset'

const terminalRecoveryMessages: Record<string, string> = {
  RECOVERY_CONTEXT_INVALID: '恢复信息已失效，请重新开始。',
  RECOVERY_CODE_EXPIRED: '验证码已过期，请重新申请重置。',
  RECOVERY_ATTEMPTS_EXCEEDED: '验证码尝试次数已用尽，请重新申请重置。',
}

function recoverableErrorMessage(error: unknown) {
  if (!(error instanceof AuthApiError)) {
    return '服务暂时不可用，请稍后重试。'
  }

  switch (error.code) {
    case 'NETWORK_ERROR':
      return '暂时无法连接服务，请检查网络后重试。'
    case 'CSRF_ORIGIN_INVALID':
      return '请求来源无效，请刷新后重试。'
    default:
      return '服务暂时不可用，请稍后重试。'
  }
}

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string>()
  const [terminalError, setTerminalError] = useState<string>()
  const [verifiedRecoveryCode, setVerifiedRecoveryCode] = useState(false)
  const [retryOperation, setRetryOperation] = useState<RecoveryOperation>()
  const form = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema) })

  function focusCodeInput() {
    window.setTimeout(() => form.setFocus('code', { shouldSelect: true }), 0)
  }

  function handleActionError(error: unknown, operation: RecoveryOperation) {
    if (error instanceof AuthApiError && error.code === 'INVALID_RECOVERY_CODE') {
      form.setError('code', { message: '验证码不正确，请重新输入。' })
      setRetryOperation(undefined)
      focusCodeInput()
      return
    }

    if (error instanceof AuthApiError && terminalRecoveryMessages[error.code]) {
      setTerminalError(terminalRecoveryMessages[error.code])
      setRetryOperation(undefined)
      return
    }

    setFormError(recoverableErrorMessage(error))
    setRetryOperation(operation)
  }

  async function completeReset(values: ResetPasswordValues, operation: RecoveryOperation) {
    setFormError(undefined)
    try {
      await resetPassword({ code: values.code, newPassword: values.password })
      navigate('/login', { replace: true, state: { message: '密码已更新，请重新登录。' } })
    } catch (error) {
      handleActionError(error, operation)
    }
  }

  async function onSubmit(values: ResetPasswordValues) {
    setFormError(undefined)
    setTerminalError(undefined)
    let failedOperation: RecoveryOperation = verifiedRecoveryCode ? 'reset' : 'verify'

    try {
      if (!verifiedRecoveryCode) {
        // The server owns the HttpOnly recovery context; this flag only prevents repeat verification in this view.
        await verifyRecoveryCode(values.code)
        setVerifiedRecoveryCode(true)
        failedOperation = 'reset'
      }
      await resetPassword({ code: values.code, newPassword: values.password })
      navigate('/login', { replace: true, state: { message: '密码已更新，请重新登录。' } })
    } catch (error) {
      handleActionError(error, failedOperation)
    }
  }

  function retryFailedOperation() {
    const values = form.getValues()
    if (retryOperation === 'reset') {
      void completeReset(values, 'reset')
      return
    }
    void onSubmit(values)
  }

  if (terminalError) {
    return (
      <AuthEntryPage progress="步骤 2/2" title="重置密码" description="需要重新申请重置验证码。">
        <Alert className="mt-6" variant="destructive"><AlertDescription>{terminalError}</AlertDescription></Alert>
        <Link className="mt-6 inline-block text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/forgot-password">重新申请重置</Link>
      </AuthEntryPage>
    )
  }

  return (
    <AuthEntryPage progress="步骤 2/2" title="重置密码" description="输入邮箱收到的验证码并设置新密码。">
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? (
          <Alert variant="destructive">
            <AlertDescription>{formError}</AlertDescription>
            {retryOperation ? <Button className="mt-2 h-11 text-base" variant="link" type="button" onClick={retryFailedOperation}>重新尝试</Button> : null}
          </Alert>
        ) : null}
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
