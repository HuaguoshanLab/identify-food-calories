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

export const analysisStageCopy = {
  perception: { label: '感知餐食', announcement: '正在识别餐食信息' },
  awaiting_input: { label: '等待补充', announcement: '等待你补充信息' },
  tool_calculation: { label: '营养计算', announcement: '正在进行营养计算' },
  validation: { label: '结果校验', announcement: '正在校验分析结果' },
  completed: { label: '完成分析', announcement: '分析已完成' },
  retryable: { label: '可重新尝试', announcement: '本次分析暂未完成，你可以重新尝试。' },
  terminal: { label: '需要新的输入', announcement: '当前分析无法继续，请补充信息或重新开始。' },
} as const

