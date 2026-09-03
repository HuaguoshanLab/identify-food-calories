import { z } from 'zod'
import { useEffect, useState, type PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAdminAuth } from './AdminAuthProvider'

const probeResponseSchema = z.object({
  status: z.literal('ADMIN_ACCESS_GRANTED'),
}).strict()

type ProbeState = 'checking' | 'granted' | 'forbidden' | 'unauthenticated'

async function probeAdminAccess(accessToken: string) {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}/probe`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    method: 'GET',
  })
  if (!response.ok) return response.status === 403 ? 'forbidden' : 'unauthenticated'
  probeResponseSchema.parse(await response.json())
  return 'granted' as const
}

/**
 * This only delays route rendering until the API proves the current DB role.
 * Every admin request still receives its own backend RBAC check.
 */
export function AdminRouteGuard({ children }: PropsWithChildren) {
  const { accessToken, clearSession } = useAdminAuth()
  const location = useLocation()
  const [state, setState] = useState<ProbeState>(accessToken ? 'checking' : 'unauthenticated')

  useEffect(() => {
    let active = true
    if (!accessToken) {
      // A 403 cleared the token too; preserve its explicit non-disclosing outcome.
      setState((previous) => previous === 'forbidden' ? previous : 'unauthenticated')
      return () => { active = false }
    }
    setState('checking')
    void probeAdminAccess(accessToken).then((nextState) => {
      if (!active) return
      if (nextState !== 'granted') clearSession()
      setState(nextState)
    }).catch(() => {
      if (!active) return
      clearSession()
      setState('unauthenticated')
    })
    return () => { active = false }
  }, [accessToken, clearSession])

  if (state === 'checking') return <main aria-busy="true" aria-live="polite" className="admin-runtime-root">正在验证后台访问权限…</main>
  if (state === 'forbidden') return <Navigate replace to="/admin/forbidden" />
  if (state === 'unauthenticated') {
    const returnTo = `${location.pathname}${location.search}`
    const login = returnTo.startsWith('/admin/') ? `/admin/login?returnTo=${encodeURIComponent(returnTo)}` : '/admin/login'
    return <Navigate replace to={login} />
  }
  return <>{children}</>
}
