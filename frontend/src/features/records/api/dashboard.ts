import { z } from 'zod'
import type { AuthenticatedRequest } from '@/auth/AuthContext'

const nutritionTotalsSchema = z.object({ energy_kcal: z.string(), protein_g: z.string(), fat_g: z.string(), carbohydrate_g: z.string() }).strict()
const daySummarySchema = z.object({ consumed_local_date: z.string().date(), totals: nutritionTotalsSchema, meal_count: z.number().int().nonnegative() }).strict()
const targetRangeSchema = z.object({ lower: z.string(), upper: z.string() }).strict()
export const dashboardTargetEligibilitySchema = z.discriminatedUnion('eligible', [
  z.object({ eligible: z.literal(false) }).strict(),
  z.object({ eligible: z.literal(true), target_version: z.string().min(1), target: z.object({ energy_kcal: targetRangeSchema, protein_g: targetRangeSchema, fat_g: targetRangeSchema, carbohydrate_g: targetRangeSchema }).strict() }).strict(),
])

const dashboardOverviewPayloadSchema = z.object({ today: daySummarySchema, week: z.array(daySummarySchema).length(7), target_eligibility: z.unknown().optional() }).strict()
export const dashboardOverviewSchema = dashboardOverviewPayloadSchema.transform((payload) => {
  const eligibility = dashboardTargetEligibilitySchema.safeParse(payload.target_eligibility)
  return { today: payload.today, week: payload.week, target_eligibility: eligibility.success ? eligibility.data : undefined }
})
export const dashboardHistoryPageSchema = z.object({ groups: z.array(z.object({ consumed_local_date: z.string().date(), totals: nutritionTotalsSchema, meal_count: z.number().int().nonnegative(), items: z.array(z.object({ id: z.string().uuid(), consumed_at: z.string().datetime({ offset: true }), totals: nutritionTotalsSchema }).strict()) }).strict()), next_cursor: z.string().min(1).nullable().default(null) }).strict()
export type DashboardOverview = z.infer<typeof dashboardOverviewSchema>
export type DashboardHistoryPage = z.infer<typeof dashboardHistoryPageSchema>

export const dashboardQueryKeys = {
  overview: () => ['dashboard', 'overview', 'current'] as const,
  history: (cursor: string | null) => ['dashboard', 'history', cursor] as const,
}

async function readJson(response: Response): Promise<unknown> { if (!response.ok) throw new Error('dashboard unavailable'); return response.json() }
/** The API owns the current local week from the confirmed dashboard preference. */
export async function getDashboardOverview(request: AuthenticatedRequest): Promise<DashboardOverview> { return dashboardOverviewSchema.parse(await readJson(await request('/dashboard/overview'))) }
export async function getDashboardHistory(request: AuthenticatedRequest, cursor: string | null): Promise<DashboardHistoryPage> { return dashboardHistoryPageSchema.parse(await readJson(await request(cursor === null ? '/dashboard/history' : `/dashboard/history?cursor=${encodeURIComponent(cursor)}`))) }
