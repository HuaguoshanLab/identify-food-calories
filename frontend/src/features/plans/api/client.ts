import type { AuthenticatedRequest } from '@/auth/AuthContext'
import { z } from 'zod'
import {
  dietPlanningStartCommandSchema,
  dietPlanningStartResponseSchema,
  planningProfileSchema,
  type DietPlanningStartCommand,
  type DietPlanningStartResponse,
  type PlanningProfile,
} from './schemas'

export type PlanningApiRequest = AuthenticatedRequest

const apiErrorSchema = z.object({
  detail: z.array(z.object({
    loc: z.array(z.union([z.string(), z.number()])),
    msg: z.string().min(1),
  }).strip()).default([]),
}).strip()

export class PlanningApiError extends Error {
  readonly fieldErrors: Record<string, string>

  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'PlanningApiError'
    this.fieldErrors = fieldErrors
  }
}

async function errorFrom(response: Response, fallback: string) {
  try {
    const parsed = apiErrorSchema.parse(await response.json())
    const fieldErrors = Object.fromEntries(parsed.detail.map((detail) => [detail.loc.filter((part) => part !== 'body').join('.'), detail.msg]))
    return new PlanningApiError(parsed.detail[0]?.msg ?? fallback, fieldErrors)
  } catch {
    return new PlanningApiError(fallback)
  }
}

export async function getPlanningProfile(request: PlanningApiRequest): Promise<PlanningProfile | null> {
  const response = await request('/planning/profile')
  if (response.status === 404) return null
  if (!response.ok) throw await errorFrom(response, '无法读取个人资料。')
  return planningProfileSchema.parse(await response.json())
}

export async function startDietPlanning(request: PlanningApiRequest, command: DietPlanningStartCommand, commandKey = `diet-plan-${crypto.randomUUID()}`): Promise<DietPlanningStartResponse> {
  const payload = dietPlanningStartCommandSchema.parse(command)
  const response = await request('/agent/threads/diet-planning', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': commandKey },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw await errorFrom(response, '暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。')
  return dietPlanningStartResponseSchema.parse(await response.json())
}
