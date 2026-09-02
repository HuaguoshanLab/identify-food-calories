import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { useAgentEventStream } from '@/features/agent/stream/useAgentEventStream'
import { listMemories } from '@/features/memory/api/client'
import { routePaths } from '@/routePaths'
import { submitDietPlanningAdjustment } from '../api/client'
import { getPlanningProfile, planningProfileQueryKey } from '../api/profile'
import type { DietPlanningStartResponse } from '../api/schemas'
import { parseSafePlanningStageEvent, type SafePlanningStage } from '../api/stream'
import { formatPlanNumber, formatPlanRange } from '../format'
import { MealCard } from './MealCard'
import { PlanOverview } from './PlanOverview'
import { CompletedPlanningStatus, FocusedPlanningAlert } from './PlanningStatus'
import { SafePlanningProgress } from './SafePlanningProgress'
import { ProfileGoalForm, type PreferenceSummaries } from './ProfileGoalForm'

const decimalSchema = z.string().regex(/^\d+(?:\.\d+)?$/)
const metricSchema = z.object({ lower: decimalSchema, upper: decimalSchema }).strict()
const nutrientsSchema = z.object({ energy_kcal: decimalSchema, carbohydrate_g: decimalSchema, protein_g: decimalSchema, fat_g: decimalSchema }).strict()
const slotSchema = z.enum(['breakfast', 'lunch', 'dinner'])
const planMealSchema = z.object({
  slot: slotSchema, display_name: z.string().min(1), portion_description: z.string().min(1), portion_grams: decimalSchema,
  method_tags: z.array(z.string().min(1)), flavour_tags: z.array(z.string().min(1)), matched_preference_summaries: z.array(z.string().min(1)), matched_exclusion_summaries: z.array(z.string().min(1)), nutrients: nutrientsSchema,
}).strict()
const rangeStatusSchema = z.enum(['low', 'in_range', 'high'])
const relaxationSchema = z.object({ metric: z.enum(['energy_kcal', 'carbohydrate_g', 'protein_g', 'fat_g']), original_range: metricSchema, plan_value: decimalSchema, deviation: z.string().regex(/^-?\d+(?:\.\d+)?$/), reason: z.string().min(1).max(500) }).strict()
const planAdjustmentSchema = z.object({
  changed_slots: z.array(slotSchema).length(1), matched_constraint: z.string().min(1).max(200),
  range_status: z.object({ energy_kcal: rangeStatusSchema, carbohydrate_g: rangeStatusSchema, protein_g: rangeStatusSchema, fat_g: rangeStatusSchema }).strict(), relaxation: relaxationSchema.optional(),
}).strict()
const planReportSchema = z.object({
  stage: z.literal('complete'), target: z.object({ energy_kcal: metricSchema, carbohydrate_g: metricSchema, protein_g: metricSchema, fat_g: metricSchema }).strict(),
  meals: z.array(planMealSchema).length(3), disclaimer: z.literal('普通饮食参考，不替代医疗建议。'), adjustment: planAdjustmentSchema.optional(),
}).strict().superRefine((report, context) => {
  if (report.meals.map((meal) => meal.slot).join(',') !== 'breakfast,lunch,dinner') context.addIssue({ code: 'custom', message: 'meal slots must remain ordered' })
})
const needsInputReportSchema = z.object({ stage: z.literal('needs_input'), message: z.string().min(1).max(500), code: z.literal('LIMIT_REACHED').optional(), input_choices: z.array(slotSchema).length(3).optional() }).strict()
const safeSnapshotSchema = z.object({ thread_id: z.string().uuid(), status: z.enum(['waiting', 'partial', 'completed', 'retryable', 'terminal', 'deletion_pending']), revision: z.number().int().nonnegative(), report: z.unknown().optional(), recovery_code: z.string().min(1).max(80).nullable().optional() }).strict()
const healthScopeCopy = '我们不能为你当前描述的情况生成个性化餐单。孕期或哺乳期、未成年人、疾病或用药、进食障碍或自伤，以及极端减重/增重目标需要专业评估。请咨询医生或注册营养师。你仍可以查看通用、非医疗的均衡饮食原则。'
const slotLabels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐' } as const
const metricLabels = { energy_kcal: ['能量', 'kcal'], carbohydrate_g: ['碳水', 'g'], protein_g: ['蛋白质', 'g'], fat_g: ['脂肪', 'g'] } as const

export type PlanMeal = z.infer<typeof planMealSchema>
export type PlanReport = z.infer<typeof planReportSchema>
export type PlanMealAdjustment = { previousName: string; matchedConstraint: string; rangeStatus: string }

function preferencesFromMemory(memories: Awaited<ReturnType<typeof listMemories>>): PreferenceSummaries {
  return { exclusions: memories.filter((memory) => memory.category === 'avoidance').map((memory) => memory.canonical_text), tastePreferences: memories.filter((memory) => memory.category === 'stable_preference').map((memory) => memory.canonical_text) }
}

function adjustmentRangeSummary(statuses: z.infer<typeof planAdjustmentSchema>['range_status']): string {
  const labels = { low: '偏低', in_range: '适中', high: '偏高' } as const
  return Object.entries(statuses).map(([metric, status]) => `${metricLabels[metric as keyof typeof metricLabels][0]}${labels[status]}`).join(' · ')
}

function RelaxationAlert({ relaxation }: { relaxation: z.infer<typeof relaxationSchema> }) {
  const [label, unit] = metricLabels[relaxation.metric]
  const direction = relaxation.deviation.startsWith('-') ? '低于原目标' : relaxation.deviation === '0' ? '与原目标边界一致' : '高于原目标'
  return <Alert role="alert"><AlertTitle>已按现有约束生成餐单，但目标已调整</AlertTitle><AlertDescription className="space-y-2"><p className="tabular-nums">{label}原目标：{formatPlanRange(relaxation.original_range.lower, relaxation.original_range.upper, unit).replace('目标：', '')}</p><p className="tabular-nums">计划值：{formatPlanNumber(relaxation.plan_value)} {unit}；偏离：{formatPlanNumber(relaxation.deviation)} {unit}（{direction}）</p><p>{relaxation.reason}</p><p>忌口和你明确排除的食物未被放宽。</p></AlertDescription></Alert>
}

export function PlanPage() {
  const { request } = useAuth()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [threadId, setThreadId] = useState<string>()
  const [report, setReport] = useState<PlanReport>()
  const [mealAdjustment, setMealAdjustment] = useState<Record<PlanMeal['slot'], PlanMealAdjustment | undefined>>({ breakfast: undefined, lunch: undefined, dinner: undefined })
  const [statusKind, setStatusKind] = useState<'idle' | 'working' | 'error' | 'refusal'>('idle')
  const [statusMessage, setStatusMessage] = useState<string>()
  const [progressStage, setProgressStage] = useState<SafePlanningStage>()
  const [inputChoices, setInputChoices] = useState<PlanMeal['slot'][]>()
  const [adjustmentText, setAdjustmentText] = useState('')
  const [adjustmentError, setAdjustmentError] = useState('')
  const [adjusting, setAdjusting] = useState(false)
  const [limitReached, setLimitReached] = useState(false)
  const [updatedSlot, setUpdatedSlot] = useState<PlanMeal['slot']>()
  const profileQuery = useQuery({ queryKey: planningProfileQueryKey, queryFn: () => getPlanningProfile(request) })
  const memoriesQuery = useQuery({ queryKey: ['planning-preference-summary'], queryFn: () => listMemories(request) })
  const preferenceSummaries = useMemo(() => preferencesFromMemory(memoriesQuery.data ?? []), [memoriesQuery.data])

  useEffect(() => { headingRef.current?.focus() }, [])

  const applySnapshot = useCallback(async (response: Response) => {
    if (!response.ok) throw new Error('planning snapshot request failed')
    const snapshot = safeSnapshotSchema.parse(await response.json())
    const parsedReport = planReportSchema.safeParse(snapshot.report)
    const needsInput = needsInputReportSchema.safeParse(snapshot.report)
    if (snapshot.status === 'completed' && parsedReport.success) {
      const changedSlot = parsedReport.data.adjustment?.changed_slots[0]
      if (changedSlot && parsedReport.data.adjustment) {
        const previousName = report?.meals.find((meal) => meal.slot === changedSlot)?.display_name
        if (previousName) setMealAdjustment((current) => ({ ...current, [changedSlot]: { previousName, matchedConstraint: parsedReport.data.adjustment!.matched_constraint, rangeStatus: adjustmentRangeSummary(parsedReport.data.adjustment!.range_status) } }))
        setUpdatedSlot(changedSlot)
      }
      setReport(parsedReport.data); setInputChoices(undefined); setLimitReached(false); setStatusKind('idle'); setStatusMessage(undefined); setProgressStage('completed')
      return
    }
    if (snapshot.status === 'terminal' && needsInput.success && needsInput.data.code === 'LIMIT_REACHED') {
      setLimitReached(true); setInputChoices(undefined); setStatusKind('idle'); setStatusMessage(undefined)
      return
    }
    if (snapshot.status === 'waiting' && needsInput.success && needsInput.data.input_choices) {
      setInputChoices(needsInput.data.input_choices); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('awaiting_input')
      return
    }
    // `terminal` also represents bounded candidate exhaustion. Only the explicit safe
    // health-scope result may use the medical-referral presentation; conflating the two
    // falsely tells eligible adults that they triggered a high-risk health boundary.
    if (snapshot.status === 'retryable' && needsInput.success && needsInput.data.message === healthScopeCopy) {
      setReport(undefined); setInputChoices(undefined); setLimitReached(false); setStatusKind('refusal'); setStatusMessage(undefined)
      return
    }
    setInputChoices(undefined); setStatusKind('error'); setStatusMessage(needsInput.success ? needsInput.data.message : undefined); setProgressStage('retryable')
  }, [report])

  useAgentEventStream({ threadId, request, onEvent: (event) => {
    try {
      const safeEvent = parseSafePlanningStageEvent(event)
      setStatusKind(safeEvent.stage === 'completed' ? 'idle' : 'working')
      setStatusMessage(undefined)
      setProgressStage(safeEvent.stage)
    } catch {
      setStatusKind('error'); setStatusMessage(undefined); setProgressStage('retryable')
    }
  }, onInvalidEvent: () => { setStatusKind('error'); setStatusMessage(undefined); setProgressStage('retryable') }, onSnapshot: applySnapshot })

  function onStarted(snapshot: DietPlanningStartResponse) {
    setThreadId(snapshot.thread_id); setReport(undefined); setMealAdjustment({ breakfast: undefined, lunch: undefined, dinner: undefined }); setInputChoices(undefined); setLimitReached(false); setUpdatedSlot(undefined); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('perception')
  }

  async function submitAdjustment(text: string) {
    if (!threadId || adjusting || limitReached || statusKind === 'refusal') return
    const normalized = text.trim()
    if (!normalized) { setAdjustmentError('请说明想调整什么。'); return }
    setAdjusting(true); setAdjustmentError(''); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('tool_calculation')
    try {
      await submitDietPlanningAdjustment(request, threadId, normalized)
      await applySnapshot(await request(`/agent/threads/${encodeURIComponent(threadId)}`))
      setAdjustmentText('')
    } catch { setStatusKind('error'); setProgressStage('retryable'); setAdjustmentError('暂时无法提交调整。请检查网络后重试。') } finally { setAdjusting(false) }
  }

  function startNewPlan() {
    setThreadId(undefined); setReport(undefined); setMealAdjustment({ breakfast: undefined, lunch: undefined, dinner: undefined }); setInputChoices(undefined); setLimitReached(false); setUpdatedSlot(undefined); setStatusKind('idle'); setStatusMessage(undefined); setProgressStage(undefined); setAdjustmentText('')
  }

  const relaxation = report?.adjustment?.relaxation
  return <section className="mx-auto w-full max-w-xl space-y-4 pb-4">
    <div className="space-y-2"><h1 ref={headingRef} tabIndex={-1} className="text-[28px] font-semibold leading-9 tracking-tight">计划</h1><p className="text-[15px] leading-6 text-muted-foreground">根据已确认的资料和偏好生成一日三餐参考。</p></div>
    <Alert><AlertTitle>普通饮食参考，不替代医疗建议。</AlertTitle></Alert>
    {statusMessage ? <Alert variant="destructive"><AlertTitle>{statusMessage}</AlertTitle></Alert> : null}
    {statusKind !== 'refusal' ? <SafePlanningProgress onRetry={startNewPlan} stage={progressStage} /> : null}
    {profileQuery.isError ? <Alert variant="destructive"><AlertTitle>无法读取个人资料</AlertTitle><AlertDescription>你仍可填写本次资料；系统不会自动保存。</AlertDescription></Alert> : null}
    <ProfileGoalForm initialValues={profileQuery.data ?? null} isLoading={profileQuery.isLoading || memoriesQuery.isLoading} preferenceLoadError={memoriesQuery.isError} preferenceSummaries={preferenceSummaries} onStarted={onStarted} />
    {inputChoices ? <section aria-labelledby="adjustment-choice-title" className="space-y-3"><h2 className="text-xl font-semibold" id="adjustment-choice-title">请确认要调整哪一餐</h2><p className="text-[15px] leading-6 text-muted-foreground">你的要求可能影响多餐，请选择要替换的餐次。</p><div className="grid grid-cols-3 gap-2">{inputChoices.map((slot) => <Button className="h-11" disabled={adjusting} key={slot} onClick={() => void submitAdjustment(slot)} type="button" variant="outline">{slotLabels[slot]}</Button>)}</div><Button className="h-11" disabled={adjusting} onClick={() => setInputChoices(undefined)} type="button" variant="ghost">返回修改描述</Button></section> : null}
    {statusKind === 'refusal' ? <FocusedPlanningAlert title="暂不能生成个性化餐单">{healthScopeCopy}</FocusedPlanningAlert> : null}
    {limitReached && !report ? <FocusedPlanningAlert title="已达到调整上限"><p>已完成 3 次自动调整，无法在当前约束内继续修改。你可以新建计划，或修改身体资料和目标后再试。</p><div className="mt-3 flex flex-col gap-2"><Button className="h-11" onClick={startNewPlan} type="button">新建计划</Button><Link className="flex h-11 items-center justify-center rounded-lg border border-input px-4 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" to={routePaths.profile}>修改个人资料</Link></div></FocusedPlanningAlert> : null}
    {report && statusKind !== 'refusal' ? <section aria-labelledby="daily-plan-title" className="space-y-4"><div className="space-y-1"><h2 className="text-xl font-semibold" id="daily-plan-title">今日三餐计划</h2><CompletedPlanningStatus /></div><PlanOverview report={report} />{relaxation ? <RelaxationAlert relaxation={relaxation} /> : null}<div className="space-y-3">{report.meals.map((meal) => <MealCard adjustment={mealAdjustment[meal.slot]} key={meal.slot} meal={meal} />)}</div>{updatedSlot ? <p aria-live="polite" className="sr-only">已更新{slotLabels[updatedSlot]}，其余餐次保持不变。</p> : null}{limitReached ? <FocusedPlanningAlert title="已达到调整上限"><p>已完成 3 次自动调整，无法在当前约束内继续修改。你可以新建计划，或修改身体资料和目标后再试。</p><div className="mt-3 flex flex-col gap-2"><Button className="h-11" onClick={startNewPlan} type="button">新建计划</Button><Link className="flex h-11 items-center justify-center rounded-lg border border-input px-4 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" to={routePaths.profile}>修改个人资料</Link></div></FocusedPlanningAlert> : <section aria-labelledby="plan-adjustment-title" className="space-y-2"><h2 className="text-xl font-semibold" id="plan-adjustment-title">调整这份计划</h2><Label htmlFor="plan-adjustment">告诉我们想换什么</Label><textarea aria-describedby={adjustmentError ? 'plan-adjustment-error' : 'plan-adjustment-help'} aria-invalid={Boolean(adjustmentError)} className="min-h-28 w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" id="plan-adjustment" maxLength={500} onChange={(event) => setAdjustmentText(event.target.value)} placeholder="例如：午餐换清淡一些，或不吃香菜" value={adjustmentText} /><p className="text-[13px] leading-5 text-muted-foreground" id="plan-adjustment-help">系统默认只替换直接受影响的菜品，其余餐次和已确认约束会保留。</p>{adjustmentError ? <p className="text-[13px] leading-5 text-destructive" id="plan-adjustment-error" role="alert">{adjustmentError}</p> : null}<Button className="h-11 w-full" disabled={adjusting} onClick={() => void submitAdjustment(adjustmentText)} type="button">{adjusting ? '正在提交调整…' : '提交调整'}</Button></section>}</section> : null}
    <footer className="text-[13px] leading-5 text-muted-foreground">普通饮食参考，不替代医疗建议。</footer>
  </section>
}
