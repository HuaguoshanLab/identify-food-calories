import { createContext } from 'react'

import type { CurrentUser } from './api'

export type AuthenticationStatus = 'bootstrapping' | 'authenticated' | 'identity-error' | 'unauthenticated'

export type AuthContextValue = {
  login: (credentials: { email: string; password: string }) => Promise<void>
  logout: () => Promise<boolean>
  logoutWarning?: string
  request: (path: string, init?: RequestInit) => Promise<Response>
  retryBootstrap: () => Promise<void>
  status: AuthenticationStatus
  user?: CurrentUser
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
