import { z } from 'zod'

export const formulaVariantSchema = z.enum(['mifflin_st_jeor_male', 'mifflin_st_jeor_female'])
export const activityLevelSchema = z.enum(['sedentary', 'light', 'moderate', 'high', 'very_high'])
export const planningGoalSchema = z.enum(['maintain', 'loss', 'gain'])
export const goalSpeedSchema = z.enum(['maintain', 'gradual_loss', 'gradual_gain'])

const decimalTextSchema = z.string().trim().regex(/^\d+(?:\.\d{1,2})?$/, '请输入有效数字。')

export const planningProfileInputSchema = z.object({
  height_cm: decimalTextSchema.refine((value) => Number(value) >= 100 && Number(value) <= 250, '身高必须在 100 到 250 cm 之间。').optional(),
  weight_kg: decimalTextSchema.refine((value) => Number(value) >= 20 && Number(value) <= 350, '体重必须在 20 到 350 kg 之间。').optional(),
  age_years: z.number().int().min(1).max(130).optional(),
  formula_variant: formulaVariantSchema.optional(),
  activity_level: activityLevelSchema.optional(),
  goal: planningGoalSchema.optional(),
  goal_speed: goalSpeedSchema.optional(),
  is_pregnant_or_breastfeeding: z.boolean().default(false),
  has_disease_or_treatment: z.boolean().default(false),
  uses_medication: z.boolean().default(false),
  has_eating_disorder_or_self_harm_risk: z.boolean().default(false),
  has_extreme_weight_control_goal: z.boolean().default(false),
}).strict()

export const planningProfileSchema = z.object({
  height_cm: decimalTextSchema,
  weight_kg: decimalTextSchema,
  age_years: z.number().int(),
  formula_variant: formulaVariantSchema,
  activity_level: activityLevelSchema,
  goal: planningGoalSchema,
  goal_speed: goalSpeedSchema,
  target_policy_version: z.string().min(1).max(80),
  formula_version: z.string().min(1).max(80),
}).strict()

export const preferenceReviewSchema = z.object({
  confirmed: z.boolean(),
  exclusions: z.array(z.string().min(1)).default([]),
  taste_preferences: z.array(z.string().min(1)).default([]),
}).strict()

export const dietPlanningStartCommandSchema = z.object({
  profile: planningProfileInputSchema,
  preferences: preferenceReviewSchema,
  save_profile: z.boolean().default(false),
}).strict()

export const dietPlanningSafeEventSchema = z.object({
  type: z.enum(['reading_context', 'calculating_targets', 'composing_plan', 'validating_plan', 'complete', 'needs_input']),
  summary: z.string().min(1).max(500),
}).strict()

/** The existing public input endpoint owns planning-thread authorization and replay handling. */
export const dietPlanningAdjustmentSchema = z.object({
  kind: z.literal('description'),
  text: z.string().trim().min(1, '请说明想调整什么。').max(500, '调整内容最多 500 个字符。'),
}).strict()

export const dietPlanningAdjustmentResponseSchema = z.object({
  thread_id: z.string().uuid(),
  status: z.enum(['waiting', 'partial', 'completed', 'retryable', 'terminal']),
}).strict()

export const dietPlanningStartResponseSchema = z.object({
  thread_id: z.string().uuid(),
  status: z.enum(['waiting', 'partial', 'accepted', 'running', 'completed', 'retryable', 'failed', 'terminal', 'deletion_pending']),
  revision: z.number().int().nonnegative(),
}).strip()

export const profileGoalFormSchema = z.object({
  height_cm: decimalTextSchema.refine((value) => Number(value) >= 100 && Number(value) <= 250, '身高必须在 100 到 250 cm 之间。'),
  weight_kg: decimalTextSchema.refine((value) => Number(value) >= 20 && Number(value) <= 350, '体重必须在 20 到 350 kg 之间。'),
  age_years: z.number({ error: '年龄必须是整数。' }).int('年龄必须是整数。').min(1).max(130),
  formula_variant: formulaVariantSchema,
  activity_level: activityLevelSchema,
  goal: planningGoalSchema,
  goal_speed: goalSpeedSchema,
  preference_reviewed: z.boolean(),
  save_profile: z.boolean(),
}).strict().superRefine((value, context) => {
  if (!value.preference_reviewed) {
    context.addIssue({ code: 'custom', message: '请先确认已复核本次饮食偏好。', path: ['preference_reviewed'] })
  }
})

export type DietPlanningStartCommand = z.infer<typeof dietPlanningStartCommandSchema>
export type DietPlanningStartResponse = z.infer<typeof dietPlanningStartResponseSchema>
export type DietPlanningAdjustment = z.infer<typeof dietPlanningAdjustmentSchema>
export type PlanningProfile = z.infer<typeof planningProfileSchema>
export type ProfileGoalFormValues = z.infer<typeof profileGoalFormSchema>
