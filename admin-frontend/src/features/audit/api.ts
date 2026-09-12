import { z } from 'zod'

const scalarSchema = z.union([z.string().max(500), z.number().finite(), z.boolean(), z.null()])
const auditWireEventSchema = z.object({
  id: z.string().uuid(), actor_identifier: z.string().min(1).max(320), actor_label: z.string().min(1).max(320), occurred_at: z.string().datetime({ offset: true }), action: z.string().min(1).max(80), object_type: z.string().min(1).max(80), object_id: z.string().min(1).max(160), reason: z.string().min(1).max(500), before: z.record(z.string(), scalarSchema), after: z.record(z.string(), scalarSchema), related_version: z.string().max(160).nullable(), command_key: z.string().min(1).max(160),
}).strict()

export const auditPageSchema = z.object({ items: z.array(auditWireEventSchema), next_cursor: z.string().min(16).max(500).nullable() }).strict()
export type AdminAuditEvent = z.infer<typeof auditWireEventSchema>
export type AuditFilterValues = Readonly<{ actor?: string, occurred_after?: string, occurred_before?: string, action?: string, object_type?: string, object_id?: string, reason?: string }>

export class AuditApiError extends Error {
  constructor(readonly status: 401 | 403 | 422 | 500) { super(`Audit API request failed with ${status}`) }
}

function queryString(filters: AuditFilterValues, cursor?: string) {
  const params = new URLSearchParams({ limit: '50' })
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value)
  if (cursor) params.set('cursor', cursor)
  return params.toString()
}

export async function readAudit(accessToken: string, filters: AuditFilterValues, cursor?: string) {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}/audit?${queryString(filters, cursor)}`, { headers: { Authorization: `Bearer ${accessToken}` }, method: 'GET' })
  if (!response.ok) {
    const status = [401, 403, 422].includes(response.status) ? response.status : 500
    throw new AuditApiError(status as AuditApiError['status'])
  }
  return auditPageSchema.parse(await response.json())
}
