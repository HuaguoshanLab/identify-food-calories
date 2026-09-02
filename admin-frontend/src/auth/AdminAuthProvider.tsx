import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react'

export type AdminIdentity = Readonly<{
  id: string
  role: 'admin'
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
  logout: () => void
}>

const AdminAuthContext = createContext<AdminAuthContextValue | undefined>(undefined)

function isIdentityChange(previous: AdminIdentity | undefined, next: AdminIdentity) {
  return previous?.id !== next.id || previous.role !== next.role
}

export function AdminAuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient()
  const sessionRef = useRef<AdminSession | undefined>(undefined)
  const [session, setSession] = useState<AdminSession | undefined>(undefined)

  const clearSession = useCallback(() => {
    // Cached admin data belongs to the previous identity and must never survive logout.
    sessionRef.current = undefined
    setSession(undefined)
    queryClient.clear()
  }, [queryClient])

  const establishSession = useCallback((nextSession: AdminSession) => {
    if (isIdentityChange(sessionRef.current?.identity, nextSession.identity)) {
      // A new verified identity must not inherit the prior administrator's cached data.
      queryClient.clear()
    }
    sessionRef.current = nextSession
    setSession(nextSession)
  }, [queryClient])

  const value = useMemo<AdminAuthContextValue>(() => ({
    accessToken: session?.accessToken,
    clearSession,
    establishSession,
    identity: session?.identity,
    isAuthenticated: session !== undefined,
    logout: clearSession,
  }), [clearSession, establishSession, session])

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export function useAdminAuth() {
  const context = useContext(AdminAuthContext)
  if (!context) {
    throw new Error('useAdminAuth must be used within AdminAuthProvider')
  }
  return context
}
