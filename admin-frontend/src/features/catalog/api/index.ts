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

export class CatalogApiError extends Error {
  constructor(readonly status: 401 | 403 | 404 | 409 | 500) {
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

async function sendCatalogCommand(path: string, init: RequestInit): Promise<CatalogDraft> {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, init)
  if (!response.ok) {
    const status = [401, 403, 404, 409].includes(response.status) ? response.status : 500
    throw new CatalogApiError(status as CatalogApiError['status'])
  }
  return catalogDraftSchema.parse(await response.json())
}

function headers(accessToken: string, idempotencyKey: string, revision?: number) {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    'Idempotency-Key': idempotencyKey,
    ...(revision ? { 'If-Match': String(revision) } : {}),
  }
}

export function createCatalogDraft(accessToken: string, values: CatalogDraftFormValues, idempotencyKey: string) {
  return sendCatalogCommand('/catalog-drafts', {
    body: JSON.stringify(toCommand(values)),
    headers: headers(accessToken, idempotencyKey),
    method: 'POST',
  })
}

export function patchCatalogDraft(accessToken: string, draft: CatalogDraft, values: CatalogDraftFormValues, idempotencyKey: string) {
  return sendCatalogCommand(`/catalog-drafts/${draft.id}`, {
    body: JSON.stringify(toCommand(values)),
    headers: headers(accessToken, idempotencyKey, draft.revision),
    method: 'PATCH',
  })
}
