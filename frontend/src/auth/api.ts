const apiBaseUrl = 'http://127.0.0.1:8000/api/v1'

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

type LoginResponse = {
  access_token: string
  expires_in: number
  token_type: 'bearer'
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    })
  } catch {
    throw new AuthApiError('NETWORK_ERROR')
  }

  const body = (await response.json().catch(() => ({}))) as T & ApiErrorBody
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

export function loginAccount(payload: { email: string; password: string }) {
  return requestJson<LoginResponse>('/auth/login', {
    body: JSON.stringify(payload),
    method: 'POST',
  })
}
