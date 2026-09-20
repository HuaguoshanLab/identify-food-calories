import {
  dietPlanningStartCommandSchema,
  dietPlanningAdjustmentResponseSchema,
  dietPlanningAdjustmentSchema,
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
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': commandKey, Prefer: 'respond-async' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw await getPlanningApiError(response, '暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。')
  return dietPlanningStartResponseSchema.parse(await response.json())
}

/**
 * Adjustment stays on the server-owned planning thread. The text is intentionally the sole
 * client choice: the graph, not the browser, retains exclusions and decides any safe relaxation.
 */
export async function submitDietPlanningAdjustment(
  request: PlanningApiRequest,
  threadId: string,
  text: string,
  commandKey = `diet-plan-adjustment-${crypto.randomUUID()}`,
) {
  const payload = dietPlanningAdjustmentSchema.parse({ kind: 'description', text })
  const response = await request(`/agent/threads/${encodeURIComponent(threadId)}/input`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': commandKey, Prefer: 'respond-async' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw await getPlanningApiError(response, '暂时无法提交调整。请检查网络后重试。')
  return dietPlanningAdjustmentResponseSchema.parse(await response.json())
}

export async function getPlanningSnapshot(request: PlanningApiRequest, threadId: string): Promise<Response> {
  return request(`/agent/threads/${encodeURIComponent(threadId)}`)
}
