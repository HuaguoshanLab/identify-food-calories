import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

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
  const sessionsQuery = useQuery({ enabled: Boolean(user?.id), queryFn: () => readSessions(request), queryKey: ['auth', 'sessions', user?.id], retry: false })
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
  return (
    <section className="mt-8 border-t border-slate-200 pt-6" aria-labelledby="sessions-heading">
      <h2 ref={headingRef} tabIndex={-1} id="sessions-heading" className="text-lg font-semibold">登录会话</h2>
      {message ? <p role="status" aria-live="polite" className="mt-3 text-sm text-teal-800">{message}</p> : null}
      {sessionsQuery.isLoading ? <div role="status" aria-label="正在加载登录会话" className="mt-4 grid gap-3"><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></div> : null}
      {sessionsQuery.isError ? <div className="mt-4 rounded-lg bg-red-50 p-4" role="alert"><p className="text-sm text-red-700">无法加载登录会话。请检查网络后重新尝试。</p><Button className="mt-3" onClick={() => void sessionsQuery.refetch()} variant="outline">重新尝试</Button></div> : null}
      {!sessionsQuery.isLoading && !sessionsQuery.isError ? <div className="mt-4 grid gap-3">
        {currentSession ? <SessionRow session={currentSession} onCurrentLogout={logoutCurrentDevice} loggingOut={loggingOut} /> : null}
        {otherSessions.length === 0 ? <div className="rounded-lg border border-slate-200 p-4"><h3 className="font-medium">暂无其他登录会话</h3><p className="mt-1 text-sm text-slate-700">只有当前设备保持登录。新的设备登录后会显示在这里。</p></div> : otherSessions.map((session) => <SessionRow key={session.id} session={session} onRevoke={() => { setMessage(undefined); revokeMutation.reset(); setSelected(session) }} />)}
      </div> : null}
      <RevokeSessionDialog error={revokeMutation.isError ? '无法撤销这个登录会话。请检查网络后重新尝试。' : undefined} onConfirm={() => selected && revokeMutation.mutate(selected)} onOpenChange={(open) => { if (!open && !revokeMutation.isPending) { setSelected(undefined); revokeMutation.reset() } }} open={Boolean(selected)} pending={revokeMutation.isPending} session={selected} />
    </section>
  )
}

function SessionRow({ loggingOut = false, onCurrentLogout, onRevoke, session }: { loggingOut?: boolean; onCurrentLogout?: () => void; onRevoke?: () => void; session: AuthSessionSummary }) {
  return <article className="rounded-lg border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{session.device_label ?? '未知设备'}{session.is_current ? '（当前设备）' : ''}</h3><p className="mt-1 text-sm text-slate-700">最近活动：{formatDate(session.last_seen_at)}</p><p className="text-sm text-slate-700">到期：{formatDate(session.expires_at)}</p></div>{session.is_current ? <Button disabled={loggingOut} onClick={onCurrentLogout} variant="outline">{loggingOut ? '正在退出…' : '退出当前设备'}</Button> : <Button onClick={onRevoke} variant="destructive">撤销会话</Button>}</div></article>
}
