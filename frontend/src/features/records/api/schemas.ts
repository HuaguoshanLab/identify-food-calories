import { z } from 'zod'
import { mealSlotSchema } from './mealMetadata'

export const mealRecordItemSchema = z.object({ id: z.string().uuid(), position: z.number().int(), display_name: z.string(), nutrition_catalog_version: z.string(), grams: z.string(), energy_kcal: z.string(), protein_g: z.string(), fat_g: z.string(), carbohydrate_g: z.string(), is_estimated: z.boolean() }).strict()
export const mealRecordSchema = z.object({ id: z.string().uuid(), meal_slot: mealSlotSchema.nullable().default(null), consumed_at: z.string(), consumed_time_zone: z.string().nullable(), consumed_local_date: z.string().nullable(), local_date_source: z.string().nullable(), nutrition_catalog_version: z.string(), calculation_version: z.string(), energy_kcal: z.string(), protein_g: z.string(), fat_g: z.string(), carbohydrate_g: z.string(), created_at: z.string(), updated_at: z.string(), items: z.array(mealRecordItemSchema) }).strict()
export type MealRecord = z.infer<typeof mealRecordSchema>
