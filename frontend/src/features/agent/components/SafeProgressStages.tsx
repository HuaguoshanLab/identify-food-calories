import { CircleAlert, CircleCheck, CircleDotDashed } from 'lucide-react'

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

function stageState(index: number, currentIndex: number, stage: SafeStreamStage) {
  if (stage === 'completed' || currentIndex > index) return 'completed'
  if (currentIndex === index) return 'active'
  return 'pending'
}

/** All visible wording is a local stage allowlist; server message text never becomes UI content. */
export function SafeProgressStages({ stage, copy = analysisStageCopy, label = '分析进度', onRetry }: SafeProgressStagesProps) {
  if (!stage) return null
  const currentIndex = stageOrder.indexOf(stage as BusinessStage)
  const current = copy[stage]
  const retryable = stage === 'retryable' && onRetry

  return (
    <section aria-label={label} className="rounded-xl border border-border bg-card p-3">
      <ol className="flex items-start justify-between gap-1">
        {stageOrder.map((businessStage, index) => {
          const state = stageState(index, currentIndex, stage)
          const active = state === 'active'
          const completed = state === 'completed'
          return <li aria-current={active ? 'step' : undefined} className="flex min-w-0 flex-1 flex-col items-center gap-1" key={businessStage}>
            <span className={`flex size-7 items-center justify-center rounded-full text-[11px] ${completed ? 'bg-primary text-primary-foreground' : active ? 'bg-muted text-foreground' : 'bg-muted/50 text-muted-foreground'}`}>
              {completed ? <CircleCheck aria-hidden="true" className="size-3.5" /> : active ? <CircleDotDashed aria-hidden="true" className="size-3.5 animate-spin motion-reduce:animate-none" /> : index + 1}
            </span>
            <span className={`text-center text-[11px] leading-4 ${active || completed ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>{copy[businessStage].label}</span>
          </li>
        })}
      </ol>
      <p aria-live="polite" className="mt-2.5 text-center text-[12px] leading-5 text-muted-foreground" role="status">{current.announcement}</p>
      {retryable ? <div className="mt-3 flex items-center justify-between gap-3 rounded-lg bg-muted/50 p-3 text-sm"><span><CircleAlert aria-hidden="true" className="mr-1 inline size-4 text-destructive" />请确认信息后再发起一次。</span><Button className="h-9 shrink-0" onClick={onRetry} type="button" variant="outline">重新尝试</Button></div> : null}
    </section>
  )
}
