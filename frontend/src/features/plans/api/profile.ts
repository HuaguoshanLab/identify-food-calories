import type { AuthenticatedRequest } from '@/auth/AuthContext'
import { z } from 'zod'

import { planningProfileSchema, type PlanningProfile } from './schemas'

export type PlanningApiRequest = AuthenticatedRequest

export const planningProfileQueryKey = ['planning-profile'] as const

export const planningProfileWriteSchema = planningProfileSchema.omit({
  formula_version: true,
  target_policy_version: true,
})

export type PlanningProfileWrite = z.infer<typeof planningProfileWriteSchema>

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

export async function getPlanningApiError(response: Response, fallback: string) {
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
  if (!response.ok) throw await getPlanningApiError(response, '无法读取个人资料。')
  return planningProfileSchema.parse(await response.json())
}

export async function replacePlanningProfile(request: PlanningApiRequest, profile: PlanningProfileWrite): Promise<PlanningProfile> {
  const payload = planningProfileWriteSchema.parse(profile)
  const response = await request('/planning/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw await getPlanningApiError(response, '保存个人资料失败，请稍后重试。')
  return planningProfileSchema.parse(await response.json())
}

export async function deletePlanningProfile(request: PlanningApiRequest): Promise<void> {
  const response = await request('/planning/profile', { method: 'DELETE' })
  if (response.status === 404) return
  if (!response.ok) throw await getPlanningApiError(response, '删除个人资料失败，请稍后重试。')
}
