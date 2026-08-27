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
  const [logoutWarning, setLogoutWarning] = useState<string>()
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
      .catch((error: unknown) => {
        if (error instanceof AuthApiError && (error.code === 'NETWORK_ERROR' || error.code === 'UNKNOWN_ERROR')) {
          sessionRef.current = undefined
          setSession(undefined)
          setStatus('identity-error')
          return undefined
        }
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
    setLogoutWarning(undefined)
    try {
      await establishSession(access)
    } catch (error) {
      clearSession()
      throw error
    }
  }, [clearSession, establishSession, queryClient])

  const retryBootstrap = useCallback(async () => {
    setStatus('bootstrapping')
    await refresh()
  }, [refresh])

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
      setLogoutWarning(undefined)
      return true
    } catch (error) {
      if (error instanceof AuthApiError) {
        setLogoutWarning('退出请求未能由服务器确认；此设备已退出，其他设备的会话状态可能仍有效。')
        return false
      }
      setLogoutWarning('退出请求未能由服务器确认；此设备已退出，其他设备的会话状态可能仍有效。')
      return false
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(() => ({
    login,
    logout,
    logoutWarning,
    request,
    retryBootstrap,
    status,
    user: session?.user,
  }), [login, logout, logoutWarning, request, retryBootstrap, session?.user, status])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
