import { CircleAlert, CircleCheck, CircleDotDashed, CircleHelp, CirclePlay, CircleStop } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { SafeStreamStage } from '../api/stream'

const stageOrder = ['perception', 'awaiting_input', 'tool_calculation', 'validation', 'completed'] as const

export const analysisStageCopy = {
  perception: { label: '感知餐食', announcement: '正在识别餐食信息' },
  awaiting_input: { label: '等待补充', announcement: '等待你补充信息' },
  tool_calculation: { label: '营养计算', announcement: '正在进行营养计算' },
  validation: { label: '结果校验', announcement: '正在校验分析结果' },
  completed: { label: '完成分析', announcement: '分析已完成' },
  retryable: { label: '可重新尝试', announcement: '本次分析暂未完成，你可以重新尝试。' },
  terminal: { label: '需要新的输入', announcement: '当前分析无法继续，请补充信息或重新开始。' },
} as const

type StageCopy = Record<SafeStreamStage, { label: string; announcement: string }>
type BusinessStage = (typeof stageOrder)[number]

export type SafeProgressStagesProps = { stage?: SafeStreamStage; copy?: StageCopy; label?: string; onRetry?: () => void }

function stageIcon(stage: BusinessStage) {
  if (stage === 'completed') return CircleCheck
  if (stage === 'awaiting_input') return CircleHelp
  if (stage === 'tool_calculation') return CirclePlay
  if (stage === 'validation') return CircleDotDashed
  return CircleStop
}

/** All visible wording is a local stage allowlist; server message text never becomes UI content. */
export function SafeProgressStages({ stage, copy = analysisStageCopy, label = '分析进度', onRetry }: SafeProgressStagesProps) {
  if (!stage) return null
  const currentIndex = stageOrder.indexOf(stage as BusinessStage)
  const current = copy[stage]
  const retryable = stage === 'retryable' && onRetry

  return (
    <section aria-label={label} className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
      <ol className="grid grid-cols-5 gap-1 text-center text-[11px] leading-4 text-muted-foreground">
        {stageOrder.map((businessStage, index) => {
          const Icon = stageIcon(businessStage)
          const active = businessStage === stage
          const completed = currentIndex > index || stage === 'completed'
          return <li aria-current={active ? 'step' : undefined} className={active ? 'font-semibold text-foreground' : undefined} key={businessStage}>
            <Icon aria-hidden="true" className={`mx-auto mb-1 size-4 ${completed ? 'text-primary' : ''}`} />
            {copy[businessStage].label}
          </li>
        })}
      </ol>
      <p aria-live="polite" className="text-sm text-muted-foreground" role="status">{current.announcement}</p>
      {retryable ? <div className="flex items-center justify-between gap-3 rounded-md bg-background p-2 text-sm"><span><CircleAlert aria-hidden="true" className="mr-1 inline size-4 text-destructive" />请确认信息后再发起一次。</span><Button className="h-9 shrink-0" onClick={onRetry} type="button" variant="outline">重新尝试</Button></div> : null}
    </section>
  )
}
