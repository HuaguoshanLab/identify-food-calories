import { z } from 'zod'

export const accessTokenSchema = z.object({
  access_token: z.string().min(1), token_type: z.literal('bearer'), expires_in: z.number().int().positive(),
}).strict()

export const currentUserSchema = z.object({
  id: z.string().uuid(), email: z.string().email(), email_verified_at: z.string().datetime({ offset: true }).nullable(),
  is_active: z.boolean(), role: z.string(),
}).strict()

async function restore() {
  const response = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include', signal: AbortSignal.timeout(15_000) })
  if (!response.ok) throw new Error('Session restoration unavailable')
  const token = accessTokenSchema.parse(await response.json())
  const me = await fetch('/api/v1/users/me', { headers: { Authorization: `Bearer ${token.access_token}` }, credentials: 'include', signal: AbortSignal.timeout(15_000) })
  if (!me.ok) throw new Error('Identity verification unavailable')
  const identity = currentUserSchema.parse(await me.json())
  if (!identity.is_active) throw new Error('Inactive identity')
  return { accessToken: token.access_token, identity: { id: identity.id } }
}

let restoration: ReturnType<typeof restore> | undefined

export function restoreAdminSession() {
  // StrictMode and concurrent mounts must not rotate the same cookie twice.
  // Across same-origin tabs, serialize rotations rather than broadcasting tokens.
  if (!restoration) {
    const flight = navigator.locks
      ? navigator.locks.request('food-agent-refresh', restore)
      : restore()
    restoration = flight.finally(() => { restoration = undefined })
  }
  return restoration
}
