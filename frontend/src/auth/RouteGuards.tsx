import { useEffect, useRef, type PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { Skeleton } from '@/components/ui/skeleton'

import { loginHrefFor } from './returnTo'
import { SessionList } from './SessionList'
import { useAuth } from './useAuth'

export function RequireAuthentication({ children }: PropsWithChildren) {
  const { retryBootstrap, status } = useAuth()
  const location = useLocation()

  if (status === 'bootstrapping') {
    return (
      <main className="flex min-h-dvh items-center justify-center px-4" role="status" aria-live="polite">
        <div className="w-full max-w-md space-y-3" aria-label="正在确认登录状态…">
          <Skeleton className="h-5 w-2/5" />
          <Skeleton className="h-5 w-3/5" />
          <p className="text-slate-700">正在确认登录状态…</p>
        </div>
      </main>
    )
  }

  if (status === 'identity-error') {
    return (
      <main className="flex min-h-dvh items-center justify-center px-4">
        <section className="w-full max-w-md rounded-xl bg-card p-6 shadow-sm ring-1 ring-foreground/10">
          <h1 className="text-xl font-semibold">无法加载账号信息</h1>
          <p className="mt-2 text-sm text-slate-700" role="alert">请检查网络后重新尝试。</p>
          <button className="mt-5 min-h-11 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white" onClick={() => void retryBootstrap()} type="button">重新尝试</button>
        </section>
      </main>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate replace to={loginHrefFor(location)} />
  }

  return children
}

export function AccountAndSessionsPage() {
  const { user } = useAuth()
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <main className="min-h-dvh px-4 py-8 md:px-6">
      <section className="mx-auto w-full max-w-md rounded-xl bg-card p-6 shadow-sm ring-1 ring-foreground/10">
        <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold tracking-tight">账号与会话</h1>
        <dl className="mt-6 grid gap-3 text-sm">
          <div>
            <dt className="text-slate-600">邮箱</dt>
            <dd className="font-medium">{user?.email}</dd>
          </div>
          <div>
            <dt className="text-slate-600">角色</dt>
            <dd className="font-medium">{user?.role}</dd>
          </div>
        </dl>
        <SessionList />
      </section>
    </main>
  )
}
