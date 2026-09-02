import { z } from 'zod'

import type { AuthenticatedRequest } from '@/auth/AuthContext'

const totalsSchema = z.object({ energy_kcal: z.string(), protein_g: z.string(), fat_g: z.string(), carbohydrate_g: z.string() }).strict()
export const weeklyReviewResponseSchema = z.object({
  status: z.enum(['insufficient_coverage', 'safety_abstain', 'success', 'retryable_error']),
  week_start: z.string().date(), week_end: z.string().date(), coverage_days: z.number().int().min(0).max(7), meal_count: z.number().int().nonnegative(), totals: totalsSchema,
  suggestions: z.array(z.string().min(1)).max(3),
}).strict().superRefine((value, context) => {
  if (value.status === 'success' && value.suggestions.length === 0) context.addIssue({ code: 'custom', message: 'success requires suggestions' })
  if (value.status !== 'success' && value.suggestions.length > 0) context.addIssue({ code: 'custom', message: 'only success may include suggestions' })
})
export type WeeklyReviewResponse = z.infer<typeof weeklyReviewResponseSchema>

export const weeklyReviewQueryKeys = { detail: (timeZone: string, weekStart: string) => ['dashboard', 'weekly-review', timeZone, weekStart] as const }

async function read(response: Response): Promise<WeeklyReviewResponse> { if (!response.ok) throw new Error('weekly review unavailable'); return weeklyReviewResponseSchema.parse(await response.json()) }
export async function getWeeklyReview(request: AuthenticatedRequest, weekStart: string): Promise<WeeklyReviewResponse> { return read(await request(`/dashboard/weekly-review?week_start=${encodeURIComponent(weekStart)}`)) }
export async function refreshWeeklyReview(request: AuthenticatedRequest, weekStart: string): Promise<WeeklyReviewResponse> { return read(await request(`/dashboard/weekly-review/refresh?week_start=${encodeURIComponent(weekStart)}`, { method: 'POST' })) }
