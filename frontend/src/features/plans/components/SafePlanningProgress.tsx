import { analysisStageCopy } from '@/features/agent/api/stream'
import { SafeProgressStages } from '@/features/agent/components/SafeProgressStages'
import type { SafePlanningStage } from '../api/stream'

const planningStageCopy = {
  ...analysisStageCopy,
  perception: { label: '感知资料', announcement: '正在读取已确认的资料与饮食偏好' },
  awaiting_input: { label: '等待补充', announcement: '等待你补充信息' },
  tool_calculation: { label: '目标计算', announcement: '正在计算每日目标区间' },
  validation: { label: '结果校验', announcement: '正在校验营养与已确认约束' },
  completed: { label: '完成计划', announcement: '计划已生成' },
  retryable: { label: '可重新尝试', announcement: '本次计划暂未完成，你可以重新尝试。' },
  terminal: { label: '需要新的输入', announcement: '当前计划无法继续，请调整资料后重新开始。' },
} as const

/** Planning only adapts local wording; shared stage semantics and a11y remain identical. */
export function SafePlanningProgress({ stage, onRetry }: { stage?: SafePlanningStage; onRetry?: () => void }) {
  return <SafeProgressStages copy={planningStageCopy} label="计划进度" onRetry={onRetry} stage={stage} />
}
