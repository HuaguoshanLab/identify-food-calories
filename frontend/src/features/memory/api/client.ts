import { z } from 'zod'
import type { AuthenticatedRequest } from '@/auth/AuthContext'

export const memorySchema = z.object({ id: z.string().uuid(), category: z.enum(['goal', 'avoidance', 'stable_preference']), source_kind: z.enum(['user_statement', 'model_inference', 'user_maintained']), canonical_text: z.string(), created_at: z.string(), updated_at: z.string() }).strict()
export type Memory = z.infer<typeof memorySchema>
async function parsed(response: Response): Promise<Memory> { return memorySchema.parse(await response.json()) }
export async function listMemories(request: AuthenticatedRequest): Promise<Memory[]> { const response = await request('/memories'); if (!response.ok) throw new Error('memories unavailable'); return memorySchema.array().parse(await response.json()) }
export async function getMemory(request: AuthenticatedRequest, id: string): Promise<Memory> { const response = await request(`/memories/${id}`); if (!response.ok) throw new Error('memory unavailable'); return parsed(response) }
export async function updateMemory(request: AuthenticatedRequest, id: string, canonicalText: string): Promise<Memory> { const response = await request(`/memories/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ canonical_text: canonicalText }) }); if (!response.ok) throw new Error('memory update failed'); return parsed(response) }
export async function deleteMemory(request: AuthenticatedRequest, id: string): Promise<void> { const response = await request(`/memories/${id}`, { method: 'DELETE' }); if (!response.ok) throw new Error('memory delete failed') }

const preferenceSummarySchema = z.object({ exclusions: z.array(z.string()), taste_preferences: z.array(z.string()) }).strict()
export async function getMemoryPreferenceSummary(request: AuthenticatedRequest) {
  const response = await request('/memories/preference-summary')
  if (!response.ok) throw new Error('preference summary unavailable')
  const summary = preferenceSummarySchema.parse(await response.json())
  return { exclusions: summary.exclusions, tastePreferences: summary.taste_preferences }
}
