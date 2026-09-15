import { useCallback, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { useAgentEventStream } from '@/features/agent/stream/useAgentEventStream'
import { getMemoryPreferenceSummary } from '@/features/memory/api/client'
import { routePaths } from '@/routePaths'
import { confirmDashboardTimeZone } from '@/features/records/api/client'
import { getTodayPlan, planArchiveKeys, type TodayPlan } from '../api/archive'
import { recipeClarificationReportSchema, type RecipeClarificationReport, foodClarificationReportSchema, planReportSchema, needsInputReportSchema, safeSnapshotSchema, type FoodClarificationReport, type PlanMeal, type PlanReport, type PlanRangeStatus, type PlanRelaxation } from '../api/report'
export type { PlanMeal, PlanReport } from '../api/report'
import { getPlanningSnapshot, submitDietPlanningAdjustment } from '../api/client'
import { getPlanningProfile, planningProfileQueryKey } from '../api/profile'
import type { DietPlanningStartResponse } from '../api/schemas'
import { parseSafePlanningStageEvent, type SafePlanningStage } from '../api/stream'
import { formatPlanNumber, formatPlanRange } from '../format'
import { MealCard } from './MealCard'
import { RecipeCandidateChoice } from './RecipeCandidateChoice'
import { PlanOverview } from './PlanOverview'
import { CompletedPlanningStatus, FocusedPlanningAlert } from './PlanningStatus'
import { SafePlanningProgress } from './SafePlanningProgress'
import { ProfileGoalForm } from './ProfileGoalForm'

const healthScopeCopy = '我们不能为你当前描述的情况生成个性化餐单。孕期或哺乳期、未成年人、疾病或用药、进食障碍或自伤，以及极端减重/增重目标需要专业评估。请咨询医生或注册营养师。你仍可以查看通用、非医疗的均衡饮食原则。'
const slotLabels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' } as const
const metricLabels = { energy_kcal: ['能量', 'kcal'], carbohydrate_g: ['碳水', 'g'], protein_g: ['蛋白质', 'g'], fat_g: ['脂肪', 'g'] } as const

export type PlanMealAdjustment = { previousName: string; matchedConstraint: string; rangeStatus: string }

function adjustmentRangeSummary(statuses: PlanRangeStatus): string {
  const labels = { low: '偏低', in_range: '适中', high: '偏高' } as const
  return Object.entries(statuses).map(([metric, status]) => `${metricLabels[metric as keyof typeof metricLabels][0]}${labels[status]}`).join(' · ')
}

function RelaxationAlert({ relaxation }: { relaxation: PlanRelaxation }) {
  const [label, unit] = metricLabels[relaxation.metric]
  const direction = relaxation.deviation.startsWith('-') ? '低于原目标' : relaxation.deviation === '0' ? '与原目标边界一致' : '高于原目标'
  return <Alert role="alert"><AlertTitle>已按现有约束生成餐单，但目标已调整</AlertTitle><AlertDescription className="space-y-2"><p className="tabular-nums">{label}原目标：{formatPlanRange(relaxation.original_range.lower, relaxation.original_range.upper, unit).replace('目标：', '')}</p><p className="tabular-nums">计划值：{formatPlanNumber(relaxation.plan_value)} {unit}；偏离：{formatPlanNumber(relaxation.deviation)} {unit}（{direction}）</p><p>{relaxation.reason}</p><p>忌口和你明确排除的食物未被放宽。</p></AlertDescription></Alert>
}

function PendingAdjustmentForm({ text }: { text: string }) {
  return <section aria-labelledby="pending-adjustment-title" className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm"><h2 className="text-base font-semibold leading-6" id="pending-adjustment-title">调整这份计划</h2><Label htmlFor="pending-plan-adjustment">告诉我们想换什么</Label><textarea className="min-h-20 w-full resize-y rounded-lg border border-input bg-muted px-3 py-2 text-base leading-6 text-muted-foreground" disabled id="pending-plan-adjustment" value={text} /><p className="text-[13px] leading-5 text-muted-foreground">调整要求已提交，请在下方确认菜品或具体菜谱。</p><Button className="h-11 w-full" disabled type="button">提交调整</Button></section>
}

export function PlanPage() {
  const { request } = useAuth()
  const [activeThreadId, setThreadId] = useState<string>()
  const [liveReport, setReport] = useState<PlanReport>()
  const [creating, setCreating] = useState(false)
  const queryClient = useQueryClient()
  const todayQuery = useQuery({ queryKey: planArchiveKeys.today, queryFn: () => getTodayPlan(request), refetchOnMount: 'always', refetchInterval: 60_000 })
  const savedPlan = todayQuery.data?.plan
  const report = liveReport ?? savedPlan?.report
  const threadId = activeThreadId ?? savedPlan?.adjustment_thread_id ?? undefined
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  const confirmation = useMutation({
    mutationFn: () => confirmDashboardTimeZone(request, timeZone),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: planArchiveKeys.all }),
  })
  const [mealAdjustment, setMealAdjustment] = useState<Record<PlanMeal['slot'], PlanMealAdjustment | undefined>>({ breakfast: undefined, lunch: undefined, dinner: undefined, snack: undefined })
  const [statusKind, setStatusKind] = useState<'idle' | 'working' | 'error' | 'refusal'>('idle')
  const [statusMessage, setStatusMessage] = useState<string>()
  const [progressStage, setProgressStage] = useState<SafePlanningStage>()
  const [inputChoices, setInputChoices] = useState<PlanMeal['slot'][]>()
  const [foodClarification, setFoodClarification] = useState<FoodClarificationReport>()
  const [selectedFoodId, setSelectedFoodId] = useState<string>()
  const [recipeClarification, setRecipeClarification] = useState<RecipeClarificationReport>()
  const [selectedRecipeId, setSelectedRecipeId] = useState<string>()
  const recipeOfferKey = useRef('')
  const [adjustmentText, setAdjustmentText] = useState('')
  const [adjustmentError, setAdjustmentError] = useState('')
  const [adjusting, setAdjusting] = useState(false)
  const [limitReached, setLimitReached] = useState(false)
  const [updatedSlot, setUpdatedSlot] = useState<PlanMeal['slot']>()
  const profileQuery = useQuery({ queryKey: planningProfileQueryKey, queryFn: () => getPlanningProfile(request) })
  const memoriesQuery = useQuery({ queryKey: ['planning-preference-summary'], queryFn: () => getMemoryPreferenceSummary(request) })
  const preferenceSummaries = memoriesQuery.data ?? { exclusions: [], tastePreferences: [] }

  const applySnapshot = useCallback(async (response: Response) => {
    if (!response.ok) throw new Error('planning snapshot request failed')
    const snapshot = safeSnapshotSchema.parse(await response.json())
    const parsedReport = planReportSchema.safeParse(snapshot.report)
    const needsInput = needsInputReportSchema.safeParse(snapshot.report)
    const foodInput = foodClarificationReportSchema.safeParse(snapshot.report)
    const recipeInput = recipeClarificationReportSchema.safeParse(snapshot.report)
    if (snapshot.status === 'partial') {
      setStatusKind('working'); setStatusMessage(undefined); setProgressStage((current) => current ?? 'perception')
      return
    }
    if (snapshot.status === 'waiting' && recipeInput.success) {
      const key = JSON.stringify(recipeInput.data.candidates)
      if (recipeOfferKey.current !== key) setSelectedRecipeId(undefined)
      recipeOfferKey.current = key
      setRecipeClarification(recipeInput.data); setFoodClarification(undefined); setSelectedFoodId(undefined); setInputChoices(undefined); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('awaiting_input')
      return
    }
    recipeOfferKey.current = ''
    setRecipeClarification(undefined); setSelectedRecipeId(undefined)
    if (snapshot.status === 'completed' && parsedReport.success) {
      const changedSlot = parsedReport.data.adjustment?.changed_slots[0]
      if (changedSlot && parsedReport.data.adjustment) {
        const previousName = report?.meals.find((meal) => meal.slot === changedSlot)?.display_name
        const currentName = parsedReport.data.meals.find((meal) => meal.slot === changedSlot)?.display_name
        // A restored stream may replay the already saved version. It carries no
        // previous name, so it cannot establish a new before/after comparison.
        if (previousName && previousName !== currentName) {
          setMealAdjustment((current) => ({ ...current, [changedSlot]: { previousName, matchedConstraint: parsedReport.data.adjustment!.matched_constraint, rangeStatus: adjustmentRangeSummary(parsedReport.data.adjustment!.range_status) } }))
          setUpdatedSlot(changedSlot)
        }
      }
      setReport(parsedReport.data); setCreating(false);
      await queryClient.invalidateQueries({ queryKey: planArchiveKeys.all });
      const restored = queryClient.getQueryData<TodayPlan>(planArchiveKeys.today)?.plan
      if (restored?.adjustment_thread_id === snapshot.thread_id) { setReport(undefined); setThreadId(undefined) }
      setInputChoices(undefined); setFoodClarification(undefined); setSelectedFoodId(undefined); setAdjustmentText(''); setLimitReached(false); setStatusKind('idle'); setStatusMessage(undefined); setProgressStage('completed')
      return
    }
    if (snapshot.status === 'terminal' && needsInput.success && needsInput.data.code === 'LIMIT_REACHED') {
      setLimitReached(true); setInputChoices(undefined); setFoodClarification(undefined); setSelectedFoodId(undefined); setStatusKind('idle'); setStatusMessage(undefined)
      return
    }
    if (snapshot.status === 'waiting' && foodInput.success) {
      setFoodClarification(foodInput.data); setSelectedFoodId(undefined); setInputChoices(undefined); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('awaiting_input')
      return
    }
    if (snapshot.status === 'waiting' && needsInput.success && needsInput.data.input_choices) {
      setInputChoices(needsInput.data.input_choices); setFoodClarification(undefined); setSelectedFoodId(undefined); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('awaiting_input')
      return
    }
    // `terminal` also represents bounded candidate exhaustion. Only the explicit safe
    // health-scope result may use the medical-referral presentation; conflating the two
    // falsely tells eligible adults that they triggered a high-risk health boundary.
    if (snapshot.status === 'retryable' && needsInput.success && needsInput.data.message === healthScopeCopy) {
      setReport(undefined); setInputChoices(undefined); setFoodClarification(undefined); setSelectedFoodId(undefined); setLimitReached(false); setStatusKind('refusal'); setStatusMessage(undefined)
      return
    }
    setInputChoices(undefined); setFoodClarification(undefined); setSelectedFoodId(undefined); setStatusKind('error'); setStatusMessage(needsInput.success ? needsInput.data.message : undefined); setProgressStage(snapshot.status === 'terminal' ? 'terminal' : 'retryable')
  }, [report, queryClient])

  useAgentEventStream({ threadId: creating ? activeThreadId : threadId, request, onEvent: (event) => {
    try {
      // The transport adds an SSE sequence ID; it is not part of the strict payload.
      const safeEvent = parseSafePlanningStageEvent({ schema_version: event.schema_version, stage: event.stage, message: event.message })
      setStatusKind(safeEvent.stage === 'completed' ? 'idle' : 'working')
      setStatusMessage(undefined)
      setProgressStage(safeEvent.stage)
    } catch {
      setStatusKind('error'); setStatusMessage(undefined); setProgressStage('retryable')
    }
  }, onInvalidEvent: () => { setStatusKind('error'); setStatusMessage(undefined); setProgressStage('retryable') }, onSnapshot: applySnapshot })

  function onStarted(snapshot: DietPlanningStartResponse) {
    setThreadId(snapshot.thread_id); setReport(undefined); setMealAdjustment({ breakfast: undefined, lunch: undefined, dinner: undefined, snack: undefined }); setInputChoices(undefined); setFoodClarification(undefined); setSelectedFoodId(undefined); setLimitReached(false); setUpdatedSlot(undefined); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('perception')
  }

  async function submitAdjustment(text: string) {
    if (!threadId || adjusting || limitReached || statusKind === 'refusal') return
    const normalized = text.trim()
    if (!normalized) { setAdjustmentError('请说明想调整什么。'); return }
    setAdjusting(true); setAdjustmentError(''); setStatusKind('working'); setStatusMessage(undefined); setProgressStage('tool_calculation')
    try {
      await submitDietPlanningAdjustment(request, threadId, normalized)
      await applySnapshot(await getPlanningSnapshot(request, threadId))
    } catch { setStatusKind('error'); setProgressStage('retryable'); setAdjustmentError('暂时无法提交调整。请检查网络后重试。') } finally { setAdjusting(false) }
  }

  async function submitFoodCandidate() {
    const candidate = foodClarification?.candidates.find((entry) => entry.food_id === selectedFoodId)
    if (!candidate) return
    await submitAdjustment(JSON.stringify({ candidate_id: candidate.food_id, catalog_version: candidate.catalog_version }))
  }

  async function submitRecipeCandidate() {
    const candidate = recipeClarification?.candidates.find((entry) => entry.recipe_id === selectedRecipeId)
    if (!candidate) return
    await submitAdjustment(JSON.stringify({ recipe_id: candidate.recipe_id, recipe_revision: candidate.revision }))
  }

  function startNewPlan() {
    setRecipeClarification(undefined); setSelectedRecipeId(undefined)
    setCreating(true)
    setThreadId(undefined); setReport(undefined); setMealAdjustment({ breakfast: undefined, lunch: undefined, dinner: undefined, snack: undefined }); setInputChoices(undefined); setFoodClarification(undefined); setSelectedFoodId(undefined); setLimitReached(false); setUpdatedSlot(undefined); setStatusKind('idle'); setStatusMessage(undefined); setProgressStage(undefined); setAdjustmentText('')
  }

  const relaxation = report?.adjustment?.relaxation ?? report?.relaxation
  const isTerminalCandidateExhausted = statusKind === 'error' && progressStage === 'terminal'
  return <section className="mx-auto w-full max-w-xl space-y-4 pb-4">
    {isTerminalCandidateExhausted ? <FocusedPlanningAlert title="暂时无法生成计划">{statusMessage ?? '当前受控餐单暂时无法满足已确认约束；请稍后重试或修改饮食偏好。'}</FocusedPlanningAlert> : null}
    {statusMessage && !isTerminalCandidateExhausted ? <Alert variant="destructive"><AlertTitle>{statusMessage}</AlertTitle></Alert> : null}
    {statusKind !== 'refusal' && (!report || creating) ? <SafePlanningProgress onRetry={startNewPlan} stage={progressStage} /> : null}
    {profileQuery.isError ? <Alert variant="destructive"><AlertTitle>无法读取个人资料</AlertTitle><AlertDescription>请先到“我的”检查身体资料，读取成功后才能生成餐单。</AlertDescription></Alert> : null}
    {todayQuery.isPending ? <p role="status">正在读取今日计划…</p> : null}
    {todayQuery.isError ? <Alert variant="destructive"><AlertTitle>无法读取已保存的计划</AlertTitle><AlertDescription><Button className="h-11" onClick={() => void todayQuery.refetch()} variant="outline">重新读取</Button></AlertDescription></Alert> : null}
    {todayQuery.data && !todayQuery.data.time_zone ? <Alert><AlertTitle>确认计划日期使用的时区</AlertTitle><AlertDescription><p>计划与饮食记录统一使用 {timeZone} 划分“今天”。</p><Button className="h-11" disabled={confirmation.isPending || !timeZone} onClick={() => confirmation.mutate()}>确认时区</Button>{confirmation.isError ? <p role="alert">确认失败，请重试或刷新读取已确认的时区。</p> : null}</AlertDescription></Alert> : null}
    {report && !creating ? <Button className="h-11 w-full" disabled={statusKind === 'working' || adjusting} onClick={startNewPlan} variant="outline">重新生成今日计划</Button> : null}
    {todayQuery.data?.time_zone && (!report || creating) ? <div className="space-y-3">
      <ProfileGoalForm initialValues={profileQuery.data ?? null} isLoading={profileQuery.isLoading || memoriesQuery.isLoading} profileLoadError={profileQuery.isError} preferenceLoadError={memoriesQuery.isError} preferenceSummaries={preferenceSummaries} onStarted={onStarted} />
    {savedPlan && creating ? <Button className="h-11 w-full" variant="ghost" onClick={() => setCreating(false)}>取消重新生成</Button> : null}
    </div> : null}
    {inputChoices ? <section aria-labelledby="adjustment-choice-title" className="space-y-3"><h2 className="text-base font-semibold leading-6" id="adjustment-choice-title">请确认要调整哪一餐</h2><p className="text-[15px] leading-6 text-muted-foreground">你的要求可能影响多餐，请选择要替换的餐次。</p><div className="grid grid-cols-3 gap-2">{inputChoices.map((slot) => <Button className="h-11" disabled={adjusting} key={slot} onClick={() => void submitAdjustment(slot)} type="button" variant="outline">{slotLabels[slot]}</Button>)}</div><Button className="h-11" disabled={adjusting} onClick={() => setInputChoices(undefined)} type="button" variant="ghost">返回修改描述</Button></section> : null}
    {statusKind === 'refusal' ? <FocusedPlanningAlert title="暂不能生成个性化餐单">{healthScopeCopy}</FocusedPlanningAlert> : null}
    {limitReached && !report ? <FocusedPlanningAlert title="已达到调整上限"><p>已完成 3 次自动调整，无法在当前约束内继续修改。你可以新建计划，或修改身体资料和目标后再试。</p><div className="mt-3 flex flex-col gap-2"><Button className="h-11" onClick={startNewPlan} type="button">新建计划</Button><Link className="flex h-11 items-center justify-center rounded-lg border border-input px-4 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" to={routePaths.profile}>修改个人资料</Link></div></FocusedPlanningAlert> : null}
    {report && !creating && statusKind !== 'refusal' ? <section aria-labelledby="daily-plan-title" className="space-y-4"><div className="space-y-1"><div className="flex items-center justify-between gap-3"><h2 className="text-base font-semibold leading-6" id="daily-plan-title">今日饮食计划</h2><CompletedPlanningStatus /></div>{savedPlan ? <p className="text-[13px] text-muted-foreground">已自动保存 · {savedPlan.plan_date} · 第 {savedPlan.current_version} 版</p> : null}</div><PlanOverview report={report} />{relaxation ? <RelaxationAlert relaxation={relaxation} /> : null}<div className="space-y-3">{report.meals.map((meal) => <MealCard adjustment={mealAdjustment[meal.slot]} key={meal.slot} meal={meal} />)}</div>{updatedSlot ? <p aria-live="polite" className="sr-only">已更新{slotLabels[updatedSlot]}，其余餐次保持不变。</p> : null}{limitReached ? <FocusedPlanningAlert title="已达到调整上限"><p>已完成 3 次自动调整，无法在当前约束内继续修改。你可以新建计划，或修改身体资料和目标后再试。</p><div className="mt-3 flex flex-col gap-2"><Button className="h-11" onClick={startNewPlan} type="button">新建计划</Button><Link className="flex h-11 items-center justify-center rounded-lg border border-input px-4 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" to={routePaths.profile}>修改个人资料</Link></div></FocusedPlanningAlert> : isTerminalCandidateExhausted ? null : threadId && !foodClarification && !recipeClarification ? <section aria-labelledby="plan-adjustment-title" className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm"><h2 className="text-base font-semibold leading-6" id="plan-adjustment-title">调整这份计划</h2><Label htmlFor="plan-adjustment">告诉我们想换什么</Label><textarea aria-describedby={adjustmentError ? 'plan-adjustment-error' : 'plan-adjustment-help'} aria-invalid={Boolean(adjustmentError)} className="min-h-20 w-full resize-y rounded-lg border border-input bg-card px-3 py-2 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" id="plan-adjustment" maxLength={500} onChange={(event) => setAdjustmentText(event.target.value)} placeholder="例如：午餐换成番茄炒蛋，或午餐换清淡一些" value={adjustmentText} /><p className="text-[13px] leading-5 text-muted-foreground" id="plan-adjustment-help">指定菜名时会查询受控目录；多个结果需由你确认。写明“今天”或“本次”的偏好只用于当前计划；明确的长期偏好会保存到饮食偏好。</p>{adjustmentError ? <p className="text-[13px] leading-5 text-destructive" id="plan-adjustment-error" role="alert">{adjustmentError}</p> : null}<Button className="h-11 w-full aria-disabled:opacity-50" aria-disabled={adjusting} onClick={() => void submitAdjustment(adjustmentText)} type="button">{adjusting ? '正在提交调整…' : '提交调整'}</Button></section> : foodClarification || recipeClarification ? null : <p className="text-sm text-muted-foreground">餐单已保存；调整会话已过期，可重新生成今日计划。</p>}</section> : null}
    {foodClarification || recipeClarification ? <PendingAdjustmentForm text={adjustmentText} /> : null}
    {recipeClarification ? <RecipeCandidateChoice report={recipeClarification} selectedId={selectedRecipeId} busy={adjusting} onSelect={setSelectedRecipeId} onSubmit={() => void submitRecipeCandidate()} /> : null}
    {foodClarification ? <><section aria-labelledby="food-candidate-title" className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm"><h2 className="text-base font-semibold leading-6" id="food-candidate-title">请选择要替换的菜品</h2><p className="text-[15px] leading-6 text-muted-foreground">{foodClarification.message}</p><div className="space-y-2" role="radiogroup" aria-labelledby="food-candidate-title">{foodClarification.candidates.map((candidate) => <button aria-checked={selectedFoodId === candidate.food_id} className="flex min-h-14 w-full items-center justify-between rounded-lg border border-input px-4 py-3 text-left text-sm transition-colors hover:bg-accent aria-checked:border-primary aria-checked:bg-accent" key={`${candidate.food_id}:${candidate.catalog_version}`} onClick={() => setSelectedFoodId(candidate.food_id)} role="radio" type="button"><span className="font-medium">{candidate.label}</span>{candidate.source_name ? <span className="text-xs text-muted-foreground">{candidate.source_name}</span> : null}</button>)}</div><p className="text-[13px] leading-5 text-muted-foreground">请选择后再提交；系统不会自动替你选中。</p><Button className="h-11 w-full" disabled={!selectedFoodId || adjusting} onClick={() => void submitFoodCandidate()} type="button">{adjusting ? '正在提交…' : '提交选择'}</Button></section></> : null}
    <footer className="text-center text-[13px] leading-5 text-muted-foreground">普通饮食参考，不替代医疗建议。</footer>
  </section>
}
