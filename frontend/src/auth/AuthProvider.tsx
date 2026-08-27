import { useQueryClient } from '@tanstack/react-query'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react'

import {
  AuthApiError,
  type CurrentUser,
  type LoginSession,
  getCurrentUser,
  loginAccount,
  logoutCurrentSession,
  refreshAccessToken,
  requestWithAccess,
} from './api'
import { AuthContext, type AuthContextValue, type AuthenticationStatus } from './AuthContext'

type AuthenticatedSession = {
  accessToken: string
  user: CurrentUser
}

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<AuthenticatedSession | undefined>(undefined)
  const [status, setStatus] = useState<AuthenticationStatus>('bootstrapping')
  const sessionRef = useRef<AuthenticatedSession | undefined>(undefined)
  const refreshFlight = useRef<Promise<AuthenticatedSession | undefined> | undefined>(undefined)
  const bootstrapped = useRef(false)

  const clearSession = useCallback(() => {
    sessionRef.current = undefined
    setSession(undefined)
    setStatus('unauthenticated')
    queryClient.clear()
  }, [queryClient])

  const establishSession = useCallback(async (access: LoginSession) => {
    // JWT only authorizes this request. The API response is the sole browser identity.
    const user = await getCurrentUser(access.access_token)
    const next = { accessToken: access.access_token, user }
    sessionRef.current = next
    setSession(next)
    setStatus('authenticated')
    return next
  }, [])

  const refresh = useCallback(() => {
    if (refreshFlight.current) {
      return refreshFlight.current
    }

    const flight = refreshAccessToken()
      .then(establishSession)
      .catch(() => {
        clearSession()
        return undefined
      })
      .finally(() => {
        refreshFlight.current = undefined
      })
    refreshFlight.current = flight
    return flight
  }, [clearSession, establishSession])

  useEffect(() => {
    if (bootstrapped.current) {
      return
    }
    bootstrapped.current = true
    void refresh()
  }, [refresh])

  const login = useCallback(async (credentials: { email: string; password: string }) => {
    const access = await loginAccount(credentials)
    // Clear user-scoped cache before publishing a possibly different account.
    queryClient.clear()
    try {
      await establishSession(access)
    } catch (error) {
      clearSession()
      throw error
    }
  }, [clearSession, establishSession, queryClient])

  const request = useCallback(async (path: string, init?: RequestInit) => {
    const active = sessionRef.current
    if (!active) {
      return new Response(null, { status: 401 })
    }

    const firstResponse = await requestWithAccess(path, active.accessToken, init)
    if (firstResponse.status !== 401) {
      return firstResponse
    }

    const refreshed = await refresh()
    if (!refreshed) {
      return firstResponse
    }
    // One replay is intentional: a broken or revoked session must not loop forever.
    return requestWithAccess(path, refreshed.accessToken, init)
  }, [refresh])

  const logout = useCallback(async () => {
    const accessToken = sessionRef.current?.accessToken
    // Local state must be cleared even when the network cannot confirm revocation.
    clearSession()
    if (!accessToken) {
      return true
    }
    try {
      await logoutCurrentSession(accessToken)
      return true
    } catch (error) {
      if (error instanceof AuthApiError) {
        return false
      }
      return false
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(() => ({
    login,
    logout,
    request,
    status,
    user: session?.user,
  }), [login, logout, request, session?.user, status])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
