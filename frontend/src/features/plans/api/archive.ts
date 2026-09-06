import { z } from 'zod'
import type { AuthenticatedRequest } from '@/auth/AuthContext'
import { planReportSchema } from './report'

const totals = z.object({ energy_kcal: z.string(), carbohydrate_g: z.string(), protein_g: z.string(), fat_g: z.string() }).strict()
const summary = z.object({ id: z.string().uuid(), plan_date: z.string().date(), time_zone: z.string().min(1), current_version: z.number().int().positive(), created_at: z.string().datetime({ offset: true }), updated_at: z.string().datetime({ offset: true }) }).strict()
export const savedPlanSchema = summary.extend({ version: z.number().int().positive(), saved_at: z.string().datetime({ offset: true }), report: planReportSchema, totals, adjustment_thread_id: z.string().uuid().nullable() }).strict()
const todaySchema = z.object({ time_zone: z.string().nullable(), today: z.string().date().nullable(), plan: savedPlanSchema.nullable() }).strict()
const historySchema = z.object({ items: z.array(summary), next_before: z.string().date().nullable() }).strict()
export type TodayPlan = z.infer<typeof todaySchema>
export type SavedPlan = z.infer<typeof savedPlanSchema>
export const planArchiveKeys = { all: ['saved-plans'] as const, today: ['saved-plans', 'today'] as const, history: ['saved-plans', 'history'] as const, detail: (id: string, version: string | null) => ['saved-plans', id, version] as const }

async function json(response: Response): Promise<unknown> {
  if (!response.ok) throw new Error('saved plan unavailable')
  return response.json()
}
export async function getTodayPlan(request: AuthenticatedRequest) { return todaySchema.parse(await json(await request('/planning/plans/today'))) }
export async function getPlanHistory(request: AuthenticatedRequest, before: string | null) { return historySchema.parse(await json(await request(`/planning/plans${before ? `?before=${encodeURIComponent(before)}` : ''}`))) }
export async function getSavedPlan(request: AuthenticatedRequest, id: string, version: string | null) { return savedPlanSchema.parse(await json(await request(`/planning/plans/${encodeURIComponent(id)}${version ? `?version=${encodeURIComponent(version)}` : ''}`))) }
export async function deleteSavedPlan(request: AuthenticatedRequest, id: string) { const response = await request(`/planning/plans/${encodeURIComponent(id)}`, { method: 'DELETE' }); if (!response.ok) throw new Error('plan deletion failed') }
