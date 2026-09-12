import { z } from 'zod'

const decimalSchema = z.string().regex(/^\d+(?:\.\d+)?$/)
const metricSchema = z.object({ lower: decimalSchema, upper: decimalSchema }).strict()
const nutrientsSchema = z.object({ energy_kcal: decimalSchema, carbohydrate_g: decimalSchema, protein_g: decimalSchema, fat_g: decimalSchema }).strict()
const slotSchema = z.enum(['breakfast', 'lunch', 'dinner', 'snack'])
const planMealSchema = z.object({
  slot: slotSchema, display_name: z.string().min(1), portion_description: z.string().min(1), portion_grams: decimalSchema,
  method_tags: z.array(z.string().min(1)), flavour_tags: z.array(z.string().min(1)), matched_preference_summaries: z.array(z.string().min(1)), matched_exclusion_summaries: z.array(z.string().min(1)), nutrients: nutrientsSchema,
}).strict()
const rangeStatusSchema = z.enum(['low', 'in_range', 'high'])
const relaxationSchema = z.object({ metric: z.enum(['energy_kcal', 'carbohydrate_g', 'protein_g', 'fat_g']), original_range: metricSchema, plan_value: decimalSchema, deviation: z.string().regex(/^-?\d+(?:\.\d+)?$/), reason: z.string().min(1).max(500) }).strict()
const planAdjustmentSchema = z.object({
  changed_slots: z.array(slotSchema).length(1), matched_constraint: z.string().min(1).max(200),
  range_status: z.object({ energy_kcal: rangeStatusSchema, carbohydrate_g: rangeStatusSchema, protein_g: rangeStatusSchema, fat_g: rangeStatusSchema }).strict(), relaxation: relaxationSchema.nullish().transform((value) => value ?? undefined),
}).strict()
export const planReportSchema = z.object({
  stage: z.literal('complete'), target: z.object({ energy_kcal: metricSchema, carbohydrate_g: metricSchema, protein_g: metricSchema, fat_g: metricSchema }).strict(),
  meals: z.array(planMealSchema).min(3).max(4), relaxation: relaxationSchema.nullish().transform((value) => value ?? undefined), disclaimer: z.literal('普通饮食参考，不替代医疗建议。'), adjustment: planAdjustmentSchema.nullish().transform((value) => value ?? undefined),
}).strict().superRefine((report, context) => {
  if (!['breakfast,lunch,dinner', 'breakfast,lunch,dinner,snack'].includes(report.meals.map((meal) => meal.slot).join(','))) context.addIssue({ code: 'custom', message: 'meal slots must remain ordered' })
})
export const needsInputReportSchema = z.object({ stage: z.literal('needs_input'), message: z.string().min(1).max(500), code: z.literal('LIMIT_REACHED').optional(), input_choices: z.array(slotSchema).min(3).max(4).optional() }).strict()
const planningFoodCandidateSchema = z.object({
  item_id: z.literal('planning-substitution'), food_id: z.string().uuid(), catalog_version: z.string().min(1).max(80),
  label: z.string().min(1).max(320), canonical_label: z.string().min(1).max(200).nullable(), relation_label: z.string().min(1).max(80).nullable(),
  prepared_state: z.string().min(1).max(120).nullable(), portion_hints: z.array(z.string().min(1).max(120)).max(8), source_name: z.string().min(1).max(120).nullable(),
}).strict()
export const foodClarificationReportSchema = z.object({
  stage: z.literal('food_clarification'), message: z.string().min(1).max(500), candidates: z.array(planningFoodCandidateSchema).min(1).max(3),
}).strict()
export const recipeClarificationReportSchema = z.object({
  stage: z.literal('recipe_clarification'), schema_version: z.literal('recipe-choices.v1'),
  message: z.string().min(1).max(500),
  candidates: z.array(z.object({
    recipe_id: z.string().uuid(), revision: z.number().int().positive(),
    food_id: z.string().uuid(), catalog_version: z.string().min(1).max(80),
    display_name: z.string().min(1).max(200), meal_slot: slotSchema,
    portion_grams: decimalSchema, portion_description: z.string().min(1).max(120),
    method_tags: z.array(z.string()), flavour_tags: z.array(z.string()),
  }).strict()).min(1).max(20),
}).strict()
export type RecipeClarificationReport = z.infer<typeof recipeClarificationReportSchema>
export const safeSnapshotSchema = z.object({ thread_id: z.string().uuid(), status: z.enum(['waiting', 'partial', 'completed', 'retryable', 'terminal', 'deletion_pending']), revision: z.number().int().nonnegative(), report: z.unknown().optional(), recovery_code: z.string().min(1).max(80).nullable().optional() }).strict()

export type PlanMeal = z.infer<typeof planMealSchema>
export type PlanReport = z.infer<typeof planReportSchema>
export type PlanRangeStatus = z.infer<typeof planAdjustmentSchema>["range_status"]
export type PlanRelaxation = z.infer<typeof relaxationSchema>
export type FoodClarificationReport = z.infer<typeof foodClarificationReportSchema>
