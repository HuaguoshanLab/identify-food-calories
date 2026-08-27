import { createContext } from 'react'

import type { CurrentUser } from './api'

export type AuthenticationStatus = 'bootstrapping' | 'authenticated' | 'unauthenticated'

export type AuthContextValue = {
  login: (credentials: { email: string; password: string }) => Promise<void>
  logout: () => Promise<boolean>
  request: (path: string, init?: RequestInit) => Promise<Response>
  status: AuthenticationStatus
  user?: CurrentUser
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
