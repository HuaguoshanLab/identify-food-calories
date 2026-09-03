import { z } from 'zod'

const decimalTextSchema = z.string().regex(/^\d+(?:\.\d+)?$/)

export const runtimeConfigSchema = z.object({
  id: z.string().uuid(),
  version: z.number().int().positive(),
  provider: z.literal('deepseek'),
  model_alias: z.literal('deepseek-v4-flash'),
  enabled: z.boolean(),
  single_call_cap_usd: decimalTextSchema,
  period_cap_usd: decimalTextSchema,
  input_usd_per_m: decimalTextSchema,
  output_usd_per_m: decimalTextSchema,
  created_at: z.string().datetime({ offset: true }),
}).strict()

export type RuntimeConfig = z.infer<typeof runtimeConfigSchema>

export const runtimeConfigFormSchema = z.object({
  provider: z.literal('deepseek'),
  model_alias: z.literal('deepseek-v4-flash'),
  enabled: z.boolean(),
  single_call_cap_usd: decimalTextSchema,
  period_cap_usd: decimalTextSchema,
  input_usd_per_m: decimalTextSchema,
  output_usd_per_m: decimalTextSchema,
  reason: z.string().trim().min(1, '请说明此次变更原因。').max(500),
}).strict()

export type RuntimeConfigFormValues = z.infer<typeof runtimeConfigFormSchema>

export class RuntimeConfigApiError extends Error {
  constructor(readonly status: 401 | 403 | 404 | 409 | 500) {
    super(`Runtime config API request failed with ${status}`)
  }
}

function headers(accessToken: string, commandKey?: string, revision?: number) {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    ...(commandKey ? { 'Idempotency-Key': commandKey } : {}),
    ...(revision !== undefined ? { 'If-Match': String(revision) } : {}),
  }
}

async function request(path: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(`${__ADMIN_API_BASE_URL__}${path}`, init)
  if (!response.ok) {
    const status = [401, 403, 404, 409].includes(response.status) ? response.status : 500
    throw new RuntimeConfigApiError(status as RuntimeConfigApiError['status'])
  }
  return response.json()
}

export function readRuntimeConfig(accessToken: string) {
  return request('/runtime-config', { headers: headers(accessToken), method: 'GET' }).then(runtimeConfigSchema.parse)
}

export function saveRuntimeConfig(accessToken: string, values: RuntimeConfigFormValues, idempotencyKey: string, expectedVersion: number) {
  const command = { ...runtimeConfigFormSchema.parse(values), confirm: true as const }
  return request('/runtime-config', {
    body: JSON.stringify(command), headers: headers(accessToken, idempotencyKey, expectedVersion), method: 'POST',
  }).then(runtimeConfigSchema.parse)
}
