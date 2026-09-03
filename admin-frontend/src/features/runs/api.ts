import { z } from 'zod'

const decimalTextSchema = z.string().regex(/^\d+(?:\.\d+)?$/)
const isoDateTimeSchema = z.string().datetime({ offset: true })
const terminalStatusSchema = z.enum(['completed', 'failed', 'limit_reached'])

const invocationSchema = z.object({
  node_name: z.string().min(1).max(80),
  status: z.enum(['prepared', 'completed', 'failed', 'outcome_unknown']),
  attempt: z.number().int().nonnegative(),
  cost_usd: decimalTextSchema,
  failure_code: z.string().min(1).max(80).nullable(),
  safe_result_digest: z.string().min(1).max(200).nullable(),
}).strict()

const runSchema = z.object({
  id: z.string().uuid(),
  status: terminalStatusSchema,
  graph_version: z.string().min(1).max(80),
  model_provider: z.string().min(1).max(80).nullable(),
  model_version: z.string().min(1).max(120).nullable(),
  graph_steps: z.number().int().nonnegative(),
  model_calls: z.number().int().nonnegative(),
  tool_calls: z.number().int().nonnegative(),
  elapsed_ms: z.number().int().nonnegative(),
  estimated_cost_usd: decimalTextSchema,
  failure_code: z.string().min(1).max(80).nullable(),
  finished_at: isoDateTimeSchema,
  invocations: z.array(invocationSchema),
}).strict()

export const runMetricsSchema = z.object({
  terminal_count: z.number().int().nonnegative(),
  failure_ratio: decimalTextSchema,
  p50_elapsed_ms: z.number().int().nonnegative().nullable(),
  p95_elapsed_ms: z.number().int().nonnegative().nullable(),
  total_cost_usd: decimalTextSchema,
}).strict()

export const runPageSchema = z.object({
  items: z.array(runSchema),
  next_cursor: z.string().min(16).max(500).nullable(),
}).strict()

export type AdminRun = z.infer<typeof runSchema>
export type AdminRunMetrics = z.infer<typeof runMetricsSchema>
export type RunFilterValues = Readonly<{
  occurred_after?: string
  occurred_before?: string
  status?: z.infer<typeof terminalStatusSchema>
  graph_version?: string
  model?: string
  failure_node?: string
  failure_code?: string
}>

export class RunsApiError extends Error {
  constructor(readonly status: 401 | 403 | 404 | 422 | 500) {
    super(`Runs API request failed with ${status}`)
  }
}

function headers(accessToken: string) {
  return { Authorization: `Bearer ${accessToken}` }
}

function queryString(filters: RunFilterValues, cursor?: string) {
  const params = new URLSearchParams({ limit: '50' })
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value)
  }
  if (cursor) params.set('cursor', cursor)
  return params.toString()
}

async function request(path: string, accessToken: string): Promise<unknown> {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, { headers: headers(accessToken), method: 'GET' })
  if (!response.ok) {
    const status = [401, 403, 404, 422].includes(response.status) ? response.status : 500
    throw new RunsApiError(status as RunsApiError['status'])
  }
  return response.json()
}

export function readRunMetrics(accessToken: string, filters: RunFilterValues) {
  return request(`/runs/metrics?${queryString(filters)}`, accessToken).then(runMetricsSchema.parse)
}

export function readRuns(accessToken: string, filters: RunFilterValues, cursor?: string) {
  return request(`/runs?${queryString(filters, cursor)}`, accessToken).then(runPageSchema.parse)
}

export function readRun(accessToken: string, runId: string) {
  return request(`/runs/${z.string().uuid().parse(runId)}`, accessToken).then(runSchema.parse)
}
