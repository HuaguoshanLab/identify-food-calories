import { z } from 'zod'
import type { MealMetadata } from './mealMetadata'
export { localMealTime, suggestedMealSlot, mealSlotLabels, mealMetadataFormSchema, type MealMetadataForm } from './mealMetadata'

import { mealRecordSchema, type MealRecord } from './schemas'
import type { AuthenticatedRequest } from '@/auth/AuthContext'

export type { MealRecord } from './schemas'

export type ApiRequest = AuthenticatedRequest

const dashboardTimezoneConfirmationSchema = z.object({
  dashboard_time_zone: z.string().min(1).max(64),
  confirmed_at: z.string().datetime({ offset: true }),
}).strict().transform((value) => ({
  dashboardTimeZone: value.dashboard_time_zone,
  confirmedAt: value.confirmed_at,
}))

export type DashboardTimezoneConfirmation = z.infer<typeof dashboardTimezoneConfirmationSchema>

/** A changed browser zone cannot replace the persisted statistical basis. */
export class DashboardTimezoneConflictError extends Error {
  constructor() {
    super('dashboard time zone conflicts with the confirmed statistical basis')
    this.name = 'DashboardTimezoneConflictError'
  }
}

async function parsed(response: Response): Promise<MealRecord> { return mealRecordSchema.parse(await response.json()) }
export async function listMealRecords(request: ApiRequest): Promise<MealRecord[]> { const response = await request('/meal-records'); if (!response.ok) throw new Error('records unavailable'); return mealRecordSchema.array().parse(await response.json()) }
export async function getMealRecord(request: ApiRequest, id: string): Promise<MealRecord> { const response = await request(`/meal-records/${id}`); if (!response.ok) throw new Error('record unavailable'); return parsed(response) }
export async function confirmMealRecord(request: ApiRequest, threadId: string, commandKey: string, metadata: MealMetadata): Promise<MealRecord> {
  // The server derives the local dashboard date from a named IANA zone; offset-only
  // values would make the persisted statistical basis unreplayable across DST changes.
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  if (!timeZone) throw new Error('browser time zone is unavailable')
  const response = await request('/meal-records', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: threadId, command_key: commandKey, time_zone: timeZone, meal_slot: metadata.mealSlot, consumed_at: metadata.consumedAt }),
  })
  if (!response.ok) throw new Error('record save failed')
  return parsed(response)
}

/**
 * The browser can propose a zone only through this records-owned command.
 * Dashboard reads deliberately cannot receive the proposal as an authority.
 */
export async function confirmDashboardTimeZone(
  request: ApiRequest,
  timeZone: string,
): Promise<DashboardTimezoneConfirmation> {
  const response = await request('/meal-records/dashboard-time-zone-confirmations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ time_zone: timeZone }),
  })
  if (response.status === 409) throw new DashboardTimezoneConflictError()
  if (response.status !== 200) throw new Error('dashboard time zone confirmation failed')
  return dashboardTimezoneConfirmationSchema.parse(await response.json())
}
export type MealItemCorrection = { itemId: string; grams: string }
export async function updateMealRecord(request: ApiRequest, id: string, metadata: MealMetadata, items?: MealItemCorrection[]): Promise<MealRecord> {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  if (!timeZone) throw new Error('browser time zone is unavailable')
  const response = await request(`/meal-records/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      consumed_at: metadata.consumedAt,
      meal_slot: metadata.mealSlot,
      time_zone: timeZone,
      ...(items ? { items: items.map((item) => ({ item_id: item.itemId, grams: item.grams })) } : {}),
    }),
  })
  if (!response.ok) throw new Error('record update failed')
  return parsed(response)
}
export async function deleteMealRecord(request: ApiRequest, id: string): Promise<void> { const response = await request(`/meal-records/${id}`, { method: 'DELETE' }); if (!response.ok) throw new Error('record delete failed') }
