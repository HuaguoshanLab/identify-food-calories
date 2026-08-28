import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { MobileFrame } from '@/layouts/MobileFrame'

import { loginHrefFor } from './returnTo'
import { useAuth } from './useAuth'

/**
 * This pathless boundary owns one identity-recovery lifecycle for every protected child route.
 * Rendering an Outlet here keeps route composition in App.tsx and prevents individual pages from
 * accidentally skipping bootstrap, error recovery, or the exact post-login return destination.
 */
export function RequireAuthentication() {
  const { retryBootstrap, status } = useAuth()
  const location = useLocation()

  if (status === 'bootstrapping') {
    return (
      <MobileFrame>
        <main className="flex flex-1 items-center justify-center px-4" role="status" aria-live="polite">
          <div className="w-full max-w-md space-y-3" aria-label="正在确认登录状态…">
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-5 w-3/5" />
            <p className="text-muted-foreground">正在确认登录状态…</p>
          </div>
        </main>
      </MobileFrame>
    )
  }

  if (status === 'identity-error') {
    return (
      <MobileFrame>
        <main className="flex flex-1 items-center justify-center px-4">
          <section className="w-full max-w-md space-y-5 rounded-xl border bg-card p-6">
            <div className="space-y-2">
              <h1 className="text-xl font-semibold">无法加载账号信息</h1>
              <Alert variant="destructive">
                <AlertDescription>请检查网络后重新尝试。</AlertDescription>
              </Alert>
            </div>
            <Button className="h-11 w-full" onClick={() => void retryBootstrap()} type="button">
              重新尝试
            </Button>
          </section>
        </main>
      </MobileFrame>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate replace to={loginHrefFor(location)} />
  }

  return <Outlet />
}
