import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react'
import { restoreAdminSession } from './session'

export type AdminIdentity = Readonly<{
  id: string
}>

export type AdminSession = Readonly<{
  accessToken: string
  identity: AdminIdentity
}>

export type AdminAuthContextValue = Readonly<{
  accessToken: string | undefined
  clearSession: () => void
  establishSession: (session: AdminSession) => void
  identity: AdminIdentity | undefined
  isAuthenticated: boolean
  isRestoring: boolean
  logout: () => void
}>

const AdminAuthContext = createContext<AdminAuthContextValue | undefined>(undefined)

function isIdentityChange(previous: AdminIdentity | undefined, next: AdminIdentity) {
  return previous?.id !== next.id
}

export function AdminAuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient()
  const sessionRef = useRef<AdminSession | undefined>(undefined)
  const [session, setSession] = useState<AdminSession | undefined>(undefined)
  const [isRestoring, setIsRestoring] = useState(true)
  const epoch = useRef(0)

  const clearSession = useCallback(() => {
    // Cached admin data belongs to the previous identity and must never survive logout.
    sessionRef.current = undefined
    epoch.current += 1
    setIsRestoring(false)
    setSession(undefined)
    queryClient.clear()
  }, [queryClient])

  const establishSession = useCallback((nextSession: AdminSession) => {
    epoch.current += 1
    setIsRestoring(false)
    if (isIdentityChange(sessionRef.current?.identity, nextSession.identity)) {
      // A new verified identity must not inherit the prior administrator's cached data.
      queryClient.clear()
    }
    sessionRef.current = nextSession
    setSession(nextSession)
  }, [queryClient])

  useEffect(() => {
    if (epoch.current !== 0) return
    let active = true
    const startedAt = epoch.current
    void restoreAdminSession().then((restored) => {
      if (active && epoch.current === startedAt) establishSession(restored)
    }).catch(() => {
      if (active && epoch.current === startedAt) clearSession()
    })
    return () => { active = false }
  }, [clearSession, establishSession])

  const value = useMemo<AdminAuthContextValue>(() => ({
    accessToken: session?.accessToken,
    clearSession,
    establishSession,
    identity: session?.identity,
    isAuthenticated: session !== undefined,
    isRestoring,
    logout: clearSession,
  }), [clearSession, establishSession, session, isRestoring])

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export function useAdminAuth() {
  const context = useContext(AdminAuthContext)
  if (!context) {
    throw new Error('useAdminAuth must be used within AdminAuthProvider')
  }
  return context
}
