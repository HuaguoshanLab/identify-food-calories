import { useCallback, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useAgentEventStream } from '@/features/agent/stream/useAgentEventStream'
import { listMemories } from '@/features/memory/api/client'
import { getPlanningProfile, planningProfileQueryKey } from '../api/profile'
import { dietPlanningSafeEventSchema, type DietPlanningStartResponse } from '../api/schemas'
import { MealCard } from './MealCard'
import { PlanOverview } from './PlanOverview'
import { CompletedPlanningStatus, PlanningStatus } from './PlanningStatus'
import { ProfileGoalForm, type PreferenceSummaries } from './ProfileGoalForm'

const decimalSchema = z.string().regex(/^\d+(?:\.\d+)?$/)
const metricSchema = z.object({ lower: decimalSchema, upper: decimalSchema }).strict()
const nutrientsSchema = z.object({ energy_kcal: decimalSchema, carbohydrate_g: decimalSchema, protein_g: decimalSchema, fat_g: decimalSchema }).strict()
const planMealSchema = z.object({
  slot: z.enum(['breakfast', 'lunch', 'dinner']), display_name: z.string().min(1), portion_description: z.string().min(1), portion_grams: decimalSchema,
  method_tags: z.array(z.string().min(1)), flavour_tags: z.array(z.string().min(1)), matched_preference_summaries: z.array(z.string().min(1)), matched_exclusion_summaries: z.array(z.string().min(1)), nutrients: nutrientsSchema,
}).strict()
const planReportSchema = z.object({
  stage: z.literal('complete'), target: z.object({ energy_kcal: metricSchema, carbohydrate_g: metricSchema, protein_g: metricSchema, fat_g: metricSchema }).strict(),
  meals: z.array(planMealSchema).length(3), disclaimer: z.literal('普通饮食参考，不替代医疗建议。'),
}).strict().superRefine((report, context) => {
  if (report.meals.map((meal) => meal.slot).join(',') !== 'breakfast,lunch,dinner') context.addIssue({ code: 'custom', message: 'meal slots must remain ordered' })
})
const safeSnapshotSchema = z.object({
  thread_id: z.string().uuid(), status: z.enum(['waiting', 'partial', 'completed', 'retryable', 'terminal', 'deletion_pending']), revision: z.number().int().nonnegative(), report: z.unknown().optional(), recovery_code: z.string().min(1).max(80).nullable().optional(),
}).strict()
const safePlanningEventCopy = {
  reading_context: '正在读取已确认的资料与饮食偏好…',
  calculating_targets: '正在计算每日目标区间…',
  composing_plan: '正在组合一日三餐…',
  validating_plan: '正在校验营养与已确认约束…',
  complete: '计划已生成。',
  needs_input: '需要你补充或确认信息后继续。',
} as const

export type PlanMeal = z.infer<typeof planMealSchema>
export type PlanReport = z.infer<typeof planReportSchema>

function preferencesFromMemory(memories: Awaited<ReturnType<typeof listMemories>>): PreferenceSummaries {
  return {
    exclusions: memories.filter((memory) => memory.category === 'avoidance').map((memory) => memory.canonical_text),
    tastePreferences: memories.filter((memory) => memory.category === 'stable_preference').map((memory) => memory.canonical_text),
  }
}

export function PlanPage() {
  const { request } = useAuth()
  const [threadId, setThreadId] = useState<string>()
  const [report, setReport] = useState<PlanReport>()
  const [statusKind, setStatusKind] = useState<'idle' | 'working' | 'error' | 'refusal'>('idle')
  const [statusMessage, setStatusMessage] = useState<string>()
  const profileQuery = useQuery({ queryKey: planningProfileQueryKey, queryFn: () => getPlanningProfile(request) })
  const memoriesQuery = useQuery({ queryKey: ['planning-preference-summary'], queryFn: () => listMemories(request) })
  const preferenceSummaries = useMemo(() => preferencesFromMemory(memoriesQuery.data ?? []), [memoriesQuery.data])

  const applySnapshot = useCallback(async (response: Response) => {
    if (!response.ok) throw new Error('planning snapshot request failed')
    const snapshot = safeSnapshotSchema.parse(await response.json())
    const parsedReport = planReportSchema.safeParse(snapshot.report)
    if (snapshot.status === 'completed' && parsedReport.success) {
      setReport(parsedReport.data)
      setStatusKind('idle')
      setStatusMessage(undefined)
      return
    }
    setReport(undefined)
    if (snapshot.status === 'terminal') {
      setStatusKind('refusal')
      setStatusMessage(undefined)
      return
    }
    if (snapshot.status === 'retryable') {
      setStatusKind('error')
      setStatusMessage(undefined)
      return
    }
    setStatusKind('working')
    setStatusMessage(safePlanningEventCopy.needs_input)
  }, [])

  useAgentEventStream({
    threadId,
    request,
    onEvent: (event) => {
      const safeEvent = dietPlanningSafeEventSchema.safeParse(event)
      if (!safeEvent.success) return
      setStatusKind(safeEvent.data.type === 'complete' ? 'idle' : 'working')
      setStatusMessage(safePlanningEventCopy[safeEvent.data.type])
    },
    onSnapshot: applySnapshot,
  })

  function onStarted(snapshot: DietPlanningStartResponse) {
    setThreadId(snapshot.thread_id)
    setReport(undefined)
    setStatusKind('working')
    setStatusMessage(safePlanningEventCopy.reading_context)
  }

  return <section className="mx-auto w-full max-w-xl space-y-4 pb-4">
    <div className="space-y-2"><h1 className="text-[28px] font-semibold leading-9 tracking-tight">饮食计划</h1><p className="text-[15px] leading-6 text-muted-foreground">先复核资料和偏好，再生成今日可执行的一日三餐。</p></div>
    <PlanningStatus kind={statusKind} message={statusMessage} />
    {profileQuery.isError ? <Alert variant="destructive"><AlertTitle>无法读取个人资料</AlertTitle><AlertDescription>你仍可填写本次资料；系统不会自动保存。</AlertDescription></Alert> : null}
    <ProfileGoalForm initialValues={profileQuery.data ?? null} isLoading={profileQuery.isLoading || memoriesQuery.isLoading} preferenceLoadError={memoriesQuery.isError} preferenceSummaries={preferenceSummaries} onStarted={onStarted} />
    {report ? <section aria-labelledby="daily-plan-title" className="space-y-4">
      <div className="space-y-1"><h2 className="text-xl font-semibold" id="daily-plan-title">今日三餐计划</h2><CompletedPlanningStatus /></div>
      <PlanOverview report={report} />
      <div className="space-y-3">{report.meals.map((meal) => <MealCard key={meal.slot} meal={meal} />)}</div>
    </section> : null}
    <footer className="text-[13px] leading-5 text-muted-foreground">普通饮食参考，不替代医疗建议。</footer>
  </section>
}
