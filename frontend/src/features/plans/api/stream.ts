import { z } from 'zod'

const safePlanningStageSchema = z.enum(['perception', 'awaiting_input', 'tool_calculation', 'validation', 'completed', 'retryable', 'terminal'])

// Re-validate at the planning boundary rather than trusting a shared transport TypeScript type.
const safePlanningStageEventSchema = z.object({
  schema_version: z.literal('safe-stream-stage.v1'),
  stage: safePlanningStageSchema,
  message: z.string().min(1).max(300),
}).strict()

export type SafePlanningStage = z.infer<typeof safePlanningStageSchema>
export type SafePlanningStageEvent = z.infer<typeof safePlanningStageEventSchema>

export function parseSafePlanningStageEvent(payload: unknown): SafePlanningStageEvent {
  return safePlanningStageEventSchema.parse(payload)
}
