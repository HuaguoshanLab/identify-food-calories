import { mealRecordSchema, type MealRecord } from './schemas'
import type { AuthenticatedRequest } from '@/auth/AuthContext'

export type { MealRecord } from './schemas'

export type ApiRequest = AuthenticatedRequest

async function parsed(response: Response): Promise<MealRecord> { return mealRecordSchema.parse(await response.json()) }
export async function listMealRecords(request: ApiRequest): Promise<MealRecord[]> { const response = await request('/meal-records'); if (!response.ok) throw new Error('records unavailable'); return mealRecordSchema.array().parse(await response.json()) }
export async function getMealRecord(request: ApiRequest, id: string): Promise<MealRecord> { const response = await request(`/meal-records/${id}`); if (!response.ok) throw new Error('record unavailable'); return parsed(response) }
export async function confirmMealRecord(request: ApiRequest, threadId: string, commandKey: string): Promise<MealRecord> { const response = await request('/meal-records', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ thread_id: threadId, command_key: commandKey }) }); if (!response.ok) throw new Error('record save failed'); return parsed(response) }
export async function updateMealRecord(request: ApiRequest, id: string, consumedAt: string): Promise<MealRecord> { const response = await request(`/meal-records/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ consumed_at: consumedAt }) }); if (!response.ok) throw new Error('record update failed'); return parsed(response) }
export async function deleteMealRecord(request: ApiRequest, id: string): Promise<void> { const response = await request(`/meal-records/${id}`, { method: 'DELETE' }); if (!response.ok) throw new Error('record delete failed') }
