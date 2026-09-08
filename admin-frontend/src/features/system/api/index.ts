import { z } from 'zod'

const roleSchema = z.enum(['user', 'admin'])
const userSchema = z.object({
  id: z.string().uuid(), email: z.string().email(), email_verified_at: z.string().datetime({ offset: true }).nullable(),
  is_active: z.boolean(), role: roleSchema, created_at: z.string().datetime({ offset: true }), updated_at: z.string().datetime({ offset: true }),
}).strict()
const userPageSchema = z.object({ items: z.array(userSchema), total: z.number().int().nonnegative(), page: z.number().int().positive(), page_size: z.number().int().positive() }).strict()
const roleItemSchema = z.object({ role: roleSchema, label: z.string(), description: z.string(), account_count: z.number().int().nonnegative(), permissions: z.array(z.string()) }).strict()
const roleListSchema = z.object({ items: z.array(roleItemSchema) }).strict()
const roleChangeSchema = z.object({ audit_id: z.string().uuid(), target_user_id: z.string().uuid(), before_role: roleSchema, after_role: roleSchema, occurred_at: z.string().datetime({ offset: true }) }).strict()

export type AdminUser = z.infer<typeof userSchema>
export type AdminRole = z.infer<typeof roleItemSchema>
export type UserFilters = Readonly<{ search?: string, role?: '' | 'user' | 'admin', status?: '' | 'active' | 'inactive' | 'unverified', page?: number, pageSize?: number }>

export class SystemApiError extends Error {
  constructor(readonly status: 401 | 403 | 404 | 409 | 500, readonly detail?: string) { super(detail ?? `System API request failed with ${status}`) }
}

async function request(path: string, accessToken: string, init?: RequestInit) {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, { ...init, headers: { Authorization: `Bearer ${accessToken}`, ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers } })
  if (!response.ok) {
    let detail: string | undefined
    try { detail = z.object({ detail: z.string() }).parse(await response.json()).detail } catch { detail = undefined }
    const status = [401, 403, 404, 409].includes(response.status) ? response.status : 500
    throw new SystemApiError(status as SystemApiError['status'], detail)
  }
  return response.json()
}

export function readUsers(accessToken: string, filters: UserFilters) {
  const params = new URLSearchParams({ page: String(filters.page ?? 1), page_size: String(filters.pageSize ?? 20) })
  if (filters.search) params.set('search', filters.search)
  if (filters.role) params.set('role', filters.role)
  if (filters.status) params.set('status', filters.status)
  return request(`/users?${params}`, accessToken).then(userPageSchema.parse)
}

export function readRoles(accessToken: string) { return request('/roles', accessToken).then(roleListSchema.parse) }

export function changeRole(accessToken: string, userId: string, role: 'user' | 'admin', reason: string) {
  return request(`/users/${userId}/role`, accessToken, { method: 'PATCH', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ role, reason, confirm: true }) }).then(roleChangeSchema.parse)
}
