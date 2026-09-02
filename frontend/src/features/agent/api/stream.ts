import { z } from 'zod'

export const safeStreamStageSchema = z.enum([
  'perception',
  'awaiting_input',
  'tool_calculation',
  'validation',
  'completed',
  'retryable',
  'terminal',
])

/** The browser rejects accidental provider, ledger, and graph-state fields at its API boundary. */
export const safeAgentStageEventSchema = z.object({
  schema_version: z.literal('safe-stream-stage.v1'),
  stage: safeStreamStageSchema,
  message: z.string().min(1).max(300),
}).strict()

export type SafeStreamStage = z.infer<typeof safeStreamStageSchema>
export type SafeAgentStageEvent = z.infer<typeof safeAgentStageEventSchema>

export function parseSafeAgentStageEvent(payload: unknown): SafeAgentStageEvent {
  return safeAgentStageEventSchema.parse(payload)
}
