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
  const summaryLabel = stage === 'completed' ? '已完成' : stage === 'retryable' ? '需要重试' : stage === 'terminal' ? '需要新输入' : '处理中'

  return (
    <section aria-label={label} className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-[0_4px_12px_rgb(25_72_53/0.06)]">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">分析进度</h2>
        <span className="text-[13px] font-medium text-primary">{summaryLabel}</span>
      </div>
      <ol className="grid grid-cols-5 gap-0 text-center">
        {stageOrder.map((businessStage, index) => {
          const Icon = stageIcon(businessStage)
          const state = stageState(index, currentIndex, stage)
          const active = state === 'active'
          const completed = state === 'completed'
          return <li aria-current={active ? 'step' : undefined} className="relative min-w-0" key={businessStage}>
            {index < stageOrder.length - 1 ? <span aria-hidden="true" className={`absolute left-1/2 right-0 top-3 h-px ${completed ? 'bg-primary' : 'bg-border'}`} /> : null}
            <span className={`relative mx-auto mb-2 flex size-6 items-center justify-center rounded-full border ${completed ? 'border-primary bg-primary text-primary-foreground' : active ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-muted text-muted-foreground'}`}>
              <Icon aria-hidden="true" className="size-3.5" />
            </span>
            <span className={`block px-0.5 text-[11px] leading-4 ${active || completed ? 'font-semibold text-foreground' : 'text-muted-foreground'}`}>{copy[businessStage].label}</span>
          </li>
        })}
      </ol>
      <p aria-live="polite" className="rounded-lg bg-muted/60 px-3 py-2 text-sm leading-5 text-muted-foreground" role="status">{current.announcement}</p>
      {retryable ? <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 p-3 text-sm"><span><CircleAlert aria-hidden="true" className="mr-1 inline size-4 text-destructive" />请确认信息后再发起一次。</span><Button className="h-9 shrink-0" onClick={onRetry} type="button" variant="outline">重新尝试</Button></div> : null}
    </section>
  )
}
