import { z } from 'zod'

const authorizationStatusSchema = z.enum(['authorized', 'pending', 'revoked'])

const requiredText = (maximum: number) => z.string().trim().min(1).max(maximum)
const nutrient = (maximum: number) => z.coerce.number().finite().min(0).max(maximum)

export const catalogDraftFormSchema = z.object({
  canonical_name: requiredText(200),
  aliases: z.string().trim().min(1).max(500),
  energy_kcal_per_100g: nutrient(10_000),
  protein_g_per_100g: nutrient(1_000),
  fat_g_per_100g: nutrient(1_000),
  carbohydrate_g_per_100g: nutrient(1_000),
  source_name: requiredText(120),
  source_url: z.string().trim().url().max(500).refine((value) => new URL(value).protocol === 'https:', '来源链接必须使用 HTTPS。'),
  authorization_status: authorizationStatusSchema,
  reason: requiredText(500),
}).strict().superRefine(({ aliases }, context) => {
  const normalized = aliases.split(',').map((alias) => alias.trim()).filter(Boolean)
  if (!normalized.length || new Set(normalized.map((alias) => alias.toLocaleLowerCase())).size !== normalized.length) {
    context.addIssue({ code: 'custom', message: '别名必须非空且不重复。', path: ['aliases'] })
  }
})

export type CatalogDraftFormValues = z.input<typeof catalogDraftFormSchema>

export const catalogDraftSchema = z.object({
  id: z.string().uuid(),
  canonical_name: z.string(),
  aliases: z.array(z.string()),
  energy_kcal_per_100g: z.union([z.string(), z.number()]),
  protein_g_per_100g: z.union([z.string(), z.number()]),
  fat_g_per_100g: z.union([z.string(), z.number()]),
  carbohydrate_g_per_100g: z.union([z.string(), z.number()]),
  source_name: z.string(),
  source_url: z.string().url(),
  authorization_status: authorizationStatusSchema,
  revision: z.number().int().positive(),
}).strict()

export type CatalogDraft = z.infer<typeof catalogDraftSchema>

const catalogDraftDiffFieldSchema = z.enum([
  'canonical_name', 'aliases', 'energy_kcal_per_100g', 'protein_g_per_100g',
  'fat_g_per_100g', 'carbohydrate_g_per_100g', 'source_name', 'source_url', 'authorization_status',
])

export const catalogDraftPreviewSchema = z.object({
  draft_id: z.string().uuid().nullable(),
  base_revision: z.number().int().nonnegative(),
  field_diffs: z.array(z.object({
    field: catalogDraftDiffFieldSchema,
    before: z.string().nullable(),
    after: z.string(),
  }).strict()).min(1),
  impact_categories: z.array(z.enum([
    'catalog_identity', 'nutrition_per_100g', 'source_evidence', 'authorization_status',
  ])).min(1),
}).strict()

export type CatalogDraftPreview = z.infer<typeof catalogDraftPreviewSchema>

const lifecycleChangeSchema = z.enum(['added', 'modified', 'removed', 'unchanged'])

const lifecyclePreviewSchema = z.object({
  draft: catalogDraftSchema,
  publication: z.object({
    id: z.string().uuid(),
    draft_revision: z.number().int().positive(),
    eligibility: z.enum(['eligible', 'disqualified']),
    related_version: z.string().min(1).max(120),
  }).strict().nullable(),
  field_diffs: z.array(z.object({
    field: catalogDraftDiffFieldSchema,
    before: z.string().nullable(),
    after: z.string().nullable(),
    change: lifecycleChangeSchema,
  }).strict()).min(1),
  impact: z.object({
    affected_catalog_items: z.number().int().nonnegative(),
    description: z.string().min(1).max(500),
  }).strict(),
}).strict()

export type CatalogLifecyclePreview = z.infer<typeof lifecyclePreviewSchema>

const catalogPublicationSchema = z.object({
  id: z.string().uuid(),
  draft_id: z.string().uuid(),
  draft_revision: z.number().int().positive(),
  content_hash: z.string().regex(/^[a-f0-9]{64}$/),
  eligibility: z.enum(['eligible', 'disqualified']),
}).strict()

export type CatalogPublication = z.infer<typeof catalogPublicationSchema>

const auditDiffValueSchema = z.union([z.string(), z.number(), z.boolean(), z.null()])
const auditEventSchema = z.object({
  id: z.string().uuid(),
  actor_identifier: z.string().min(1).max(320),
  occurred_at: z.string().datetime({ offset: true }),
  action: z.string().min(1).max(80),
  object_type: z.string().min(1).max(80),
  object_id: z.string().min(1).max(160),
  reason: z.string().min(1).max(500),
  before: z.record(z.string(), auditDiffValueSchema),
  after: z.record(z.string(), auditDiffValueSchema),
  related_version: z.string().min(1).max(120).nullable(),
  command_key: z.string().min(1).max(160),
}).strict()

const auditPageSchema = z.object({
  items: z.array(auditEventSchema),
  next_cursor: z.string().min(16).max(500).nullable(),
}).strict()

export type CatalogAuditEvent = z.infer<typeof auditEventSchema>

export const lifecycleReasonSchema = z.object({
  reason: z.string().trim().min(1, '请说明此次变更原因。').max(500),
}).strict()

export type CatalogLifecycleAction = 'review' | 'publish' | 'disqualify'

export class CatalogApiError extends Error {
  constructor(readonly status: 401 | 403 | 404 | 409 | 422 | 500) {
    super(`Catalog admin API request failed with ${status}`)
  }
}

function toCommand(values: CatalogDraftFormValues) {
  const parsed = catalogDraftFormSchema.parse(values)
  return {
    ...parsed,
    aliases: parsed.aliases.split(',').map((alias) => alias.trim()),
  }
}

function toPreviewCommand(values: CatalogDraftFormValues, draftId?: string) {
  const { reason: _reason, ...candidate } = toCommand(values)
  return { ...candidate, draft_id: draftId ?? null }
}

async function sendCatalogRequest(path: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, init)
  if (!response.ok) {
    const status = [401, 403, 404, 409, 422].includes(response.status) ? response.status : 500
    throw new CatalogApiError(status as CatalogApiError['status'])
  }
  return response.json()
}

function requestHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }
}

function commandHeaders(accessToken: string, idempotencyKey: string, revision?: number) {
  return {
    ...requestHeaders(accessToken),
    'Idempotency-Key': idempotencyKey,
    ...(revision ? { 'If-Match': String(revision) } : {}),
  }
}

export function createCatalogDraft(accessToken: string, values: CatalogDraftFormValues, idempotencyKey: string) {
  return sendCatalogRequest('/catalog-drafts', {
    body: JSON.stringify(toCommand(values)),
    headers: commandHeaders(accessToken, idempotencyKey),
    method: 'POST',
  }).then(catalogDraftSchema.parse)
}

export function patchCatalogDraft(accessToken: string, draft: CatalogDraft, values: CatalogDraftFormValues, idempotencyKey: string, expectedRevision: number) {
  return sendCatalogRequest(`/catalog-drafts/${draft.id}`, {
    body: JSON.stringify(toCommand(values)),
    headers: commandHeaders(accessToken, idempotencyKey, expectedRevision),
    method: 'PATCH',
  }).then(catalogDraftSchema.parse)
}

export function previewCatalogDraft(accessToken: string, values: CatalogDraftFormValues, draftId?: string) {
  return sendCatalogRequest('/catalog-drafts/preview', {
    body: JSON.stringify(toPreviewCommand(values, draftId)),
    headers: requestHeaders(accessToken),
    method: 'POST',
  }).then(catalogDraftPreviewSchema.parse)
}

export function readCatalogDraft(accessToken: string, draftId: string) {
  return sendCatalogRequest(`/catalog-drafts/${draftId}`, {
    headers: requestHeaders(accessToken),
    method: 'GET',
  }).then(catalogDraftSchema.parse)
}

/** A server-derived projection is mandatory; this client never generates a trusted diff. */
export function readCatalogLifecyclePreview(accessToken: string, draftId: string, signal?: AbortSignal) {
  return sendCatalogRequest(`/catalog-drafts/${draftId}/lifecycle-preview`, {
    headers: requestHeaders(accessToken),
    method: 'GET', signal,
  }).then(lifecyclePreviewSchema.parse)
}

export function submitCatalogLifecycleCommand(
  accessToken: string,
  preview: CatalogLifecyclePreview,
  action: CatalogLifecycleAction,
  reason: string,
  idempotencyKey: string,
  signal?: AbortSignal,
) {
  const command = { ...lifecycleReasonSchema.parse({ reason }), confirm: true as const }
  const path = action === 'disqualify'
    ? `/catalog-publications/${preview.publication?.id ?? ''}/disqualifications`
    : `/catalog-drafts/${preview.draft.id}/${action}`

  if (action === 'disqualify' && !preview.publication) {
    throw new CatalogApiError(409)
  }

  return sendCatalogRequest(path, {
    body: JSON.stringify(command),
    headers: commandHeaders(accessToken, idempotencyKey, action === 'disqualify' ? undefined : preview.draft.revision),
    method: 'POST', signal,
  }).then(catalogPublicationSchema.parse)
}

export function listCatalogAuditEvents(accessToken: string) {
  return sendCatalogRequest('/audit?limit=20', {
    headers: requestHeaders(accessToken),
    method: 'GET',
  }).then(auditPageSchema.parse)
}

export const catalogFilterSchema = z.object({
  search: z.string().trim().max(200), source: z.string().trim().max(120),
  authorization_status: z.union([authorizationStatusSchema, z.literal('')]),
})
export type CatalogFilters = z.infer<typeof catalogFilterSchema>
export const emptyCatalogFilters: CatalogFilters = { search: '', source: '', authorization_status: '' }

const catalogListSchema = z.object({
  items: z.array(catalogDraftSchema.extend({ updated_at: z.string().datetime({ offset: true }) }).strict()),
  total: z.number().int().nonnegative(), page: z.number().int().positive(), page_size: z.number().int().positive().max(100),
}).strict()

function catalogQuery(filters: CatalogFilters, page = 1, pageSize = 20) {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  Object.entries(catalogFilterSchema.parse(filters)).forEach(([key, value]) => { if (value) query.set(key, value) })
  return query.toString()
}

export function listCatalogDrafts(accessToken: string, filters: CatalogFilters, page: number, pageSize: number) {
  return sendCatalogRequest(`/catalog-drafts?${catalogQuery(filters, page, pageSize)}`, {
    headers: requestHeaders(accessToken), method: 'GET',
  }).then(catalogListSchema.parse)
}

const csvPreviewSchema = z.object({
  total_rows: z.number().int().nonnegative(), valid_rows: z.number().int().nonnegative(),
  rows: z.array(catalogDraftSchema.omit({ id: true, revision: true }).extend({ reason: z.string() }).strict()),
  errors: z.array(z.object({ row: z.number().int().positive(), field: z.string(), message: z.string() }).strict()),
}).strict()
export type CatalogCsvPreview = z.infer<typeof csvPreviewSchema>

export function previewCatalogCsv(accessToken: string, csvText: string) {
  return sendCatalogRequest('/catalog-drafts/import-preview', {
    method: 'POST', headers: requestHeaders(accessToken), body: JSON.stringify({ csv_text: csvText }),
  }).then(csvPreviewSchema.parse)
}

export function importCatalogCsv(accessToken: string, csvText: string, reason: string, idempotencyKey: string) {
  return sendCatalogRequest('/catalog-drafts/import', {
    method: 'POST', headers: commandHeaders(accessToken, idempotencyKey),
    body: JSON.stringify({ csv_text: csvText, ...lifecycleReasonSchema.parse({ reason }), confirm: true }),
  }).then(z.object({ imported_count: z.number().int().nonnegative(), draft_ids: z.array(z.string().uuid()) }).strict().parse)
}

export async function downloadCatalogCsv(accessToken: string, filters: CatalogFilters, template = false) {
  const path = template ? '/catalog-drafts/template' : `/catalog-drafts/export?${catalogQuery(filters)}`
  const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, { headers: requestHeaders(accessToken) })
  if (!response.ok) {
    throw new CatalogApiError(([401, 403, 422].includes(response.status) ? response.status : 500) as CatalogApiError['status'])
  }
  if (!response.headers.get('Content-Type')?.startsWith('text/csv')) throw new CatalogApiError(500)
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = template ? '营养目录导入模板.csv' : '营养目录.csv'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  // Allow the browser to consume the blob before releasing its object URL.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
