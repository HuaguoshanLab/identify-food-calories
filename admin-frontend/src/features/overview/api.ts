import { z } from 'zod'

const decimalTextSchema = z.string().regex(/^\d+(?:\.\d+)?$/)
const isoDateTimeSchema = z.string().datetime({ offset: true })

export const overviewMetricsSchema = z.object({
  terminal_count: z.number().int().nonnegative(),
  failure_ratio: decimalTextSchema,
  p50_elapsed_ms: z.number().int().nonnegative().nullable(),
  p95_elapsed_ms: z.number().int().nonnegative().nullable(),
  total_cost_usd: decimalTextSchema,
}).strict()

export type OverviewMetrics = z.infer<typeof overviewMetricsSchema>
export type OverviewWindow = Readonly<{ occurred_after: string, occurred_before: string }>

export class OverviewApiError extends Error {
  constructor(readonly status: 401 | 403 | 422 | 500) { super(`Overview API request failed with ${status}`) }
}

export function recentTerminalWindow(now = new Date()): OverviewWindow {
  return { occurred_after: new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(), occurred_before: now.toISOString() }
}

export async function readOverviewMetrics(accessToken: string, window: OverviewWindow) {
  isoDateTimeSchema.parse(window.occurred_after)
  isoDateTimeSchema.parse(window.occurred_before)
  const params = new URLSearchParams(window)
  const response = await fetch(`${__ADMIN_API_BASE_URL__}/runs/metrics?${params}`, { headers: { Authorization: `Bearer ${accessToken}` }, method: 'GET' })
  if (!response.ok) {
    const status = [401, 403, 422].includes(response.status) ? response.status : 500
    throw new OverviewApiError(status as OverviewApiError['status'])
  }
  return overviewMetricsSchema.parse(await response.json())
}
