import { z } from 'zod'

const reasonSchema = z.object({ reason: z.string().trim().min(1).max(500) }).strict()
const buildSchema = z.object({
  id: z.string().uuid(), vector_space_id: z.string().uuid(), embedding_model: z.string().min(1), embedding_dimension: z.literal(1024), adapter_version: z.string().min(1), retrieval_version: z.string().min(1), snapshot_hash: z.string().regex(/^[a-f0-9]{64}$/), expected_name_count: z.number().int().nonnegative(), pending_count: z.number().int().nonnegative(), failed_count: z.number().int().nonnegative(), completed_count: z.number().int().nonnegative(), status: z.enum(['empty', 'pending', 'processing', 'partial_failure', 'ready']), requested_at: z.string().datetime({ offset: true }), is_active: z.boolean(), activation_ready: z.boolean(),
}).strict()
const backfillSchema = z.object({
  audit_id: z.string().uuid(), publication_count: z.number().int().nonnegative(), name_count: z.number().int().nonnegative(), embedding_job_count: z.number().int().nonnegative(),
}).strict()

export type VectorBuild = z.infer<typeof buildSchema>
export type VectorReason = z.infer<typeof reasonSchema>
// The public build contract pins the configured DashScope adapter.  Activation
// remains separately gated by server-side release evidence.
export const vectorBuildIdentity = { embedding_model: 'text-embedding-v4', embedding_dimension: 1024 as const, adapter_version: 'dashscope-text-embedding-v4-1024.v1', retrieval_version: 'retrieval-06-3-v1' } as const

export class VectorRetrievalApiError extends Error { constructor(readonly status: 401 | 403 | 404 | 409 | 422 | 500) { super(`Vector API failed: ${status}`) } }

function headers(token: string, key?: string) { return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(key ? { 'Idempotency-Key': key } : {}) } }
async function request(path: string, init: RequestInit) { const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, init); if (!response.ok) { const status = [401, 403, 404, 409, 422].includes(response.status) ? response.status : 500; throw new VectorRetrievalApiError(status as VectorRetrievalApiError['status']) }; return response.json() }

export function listVectorBuilds(token: string) { return request('/vector-space-builds', { headers: headers(token), method: 'GET' }).then(z.object({ items: z.array(buildSchema) }).strict().parse) }
export function backfillCatalogSearchIndex(token: string, values: VectorReason, key: string) { return request('/catalog-search-index-backfills', { method: 'POST', headers: headers(token, key), body: JSON.stringify({ ...reasonSchema.parse(values), confirm: true }) }).then(backfillSchema.parse) }
export function createVectorBuild(token: string, values: VectorReason, key: string) { return request('/vector-space-builds', { method: 'POST', headers: headers(token, key), body: JSON.stringify({ ...vectorBuildIdentity, ...reasonSchema.parse(values), confirm: true }) }).then(buildSchema.parse) }
export function retryVectorBuild(token: string, build: VectorBuild, values: VectorReason, key: string) { return request(`/vector-space-builds/${build.id}/retries`, { method: 'POST', headers: headers(token, key), body: JSON.stringify({ ...reasonSchema.parse(values), confirm: true }) }).then(buildSchema.extend({ reset_count: z.number().int().nonnegative() }).strict().parse) }
export function activateVectorBuild(token: string, build: VectorBuild, values: VectorReason, key: string) { return request(`/vector-space-builds/${build.vector_space_id}/activations`, { method: 'POST', headers: headers(token, key), body: JSON.stringify({ build_id: build.id, ...reasonSchema.parse(values), confirm: true }) }).then(z.object({ vector_space_id: z.string().uuid(), build_id: z.string().uuid(), approved_at: z.string().datetime({ offset: true }) }).strict().parse) }
