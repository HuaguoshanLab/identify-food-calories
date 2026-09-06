import { z } from 'zod'

/** meal-slot.v1: suggestions are editable and never reinterpret historical records. */
export const mealSlotSchema = z.enum(['breakfast', 'lunch', 'dinner', 'snack'])
export type MealSlot = z.infer<typeof mealSlotSchema>
export const mealSlotLabels: Record<MealSlot, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }

export function localMealTime(value = new Date()): string {
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`
}

export function suggestedMealSlot(value = new Date()): MealSlot {
  const hour = value.getHours()
  if (hour >= 5 && hour < 11) return 'breakfast'
  if (hour >= 11 && hour < 15) return 'lunch'
  if (hour >= 17 && hour < 22) return 'dinner'
  return 'snack'
}

const consumedTimeSchema = z.string().min(1, '请选择用餐时间。').refine((value) => {
  const date = new Date(value)
  // Reject invalid local dates, including normalization over a DST gap.
  return Number.isFinite(date.getTime()) && localMealTime(date) === value && date.getTime() <= Date.now()
}, '请选择有效的当前或过去用餐时间。')
export const mealMetadataFormSchema = z.object({ mealSlot: mealSlotSchema, consumedAt: consumedTimeSchema })
export const mealMetadataEditSchema = z.object({ mealSlot: z.union([mealSlotSchema, z.literal('')]), consumedAt: consumedTimeSchema })
export type MealMetadataForm = z.infer<typeof mealMetadataFormSchema>
export type MealMetadataEditForm = z.infer<typeof mealMetadataEditSchema>
export type MealMetadata = { mealSlot: MealSlot | null; consumedAt: string }
