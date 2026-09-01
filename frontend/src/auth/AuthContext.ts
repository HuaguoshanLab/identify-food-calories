import { createContext } from 'react'

import type { CurrentUser } from './api'

export type AuthenticationStatus = 'bootstrapping' | 'authenticated' | 'identity-error' | 'unauthenticated'

/**
 * AuthProvider owns the authenticated browser request capability. Domain API
 * modules receive it as a dependency, so they never reach into another feature
 * merely to reuse a transport type.
 */
export type AuthenticatedRequest = (path: string, init?: RequestInit) => Promise<Response>

export type AuthContextValue = {
  login: (credentials: { email: string; password: string }) => Promise<void>
  logout: () => Promise<boolean>
  logoutWarning?: string
  request: AuthenticatedRequest
  retryBootstrap: () => Promise<void>
  status: AuthenticationStatus
  user?: CurrentUser
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
