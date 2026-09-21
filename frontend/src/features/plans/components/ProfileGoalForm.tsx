import { useEffect, useRef, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AlertTriangle, ChevronRight, Sparkles } from 'lucide-react'

import { getMemoryPreferenceSummary } from '@/features/memory/api/client'
import { getPlanningProfile, PlanningApiError, startDietPlanning } from '../api/client'
import { profileGoalFormSchema, type DietPlanningStartResponse, type PlanningProfile, type ProfileGoalFormValues } from '../api/schemas'

const activityLabels: Record<string, string> = { sedentary: '久坐', light: '轻度', moderate: '中度', high: '高度', very_high: '非常高' }
const goalLabels: Record<string, string> = { maintain: '维持体重', loss: '减重', gain: '增重' }
const speedLabels: Record<string, string> = { maintain: '维持', gradual_loss: '循序渐进减重', gradual_gain: '循序渐进增重' }

const emptyValues: ProfileGoalFormValues = {
  height_cm: '', weight_kg: '', age_years: undefined as unknown as number, formula_variant: undefined as unknown as ProfileGoalFormValues['formula_variant'],
  activity_level: undefined as unknown as ProfileGoalFormValues['activity_level'], goal: undefined as unknown as ProfileGoalFormValues['goal'], goal_speed: undefined as unknown as ProfileGoalFormValues['goal_speed'], preference_reviewed: false, save_profile: false,
}

export type PreferenceSummaries = { exclusions: string[]; tastePreferences: string[] }

type ProfileGoalFormProps = {
  initialValues?: PlanningProfile | null
  preferenceSummaries?: PreferenceSummaries
  isLoading?: boolean
  preferenceLoadError?: boolean
  profileLoadError?: boolean
  onStarted?: (snapshot: DietPlanningStartResponse) => void
}

export function ProfileGoalForm({ initialValues, preferenceSummaries, isLoading = false, preferenceLoadError = false, profileLoadError = false, onStarted }: ProfileGoalFormProps) {
  const { request } = useAuth()
  const submitButtonRef = useRef<HTMLButtonElement>(null)
  const [pageError, setPageError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const profileQuery = useQuery({ queryKey: ['planning-profile'], queryFn: () => getPlanningProfile(request), enabled: initialValues === undefined })
  const memoriesQuery = useQuery({ queryKey: ['planning-preference-summary'], queryFn: () => getMemoryPreferenceSummary(request), enabled: preferenceSummaries === undefined })
  const form = useForm<ProfileGoalFormValues>({ defaultValues: emptyValues, resolver: zodResolver(profileGoalFormSchema) })
  const profile = initialValues === undefined ? profileQuery.data : initialValues
  const preferences = preferenceSummaries ?? memoriesQuery.data ?? { exclusions: [], tastePreferences: [] }
  const preferenceKey = JSON.stringify(preferences)

  useEffect(() => {
    // Background refetches can change what is being confirmed; never reuse stale consent.
    form.setValue('preference_reviewed', false)
  }, [form, preferenceKey])

  useEffect(() => {
    if (!profile) return
    form.reset({
      height_cm: String(Number(profile.height_cm)), weight_kg: String(Number(profile.weight_kg)), age_years: profile.age_years,
      formula_variant: profile.formula_variant, activity_level: profile.activity_level, goal: profile.goal, goal_speed: profile.goal_speed,
      preference_reviewed: false, save_profile: false,
    })
  }, [form, profile])

  const submit = form.handleSubmit(async (values) => {
    if (!profile || profileLoadError || profileQuery.isError || preferenceLoadError || memoriesQuery.isError) return
    setPageError('')
    setStatusMessage('')
    try {
      const snapshot = await startDietPlanning(request, {
        profile: {
          height_cm: values.height_cm, weight_kg: values.weight_kg, age_years: values.age_years,
          formula_variant: values.formula_variant, activity_level: values.activity_level, goal: values.goal, goal_speed: values.goal_speed,
          is_pregnant_or_breastfeeding: false, has_disease_or_treatment: false, uses_medication: false,
          has_eating_disorder_or_self_harm_risk: false, has_extreme_weight_control_goal: false,
        },
        preferences: { confirmed: values.preference_reviewed, exclusions: preferences.exclusions, taste_preferences: preferences.tastePreferences },
        save_profile: values.save_profile,
      })
      setStatusMessage('计划请求已提交。')
      onStarted?.(snapshot)
    } catch (error) {
      if (error instanceof PlanningApiError) {
        const fieldMap: Record<string, keyof ProfileGoalFormValues> = {
          'profile.height_cm': 'height_cm', 'profile.weight_kg': 'weight_kg', 'profile.age_years': 'age_years',
          'profile.formula_variant': 'formula_variant', 'profile.activity_level': 'activity_level', 'profile.goal': 'goal', 'profile.goal_speed': 'goal_speed',
        }
        for (const [field, message] of Object.entries(error.fieldErrors)) {
          const target = fieldMap[field]
          if (target) form.setError(target, { type: 'server', message })
        }
        setPageError(error.message)
        return
      }
      setPageError('暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。')
    } finally { window.requestAnimationFrame(() => submitButtonRef.current?.focus()) }
  })

  const loading = isLoading || profileQuery.isLoading || memoriesQuery.isLoading
  const showPreferenceLoadError = preferenceLoadError || memoriesQuery.isError

  return <form className="space-y-4" noValidate onSubmit={submit}>
    {loading ? <p role="status">正在读取身体资料…</p> : profileLoadError || profileQuery.isError ? <Alert variant="destructive"><AlertDescription>无法读取身体资料，请返回“我的”检查后重试。<a className="flex min-h-11 items-center text-primary underline" href="/app/me/profile">查看个人资料</a></AlertDescription></Alert> : profile ? <section className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-sm" aria-labelledby="body-data-title">
      <div className="flex items-center justify-between gap-3"><h2 className="text-base font-semibold" id="body-data-title"><span aria-hidden="true" className="mr-2 text-sm text-primary">01</span>身体资料与目标</h2><a className="inline-flex min-h-11 items-center text-sm font-medium text-primary" href="/app/me/profile">修改</a></div>
      <dl className="grid grid-cols-2 gap-3">
        {([['身高', `${Number(profile.height_cm)} cm`], ['体重', `${Number(profile.weight_kg)} kg`], ['年龄', `${profile.age_years} 岁`], ['估算参数', profile.formula_variant === 'mifflin_st_jeor_male' ? '男性参数' : '女性参数'], ['活动水平', activityLabels[profile.activity_level]], ['饮食目标', `${goalLabels[profile.goal]} · ${speedLabels[profile.goal_speed]}`]]).map(([label, value], index) => <div className={`min-w-0 rounded-md bg-muted p-2 text-center ${index >= 4 ? 'col-span-2 text-left' : ''}`} key={label}><dt className="text-[13px] text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-sm font-semibold tabular-nums">{value}</dd></div>)}
      </dl>
    </section> : <section className="flex gap-3 rounded-xl border border-border bg-card p-4 shadow-sm"><span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning"><AlertTriangle aria-hidden="true" className="size-5" /></span><div><h2 className="text-base font-semibold">尚未设置身体资料</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">填写资料与目标后即可生成餐单。</p><a className="mt-3 inline-flex min-h-11 w-40 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground" href="/app/me/profile">去填写<ChevronRight aria-hidden="true" className="size-4" /></a></div></section>}
    <section aria-labelledby="preference-title" className="space-y-3 rounded-xl border border-border bg-card p-4 text-sm leading-6 shadow-sm"><h2 className="text-base font-semibold leading-6" id="preference-title"><span aria-hidden="true" className="mr-2 text-sm text-primary">02</span>本次饮食偏好</h2>{showPreferenceLoadError ? <Alert variant="destructive"><AlertDescription>暂时无法读取饮食偏好，请稍后重试。</AlertDescription></Alert> : <><p>忌口：{preferences.exclusions.length ? `已确认 ${preferences.exclusions.join('、')}` : '本次确认无'}</p><p>口味：{preferences.tastePreferences.length ? `已确认 ${preferences.tastePreferences.join('、')}` : '本次确认无'}</p><a className="flex min-h-11 items-center justify-between text-sm font-medium text-primary" href="/app/me/memories">管理饮食偏好<ChevronRight aria-hidden="true" className="size-4" /></a>{form.formState.errors.preference_reviewed?.message ? <p className="text-sm text-destructive" role="alert">{form.formState.errors.preference_reviewed.message}</p> : null}</>}</section>
    <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-border bg-card px-3 py-2 text-sm transition-colors has-[:checked]:border-primary/40 has-[:checked]:bg-accent/60"><input className="size-4" type="checkbox" {...form.register('preference_reviewed')} />我已复核以上饮食偏好</label>
    {pageError ? <Alert variant="destructive"><AlertDescription>{pageError}</AlertDescription></Alert> : null}
    {statusMessage ? <p aria-live="polite" className="text-sm text-muted-foreground">{statusMessage}</p> : null}
    <Button className="h-11 w-full" disabled={!profile || profileLoadError || profileQuery.isError || loading || form.formState.isSubmitting || showPreferenceLoadError} ref={submitButtonRef} type="submit"><Sparkles aria-hidden="true" className="size-5" />{form.formState.isSubmitting ? '正在生成餐单…' : '生成今日餐单'}</Button>
  </form>
}
