import {
  dietPlanningStartCommandSchema,
  dietPlanningStartResponseSchema,
  type DietPlanningStartCommand,
  type DietPlanningStartResponse,
} from './schemas'
import { getPlanningApiError, type PlanningApiRequest } from './profile'

export { getPlanningProfile, PlanningApiError } from './profile'
export type { PlanningApiRequest } from './profile'

export async function startDietPlanning(request: PlanningApiRequest, command: DietPlanningStartCommand, commandKey = `diet-plan-${crypto.randomUUID()}`): Promise<DietPlanningStartResponse> {
  const payload = dietPlanningStartCommandSchema.parse(command)
  const response = await request('/agent/threads/diet-planning', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': commandKey },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw await getPlanningApiError(response, '暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。')
  return dietPlanningStartResponseSchema.parse(await response.json())
}
