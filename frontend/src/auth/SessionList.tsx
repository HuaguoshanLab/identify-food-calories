import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

import type { AuthSessionSummary } from './api'
import { RevokeSessionDialog } from './RevokeSessionDialog'
import { useAuth } from './useAuth'

async function readSessions(request: (path: string, init?: RequestInit) => Promise<Response>) {
  const response = await request('/auth/sessions', { method: 'GET' })
  if (!response.ok) throw new Error('SESSION_LIST_FAILED')
  return response.json() as Promise<AuthSessionSummary[]>
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? '未知时间' : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(date)
}

export function SessionList() {
  const { logout, request, user } = useAuth()
  const queryClient = useQueryClient()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [selected, setSelected] = useState<AuthSessionSummary>()
  const [message, setMessage] = useState<string>()
  const [loggingOut, setLoggingOut] = useState(false)
  const canLoadSessions = Boolean(user?.id)
  const sessionsQuery = useQuery({ enabled: canLoadSessions, queryFn: () => readSessions(request), queryKey: ['auth', 'sessions', user?.id], retry: false })
  const revokeMutation = useMutation({
    mutationFn: async (session: AuthSessionSummary) => {
      const response = await request(`/auth/sessions/${session.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('SESSION_REVOKE_FAILED')
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['auth', 'sessions', user?.id] })
      setSelected(undefined)
      setMessage('登录会话已撤销。')
      headingRef.current?.focus()
    },
  })

  async function logoutCurrentDevice() {
    setLoggingOut(true)
    await logout()
  }

  const sessions = sessionsQuery.data ?? []
  const currentSession = sessions.find((session) => session.is_current)
  const otherSessions = sessions.filter((session) => !session.is_current)
  const isLoading = !canLoadSessions || sessionsQuery.isLoading
  return (
    <section className="grid gap-4" aria-labelledby="sessions-heading">
      <h2 ref={headingRef} tabIndex={-1} id="sessions-heading" className="text-xl font-semibold leading-7">登录会话</h2>
      {message ? <p role="status" aria-live="polite" className="text-base text-foreground">{message}</p> : null}
      {isLoading ? <div role="status" aria-label="正在加载登录会话" className="grid gap-4"><Skeleton className="h-36 w-full rounded-lg" /><Skeleton className="h-36 w-full rounded-lg" /></div> : null}
      {sessionsQuery.isError ? <InlineRetryState error onRetry={() => void sessionsQuery.refetch()} /> : null}
      {!isLoading && !sessionsQuery.isError ? <div className="grid gap-4">
        {currentSession ? <SessionRow session={currentSession} onCurrentLogout={logoutCurrentDevice} loggingOut={loggingOut} /> : null}
        {currentSession && otherSessions.length === 0 ? <NormalEmptyState /> : null}
        {!currentSession ? <InlineRetryState onRetry={() => void sessionsQuery.refetch()} /> : null}
        {otherSessions.map((session) => <SessionRow key={session.id} session={session} onRevoke={() => { setMessage(undefined); revokeMutation.reset(); setSelected(session) }} />)}
      </div> : null}
      <RevokeSessionDialog error={revokeMutation.isError ? '无法撤销这个登录会话。请检查网络后重新尝试。' : undefined} onConfirm={() => { if (selected) revokeMutation.mutate(selected) }} onOpenChange={(open) => { if (!open && !revokeMutation.isPending) { setSelected(undefined); revokeMutation.reset() } }} open={Boolean(selected)} pending={revokeMutation.isPending} session={selected} />
    </section>
  )
}

function SessionRow({ loggingOut = false, onCurrentLogout, onRevoke, session }: { loggingOut?: boolean; onCurrentLogout?: () => void; onRevoke?: () => void; session: AuthSessionSummary }) {
  return (
    <article className="rounded-lg border bg-card p-4 text-card-foreground">
      <div className="flex flex-col gap-4 min-[380px]:flex-row min-[380px]:items-start min-[380px]:justify-between">
        <div className="min-w-0">
          <h3 className="break-words text-base font-semibold leading-6">{session.device_label ?? '未知设备'}{session.is_current ? '（当前设备）' : ''}</h3>
          <div data-testid="session-dates" className="mt-2 grid gap-1 text-xs leading-4 text-muted-foreground tabular-nums">
            <p>最近活动：{formatDate(session.last_seen_at)}</p>
            <p>到期：{formatDate(session.expires_at)}</p>
          </div>
        </div>
        {session.is_current ? <Button className="min-h-11 w-full shrink-0 min-[380px]:w-auto" disabled={loggingOut} onClick={onCurrentLogout} variant="outline">{loggingOut ? '正在退出…' : '退出当前设备'}</Button> : <Button className="min-h-11 w-full shrink-0 min-[380px]:w-auto" onClick={onRevoke} variant="destructive">撤销会话</Button>}
      </div>
    </article>
  )
}

function InlineRetryState({ error = false, onRetry }: { error?: boolean; onRetry: () => void }) {
  return (
    <Alert variant={error ? 'destructive' : 'default'}>
      <AlertTitle>{error ? '无法加载登录会话。请检查网络后重新尝试。' : '暂时没有可显示的登录会话。'}</AlertTitle>
      {!error ? <AlertDescription>请重新尝试；当前设备会话恢复后将显示在这里。</AlertDescription> : null}
      <Button className="mt-4 min-h-11" onClick={onRetry} variant="outline">重新尝试</Button>
    </Alert>
  )
}

function NormalEmptyState() {
  return (
    <section className="rounded-lg border bg-card p-4 text-card-foreground" aria-labelledby="other-sessions-heading">
      <h3 id="other-sessions-heading" className="text-base font-semibold leading-6">暂无其他登录会话</h3>
      <p className="mt-2 text-base leading-6 text-muted-foreground">只有当前设备保持登录。新的设备登录后会显示在这里。</p>
    </section>
  )
}
