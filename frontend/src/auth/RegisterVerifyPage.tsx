import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import {
  AuthApiError,
  getRegistrationContext,
  resendRegistrationCode,
  verifyRegistration,
  type PendingVerificationContext,
} from './api'
import { AuthEntryPage } from './PublicPages'
import { verificationCodeSchema, type VerificationCodeValues } from './schemas'

function secondsUntil(isoTimestamp: string, now: number) {
  return Math.max(0, Math.ceil((new Date(isoTimestamp).getTime() - now) / 1_000))
}

function verificationErrorMessage(error: AuthApiError) {
  switch (error.code) {
    case 'INVALID_VERIFICATION_CODE':
      return '验证码不正确，请重新输入。'
    case 'VERIFICATION_CODE_EXPIRED':
      return '验证码已过期，请重新发送。'
    case 'VERIFICATION_ATTEMPTS_EXCEEDED':
      return '验证码已失效，请重新发送后再试。'
    case 'NETWORK_ERROR':
      return '暂时无法连接服务，请检查网络后重试。'
    default:
      return '服务暂时不可用，请稍后重试。'
  }
}

export function RegisterVerifyPage() {
  const navigate = useNavigate()
  const contextQuery = useQuery({
    queryKey: ['auth', 'registration-context'],
    queryFn: getRegistrationContext,
    retry: false,
  })
  const [resendContext, setResendContext] = useState<PendingVerificationContext>()
  const [invalidContext, setInvalidContext] = useState(false)
  const [formError, setFormError] = useState<string>()
  const [announcement, setAnnouncement] = useState<string>()
  const [canRetryVerification, setCanRetryVerification] = useState(false)
  const [terminal, setTerminal] = useState(false)
  const [clock, setClock] = useState(() => Date.now())
  const form = useForm<VerificationCodeValues>({
    resolver: zodResolver(verificationCodeSchema),
  })
  const codeInputProps = form.register('code', {
    onChange: (event) => {
      form.setValue('code', event.target.value.replace(/[^0-9]/g, '').slice(0, 6), {
        shouldValidate: true,
      })
    },
  })

  const pending = invalidContext ? undefined : resendContext ?? contextQuery.data
  const resendAvailableAt = pending?.resend_available_at

  useEffect(() => {
    if (!resendAvailableAt) {
      return
    }

    const timer = window.setInterval(() => setClock(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [resendAvailableAt])

  function focusCodeInput(select = false) {
    window.setTimeout(() => {
      form.setFocus('code', { shouldSelect: select })
    }, 0)
  }

  async function onSubmit(values: VerificationCodeValues) {
    setFormError(undefined)
    setCanRetryVerification(false)
    try {
      await verifyRegistration(values.code)
      form.reset()
      navigate('/login', { replace: true, state: { message: '邮箱验证成功，请登录。' } })
    } catch (error) {
      if (!(error instanceof AuthApiError)) {
        setFormError('服务暂时不可用，请稍后重试。')
        setCanRetryVerification(true)
        return
      }

      if (error.code === 'VERIFICATION_CONTEXT_INVALID') {
        setInvalidContext(true)
        return
      }
      if (error.code === 'INVALID_VERIFICATION_CODE') {
        form.setError('code', { message: verificationErrorMessage(error) })
        focusCodeInput(true)
        return
      }
      if (error.code === 'VERIFICATION_ATTEMPTS_EXCEEDED') {
        form.reset()
        setTerminal(true)
      }
      if (error.code === 'VERIFICATION_CODE_EXPIRED') {
        setTerminal(true)
      }
      setFormError(verificationErrorMessage(error))
      setCanRetryVerification(error.code === 'NETWORK_ERROR')
    }
  }

  async function resendCode() {
    if (cooldown > 0) {
      return
    }

    setFormError(undefined)
    setAnnouncement(undefined)
    try {
      const nextPending = await resendRegistrationCode()
      setResendContext(nextPending)
      setTerminal(false)
      form.reset()
      setAnnouncement('新验证码已发送，之前的验证码已失效。')
      focusCodeInput()
    } catch (error) {
      if (!(error instanceof AuthApiError)) {
        setFormError('服务暂时不可用，请稍后重试。')
        return
      }
      if (error.code === 'RESEND_COOLDOWN') {
        if (pending) {
          setResendContext({
            ...pending,
            resend_available_at: new Date(clock + (error.retryAfter ?? 60) * 1_000).toISOString(),
          })
        }
        return
      }
      if (error.code === 'VERIFICATION_CONTEXT_INVALID') {
        setInvalidContext(true)
        return
      }
      setFormError(verificationErrorMessage(error))
    }
  }

  if (contextQuery.isPending) {
    return (
      <AuthEntryPage progress="步骤 2/2" title="验证邮箱" description="正在确认验证信息…">
        <p role="status" aria-live="polite" className="mt-6 text-sm text-muted-foreground">正在确认验证信息…</p>
      </AuthEntryPage>
    )
  }

  if (contextQuery.isError || !pending) {
    const invalidContext = contextQuery.error instanceof AuthApiError && contextQuery.error.code === 'VERIFICATION_CONTEXT_INVALID'
    return (
      <AuthEntryPage
        progress="步骤 2/2"
        title="验证邮箱"
        description={invalidContext ? '验证信息已失效，请重新开始。' : '暂时无法连接服务，请检查网络后重试。'}
      >
        {invalidContext ? (
          <Link className="mt-6 inline-block text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/register">返回注册</Link>
        ) : (
          <Button className="mt-6 h-11 text-base" variant="link" type="button" onClick={() => void contextQuery.refetch()}>重新尝试</Button>
        )}
      </AuthEntryPage>
    )
  }

  const cooldown = secondsUntil(pending.resend_available_at, clock)
  const disabled = terminal || form.formState.isSubmitting
  const resendLabel = cooldown > 0 ? `${cooldown} 秒后可重新发送` : '重新发送验证码'

  return (
    <AuthEntryPage
      progress="步骤 2/2"
      title="验证邮箱"
      description={`输入发送到 ${pending.masked_email} 的 6 位验证码。验证码 10 分钟内有效。`}
    >
      <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
        {formError ? (
          <Alert variant="destructive">
            <AlertDescription>{formError}</AlertDescription>
            {canRetryVerification ? (
              <Button className="mt-2 h-11 text-base" variant="link" type="button" onClick={() => void form.handleSubmit(onSubmit)()}>
                重新尝试验证
              </Button>
            ) : null}
          </Alert>
        ) : null}
        {announcement ? <p aria-live="polite" className="text-sm text-muted-foreground">{announcement}</p> : null}
        <div className="grid gap-2">
          <Label htmlFor="registration-code" className="text-base">6 位邮箱验证码</Label>
          <Input
            id="registration-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            aria-invalid={Boolean(form.formState.errors.code)}
            aria-describedby={form.formState.errors.code ? 'registration-code-error' : undefined}
            disabled={disabled}
            className="h-11 text-base"
            {...codeInputProps}
          />
          {form.formState.errors.code ? <p id="registration-code-error" className="text-sm text-destructive">{form.formState.errors.code.message}</p> : null}
        </div>
        <Button disabled={disabled} className="h-11 w-full cursor-pointer text-base font-semibold" type="submit">
          验证并激活账号{form.formState.isSubmitting ? '…' : ''}
        </Button>
        <Button disabled={cooldown > 0 || form.formState.isSubmitting} className="h-11 w-full cursor-pointer text-base font-semibold" variant="outline" type="button" onClick={() => void resendCode()}>
          {resendLabel}
        </Button>
        <Link className="w-fit text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/register">返回修改邮箱</Link>
      </form>
    </AuthEntryPage>
  )
}
