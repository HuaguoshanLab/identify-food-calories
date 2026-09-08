import { z } from 'zod'

const mealSlotSchema = z.enum(['breakfast', 'lunch', 'dinner', 'snack'])
const candidateSchema = z.object({
  id: z.string().uuid(),
  catalog_food_name: z.string().min(1),
  meal_slot: mealSlotSchema,
  portion_grams: z.string(),
  portion_description: z.string(),
  method_tags: z.array(z.string()),
  flavour_tags: z.array(z.string()),
  status: z.enum(['pending', 'enabled', 'disabled']),
  revision: z.number().int().positive(),
}).strict()
const listResponseSchema = z.object({ items: z.array(candidateSchema), total: z.number().int().nonnegative(), page: z.number().int().positive(), page_size: z.number().int().positive() }).strict()
const previewSchema = z.object({
  total_rows: z.number().int().nonnegative(), valid_rows: z.number().int().nonnegative(),
  rows: z.array(z.object({ catalog_food_name: z.string(), meal_slot: mealSlotSchema, portion_grams: z.string(), portion_description: z.string(), method_tags: z.array(z.string()), flavour_tags: z.array(z.string()), status: z.enum(['pending', 'disabled']) }).strict()),
  errors: z.array(z.object({ row: z.number().int().positive(), field: z.string(), message: z.string() }).strict()),
}).strict()

export type RecipeCandidate = z.infer<typeof candidateSchema>
export type RecipeCandidateCsvPreview = z.infer<typeof previewSchema>
export type RecipeCandidateOperation = 'enable' | 'disable' | 'delete'

export class RecipeCandidateApiError extends Error {
  constructor(readonly status: number, readonly detail?: string) { super(`recipe candidate request failed: ${status}`) }
}

async function request(input: string, init: RequestInit) {
  const response = await fetch(input, init)
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined)
    const detail = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string' ? body.detail : undefined
    throw new RecipeCandidateApiError(response.status, detail)
  }
  return response
}

function authorized(token: string, extra: HeadersInit = {}) {
  return { Authorization: `Bearer ${token}`, ...extra }
}

export async function listRecipeCandidates(token: string, page: number, pageSize: number) {
  const response = await request(`/api/v1/admin/recipe-candidates?page=${page}&page_size=${pageSize}`, { headers: authorized(token) })
  return listResponseSchema.parse(await response.json())
}

export async function previewRecipeCandidates(token: string, csvText: string) {
  const response = await request('/api/v1/admin/recipe-candidates/import-preview', { method: 'POST', headers: authorized(token, { 'Content-Type': 'application/json' }), body: JSON.stringify({ csv_text: csvText }) })
  return previewSchema.parse(await response.json())
}

export async function importRecipeCandidates(token: string, csvText: string, reason: string, idempotencyKey: string) {
  const response = await request('/api/v1/admin/recipe-candidates/import', { method: 'POST', headers: authorized(token, { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey }), body: JSON.stringify({ csv_text: csvText, reason, confirm: true }) })
  return z.object({ imported_count: z.number().int().nonnegative() }).passthrough().parse(await response.json())
}

export async function changeRecipeCandidates(token: string, operation: RecipeCandidateOperation, ids: string[], reason: string, idempotencyKey: string) {
  await request(`/api/v1/admin/recipe-candidates/${operation}`, { method: 'POST', headers: authorized(token, { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey }), body: JSON.stringify({ ids, reason, confirm: true }) })
}

export async function downloadRecipeCandidates(token: string, template = false) {
  const response = await request(`/api/v1/admin/recipe-candidates/${template ? 'template' : 'export'}`, { headers: authorized(token) })
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = template ? '菜谱候选导入模板.csv' : '菜谱候选.csv'
  link.click()
  URL.revokeObjectURL(url)
}
