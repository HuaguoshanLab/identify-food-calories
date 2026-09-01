import { CircleAlert, CircleCheck, LoaderCircle } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const safePlanningEventCopy = {
  reading_context: '正在读取已确认的资料与饮食偏好…',
  calculating_targets: '正在计算每日目标区间…',
  composing_plan: '正在组合一日三餐…',
  validating_plan: '正在校验营养与已确认约束…',
  complete: '计划已生成。',
  needs_input: '需要你补充或确认信息后继续。',
} as const

export type PlanningStatusKind = 'idle' | 'working' | 'error' | 'refusal'

export function PlanningStatus({ kind, message }: { kind: PlanningStatusKind; message?: string }) {
  if (kind === 'idle') return null
  if (kind === 'refusal') {
    return <Alert role="alert" tabIndex={-1} variant="destructive"><CircleAlert aria-hidden="true" /><AlertTitle>暂不能生成个性化餐单</AlertTitle><AlertDescription>我们不能为你当前描述的情况生成个性化餐单。孕期或哺乳期、未成年人、疾病或用药、进食障碍或自伤，以及极端减重/增重目标需要专业评估。请咨询医生或注册营养师。你仍可以查看通用、非医疗的均衡饮食原则。</AlertDescription></Alert>
  }
  if (kind === 'error') {
    return <Alert variant="destructive"><CircleAlert aria-hidden="true" /><AlertTitle>暂时无法生成计划</AlertTitle><AlertDescription>{message ?? '请检查资料和网络后重试；若问题持续，请稍后再试。'}</AlertDescription></Alert>
  }
  return <p aria-live="polite" className="flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />{message ?? safePlanningEventCopy.reading_context}</p>
}

export function FocusedPlanningAlert({ children, title }: { children: React.ReactNode; title: string }) {
  const alertRef = useRef<HTMLDivElement>(null)
  useEffect(() => { alertRef.current?.focus() }, [])
  return <Alert ref={alertRef} role="alert" tabIndex={-1} variant="destructive"><CircleAlert aria-hidden="true" /><AlertTitle>{title}</AlertTitle><AlertDescription>{children}</AlertDescription></Alert>
}

export function CompletedPlanningStatus() {
  return <p aria-live="polite" className="flex items-center gap-2 text-sm text-muted-foreground"><CircleCheck aria-hidden="true" className="size-4" />{safePlanningEventCopy.complete}</p>
}
