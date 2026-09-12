const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

function resolveApiBaseUrl(value: string | undefined): string {
  if (!value) {
    // Production deployments may keep the API behind the SPA's same-origin proxy.
    return '/api/v1'
  }

  if (value.startsWith('/')) {
    if (value.startsWith('//')) {
      throw new Error('VITE_API_BASE_URL must be a same-origin path or an HTTP(S) URL.')
    }
    return value.replace(/\/+$/, '') || '/'
  }

  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error('VITE_API_BASE_URL must be a same-origin path or an HTTP(S) URL.')
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('VITE_API_BASE_URL must use HTTP(S).')
  }
  if (import.meta.env.PROD && parsed.protocol !== 'https:') {
    throw new Error('Production VITE_API_BASE_URL must use HTTPS.')
  }
  return parsed.toString().replace(/\/$/, '')
}

const apiBaseUrl = resolveApiBaseUrl(configuredApiBaseUrl)

type ApiErrorBody = {
  error?: {
    code?: string
    request_id?: string
    retry_after?: number
  }
}

export class AuthApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly requestId?: string,
    public readonly retryAfter?: number,
  ) {
    super(code)
  }
}

export type PendingVerificationContext = {
  expires_at: string
  masked_email: string
  resend_available_at: string
}

type CodeDispatchResponse = PendingVerificationContext & {
  status: 'CODE_DISPATCH_ACCEPTED'
}

type VerificationSuccessResponse = {
  next_action: 'login'
  status: 'EMAIL_VERIFIED'
}

type RecoveryCodeVerifiedResponse = {
  status: 'RECOVERY_CODE_VERIFIED'
}

type PasswordResetResponse = {
  message: '密码已更新，请重新登录。'
  status: 'PASSWORD_RESET'
}

type LoginResponse = {
  access_token: string
  expires_in: number
  token_type: 'bearer'
}

export type CurrentUser = {
  id: string
  email: string
  email_verified_at: string | null
  is_active: boolean
  role: string
}

export type LoginSession = LoginResponse

export type AuthSessionSummary = {
  created_at: string
  device_label: string | null
  expires_at: string
  id: string
  is_current: boolean
  last_seen_at: string
  revoked_at: string | null
}

export function apiUrl(path: string) {
  if (!path.startsWith('/')) {
    throw new Error('API paths must begin with a slash.')
  }
  return `${apiBaseUrl}${path}`
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  const signal = init?.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000)

  try {
    response = await fetch(apiUrl(path), {
      ...init,
      signal,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    })
  } catch {
    throw new AuthApiError('NETWORK_ERROR')
  }

  const body = (await response.json().catch(() => {
    if (signal.aborted) throw new AuthApiError('NETWORK_ERROR')
    return {}
  })) as T & ApiErrorBody
  if (!response.ok) {
    const error = body.error
    throw new AuthApiError(
      error?.code ?? 'UNKNOWN_ERROR',
      error?.request_id,
      error?.retry_after,
    )
  }

  return body
}

export function registerAccount(payload: { email: string; password: string }) {
  return requestJson<CodeDispatchResponse>('/auth/register', {
    body: JSON.stringify(payload),
    method: 'POST',
  })
}

export function getRegistrationContext() {
  return requestJson<PendingVerificationContext>('/auth/register/context', { method: 'GET' })
}

export function verifyRegistration(code: string) {
  return requestJson<VerificationSuccessResponse>('/auth/register/verify', {
    body: JSON.stringify({ code }),
    method: 'POST',
  })
}

export function resendRegistrationCode() {
  return requestJson<CodeDispatchResponse>('/auth/register/resend', { method: 'POST' })
}

export function requestPasswordRecovery(email: string) {
  return requestJson<{ status: 'RECOVERY_CODE_DISPATCH_ACCEPTED' }>('/auth/password-recovery/forgot', {
    body: JSON.stringify({ email }),
    method: 'POST',
  })
}

export function verifyRecoveryCode(code: string) {
  return requestJson<RecoveryCodeVerifiedResponse>('/auth/password-recovery/verify', {
    body: JSON.stringify({ code }),
    method: 'POST',
  })
}

export function resetPassword(payload: { code: string; newPassword: string }) {
  return requestJson<PasswordResetResponse>('/auth/password-recovery/reset', {
    body: JSON.stringify({ code: payload.code, new_password: payload.newPassword }),
    method: 'POST',
  })
}

export function loginAccount(payload: { email: string; password: string }) {
  return requestJson<LoginResponse>('/auth/login', {
    body: JSON.stringify(payload),
    method: 'POST',
  })
}

export function refreshAccessToken() {
  return requestJson<LoginSession>('/auth/refresh', { method: 'POST' })
}

export function getCurrentUser(accessToken: string) {
  return requestJson<CurrentUser>('/users/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
    method: 'GET',
  })
}

export async function requestWithAccess(path: string, accessToken: string, init?: RequestInit) {
  try {
    return await fetch(apiUrl(path), {
      ...init,
      credentials: 'include',
      headers: {
        ...init?.headers,
        Authorization: `Bearer ${accessToken}`,
      },
    })
  } catch {
    throw new AuthApiError('NETWORK_ERROR')
  }
}

export async function logoutCurrentSession(accessToken: string) {
  const response = await requestWithAccess('/auth/logout', accessToken, { method: 'POST' })
  if (!response.ok && response.status !== 401) {
    throw new AuthApiError('LOGOUT_FAILED')
  }
}
