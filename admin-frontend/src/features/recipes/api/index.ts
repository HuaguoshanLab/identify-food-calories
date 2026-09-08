import { z } from 'zod'

const candidate = z.object({ id: z.string().uuid(), catalog_food_name: z.string().min(1), meal_slot: z.enum(['breakfast', 'lunch', 'dinner', 'snack']), portion_grams: z.string(), portion_description: z.string(), method_tags: z.array(z.string()), flavour_tags: z.array(z.string()), status: z.enum(['pending', 'enabled', 'disabled']), revision: z.number().int().positive() }).strict()
const listResponse = z.object({ items: z.array(candidate), total: z.number().int().nonnegative(), page: z.number().int().positive(), page_size: z.number().int().positive() }).strict()
export type RecipeCandidate = z.infer<typeof candidate>
export async function listRecipeCandidates(token: string) { const response = await fetch('/api/v1/admin/recipe-candidates', { headers: { Authorization: `Bearer ${token}` } }); if (!response.ok) throw new Error(`recipe candidate request failed: ${response.status}`); return listResponse.parse(await response.json()) }
