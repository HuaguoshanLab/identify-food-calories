import { z } from 'zod'

export const purposeLabels = {"whole_meal": "整餐候选", "component": "组合组成项", "both": "两者皆可", "unknown": "待确认"} as const
const purposeSchema = z.enum(["whole_meal", "component", "both", "unknown"])
export const roleLabels = {"staple": "主食", "protein": "蛋白质菜", "vegetable": "蔬菜菜肴", "mixed_main": "混合主餐", "fruit": "水果", "dairy": "奶及替代品", "nuts_seeds": "坚果种子", "soup": "汤羹", "drink": "饮品", "side": "其他配菜", "unknown": "待确认"} as const
const roleSchema = z.enum(["staple", "protein", "vegetable", "mixed_main", "fruit", "dairy", "nuts_seeds", "soup", "drink", "side", "unknown"])
export const ingredientTagLabels = {"rice": "米及制品", "wheat": "麦及制品", "other_grain": "其他谷物", "tuber": "薯类", "pulses": "杂豆", "livestock": "畜肉", "poultry": "禽肉", "fish": "鱼类", "shellfish": "虾蟹贝类", "egg": "蛋类", "offal": "动物内脏", "soy": "大豆及豆制品", "other_plant_protein": "其他植物蛋白制品", "leafy_veg": "叶菜", "stem_flower_veg": "花茎类", "fruit_veg": "瓜茄类", "root_veg": "根菜", "mushroom": "菌菇", "algae": "藻类", "fruit": "水果", "dairy": "奶及奶制品", "plant_drink": "植物替代饮品", "nuts": "坚果", "seeds": "种子"} as const
const ingredientTagSchema = z.enum(["rice", "wheat", "other_grain", "tuber", "pulses", "livestock", "poultry", "fish", "shellfish", "egg", "offal", "soy", "other_plant_protein", "leafy_veg", "stem_flower_veg", "fruit_veg", "root_veg", "mushroom", "algae", "fruit", "dairy", "plant_drink", "nuts", "seeds"])
export const classificationSchema = z.object({ version: z.literal('recipe-classification.v1'), purpose: purposeSchema, role: roleSchema, ingredient_tags: z.array(ingredientTagSchema), evidence: z.string(), basis: z.enum(['name_only', 'name_and_legacy_role', 'admin_review']) }).strict()
const classificationEntrySchema = z.object({ id: z.string().uuid(), revision: z.number().int().positive(), catalog_food_name: z.string(), classification: classificationSchema }).strict()
export const classificationPreviewSchema = z.object({ entries: z.array(classificationEntrySchema), skipped_count: z.number().int().nonnegative() }).strict()
export type ClassificationPreview = z.infer<typeof classificationPreviewSchema>

const mealSlotSchema = z.enum(['breakfast', 'lunch', 'dinner', 'snack'])
const candidateSchema = z.object({
  id: z.string().uuid(),
  classification: classificationSchema.nullable().default(null),
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
  rows: z.array(z.object({ catalog_food_name: z.string(), meal_slot: mealSlotSchema, classification: classificationSchema.nullable(), portion_grams: z.string(), portion_description: z.string(), method_tags: z.array(z.string()), flavour_tags: z.array(z.string()), status: z.enum(['pending', 'disabled']) }).strict()),
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

export async function previewClassifications(token: string, ids: string[], reviewUnknown = false) {
  const response = await request('/api/v1/admin/recipe-candidates/classification-preview', { method: 'POST', headers: authorized(token, { 'Content-Type': 'application/json' }), body: JSON.stringify({ ids, review_unknown: reviewUnknown }) })
  return classificationPreviewSchema.parse(await response.json())
}
export async function saveClassifications(token: string, entries: ClassificationPreview['entries'], reason: string, key: string, reviewUnknown = false) {
  const response = await request('/api/v1/admin/recipe-candidates/classification-backfill', { method: 'POST', headers: authorized(token, { 'Content-Type': 'application/json', 'Idempotency-Key': key }), body: JSON.stringify({ entries, reason, confirm: true, review_unknown: reviewUnknown }) })
  return z.object({ changed_count: z.number().int().nonnegative() }).strict().parse(await response.json())
}

export async function reviewClassifications(token: string, entries: ClassificationPreview['entries'], reason: string, key: string) {
  const payload = { entries: z.array(classificationEntrySchema).min(1).max(1000).parse(entries), reason: z.string().trim().min(1).max(500).parse(reason), confirm: true }
  const response = await request('/api/v1/admin/recipe-candidates/classification-review', { method: 'POST', headers: authorized(token, { 'Content-Type': 'application/json', 'Idempotency-Key': key }), body: JSON.stringify(payload) })
  return z.object({ changed_count: z.number().int().nonnegative() }).strict().parse(await response.json())
}
