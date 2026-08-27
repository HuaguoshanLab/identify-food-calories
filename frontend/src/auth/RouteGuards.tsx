import { useEffect, useRef, type PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { loginHrefFor } from './returnTo'
import { useAuth } from './useAuth'

export function RequireAuthentication({ children }: PropsWithChildren) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'bootstrapping') {
    return (
      <main className="flex min-h-dvh items-center justify-center px-4" role="status" aria-live="polite">
        <p className="text-slate-700">正在确认登录状态…</p>
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
      </section>
    </main>
  )
}
