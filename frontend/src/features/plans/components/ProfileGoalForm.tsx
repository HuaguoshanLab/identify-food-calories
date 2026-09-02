import { useEffect, useRef, useState, type ComponentProps, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { listMemories } from '@/features/memory/api/client'
import { getPlanningProfile, PlanningApiError, startDietPlanning } from '../api/client'
import { profileGoalFormSchema, type DietPlanningStartResponse, type PlanningProfile, type ProfileGoalFormValues } from '../api/schemas'

const activityOptions = [
  ['sedentary', '久坐', '大部分时间坐着，几乎不运动'],
  ['light', '轻度', '每周有少量轻松活动'],
  ['moderate', '中度', '每周规律中等强度活动'],
  ['high', '高度', '大多数天有较高强度活动'],
  ['very_high', '非常高', '高强度训练或体力工作为主'],
] as const

const goalOptions = [['maintain', '维持体重'], ['loss', '减重'], ['gain', '增重']] as const
const speedOptions = [['maintain', '维持'], ['gradual_loss', '循序渐进减重'], ['gradual_gain', '循序渐进增重']] as const

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
  onStarted?: (snapshot: DietPlanningStartResponse) => void
}

export function ProfileGoalForm({ initialValues, preferenceSummaries, isLoading = false, preferenceLoadError = false, onStarted }: ProfileGoalFormProps) {
  const { request } = useAuth()
  const submitButtonRef = useRef<HTMLButtonElement>(null)
  const [pageError, setPageError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const profileQuery = useQuery({ queryKey: ['planning-profile'], queryFn: () => getPlanningProfile(request), enabled: initialValues === undefined })
  const memoriesQuery = useQuery({ queryKey: ['planning-preference-summary'], queryFn: () => listMemories(request), enabled: preferenceSummaries === undefined })
  const form = useForm<ProfileGoalFormValues>({ defaultValues: emptyValues, resolver: zodResolver(profileGoalFormSchema) })
  const profile = initialValues === undefined ? profileQuery.data : initialValues
  const preferences = preferenceSummaries ?? {
    exclusions: (memoriesQuery.data ?? []).filter((memory) => memory.category === 'avoidance').map((memory) => memory.canonical_text),
    tastePreferences: (memoriesQuery.data ?? []).filter((memory) => memory.category === 'stable_preference').map((memory) => memory.canonical_text),
  }

  useEffect(() => {
    if (!profile) return
    form.reset({
      height_cm: String(Number(profile.height_cm)), weight_kg: String(Number(profile.weight_kg)), age_years: profile.age_years,
      formula_variant: profile.formula_variant, activity_level: profile.activity_level, goal: profile.goal, goal_speed: profile.goal_speed,
      preference_reviewed: false, save_profile: false,
    })
  }, [form, profile])

  const submit = form.handleSubmit(async (values) => {
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
        if (Object.keys(error.fieldErrors).length === 0) setPageError(error.message)
        return
      }
      setPageError('暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。')
    } finally { window.requestAnimationFrame(() => submitButtonRef.current?.focus()) }
  })

  const loading = isLoading || profileQuery.isLoading || memoriesQuery.isLoading
  const showPreferenceLoadError = preferenceLoadError || memoriesQuery.isError

  return <form className="space-y-4" noValidate onSubmit={submit}>
    <section aria-labelledby="body-data-title" className="space-y-3">
      <h2 className="text-xl font-semibold" id="body-data-title">身体资料</h2>
      <FieldError error={form.formState.errors.height_cm?.message} id="height-cm-error"><Label htmlFor="height-cm">身高</Label><div className="flex items-center gap-2"><Input aria-describedby="height-cm-error" className="h-11 tabular-nums" id="height-cm" inputMode="decimal" type="number" {...form.register('height_cm')} /><span className="text-sm text-muted-foreground">cm</span></div></FieldError>
      <FieldError error={form.formState.errors.weight_kg?.message} id="weight-kg-error"><Label htmlFor="weight-kg">体重</Label><div className="flex items-center gap-2"><Input aria-describedby="weight-kg-error" className="h-11 tabular-nums" id="weight-kg" inputMode="decimal" type="number" {...form.register('weight_kg')} /><span className="text-sm text-muted-foreground">kg</span></div></FieldError>
      <FieldError error={form.formState.errors.age_years?.message} id="age-years-error"><Label htmlFor="age-years">年龄</Label><div className="flex items-center gap-2"><Input aria-describedby="age-years-error" className="h-11 tabular-nums" id="age-years" inputMode="numeric" type="number" {...form.register('age_years', { valueAsNumber: true })} /><span className="text-sm text-muted-foreground">岁</span></div></FieldError>
      <fieldset className="space-y-2"><legend className="text-sm font-medium">用于目标估算的身体参数</legend><p className="text-sm text-muted-foreground">目标估算结果是饮食参考，不是医疗诊断。</p><div className="grid gap-2"><Choice label="使用男性参数" value="mifflin_st_jeor_male" {...form.register('formula_variant')} /><Choice label="使用女性参数" value="mifflin_st_jeor_female" {...form.register('formula_variant')} /></div>{form.formState.errors.formula_variant?.message ? <p className="text-sm text-destructive" role="alert">{form.formState.errors.formula_variant.message}</p> : null}</fieldset>
    </section>
    <fieldset className="space-y-2"><legend className="text-sm font-medium">日常活动水平</legend><div className="grid gap-2">{activityOptions.map(([value, label, detail]) => <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm" key={value}><input className="size-4" type="radio" value={value} {...form.register('activity_level')} /><span><strong>{label}</strong><span className="ml-1 text-muted-foreground">{detail}</span></span></label>)}</div>{form.formState.errors.activity_level?.message ? <p className="text-sm text-destructive" role="alert">{form.formState.errors.activity_level.message}</p> : null}</fieldset>
    <section className="space-y-3" aria-labelledby="goal-title"><h2 className="text-xl font-semibold" id="goal-title">目标与速度</h2><fieldset className="space-y-2"><legend className="text-sm font-medium">本次目标</legend><div className="grid gap-2">{goalOptions.map(([value, label]) => <Choice key={value} label={label} value={value} {...form.register('goal')} />)}</div>{form.formState.errors.goal?.message ? <p className="text-sm text-destructive" role="alert">{form.formState.errors.goal.message}</p> : null}</fieldset><FieldError error={form.formState.errors.goal_speed?.message} id="goal-speed-error"><Label htmlFor="goal-speed">目标速度</Label><select aria-describedby="goal-speed-error" className="h-11 w-full rounded-lg border border-input bg-transparent px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" id="goal-speed" {...form.register('goal_speed')}><option value="">请选择保守预设</option>{speedOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></FieldError></section>
    <section aria-labelledby="preference-title" className="space-y-2"><h2 className="text-xl font-semibold" id="preference-title">本次饮食偏好</h2>{showPreferenceLoadError ? <Alert variant="destructive"><AlertDescription>暂时无法读取饮食偏好，请稍后重试。</AlertDescription></Alert> : <><p>忌口：{preferences.exclusions.length ? `已确认 ${preferences.exclusions.join('、')}` : '本次确认无'}</p><p>口味：{preferences.tastePreferences.length ? `已确认 ${preferences.tastePreferences.join('、')}` : '本次确认无'}</p><a className="inline-flex min-h-11 items-center text-sm text-primary underline-offset-4 hover:underline" href="/app/me/memories">管理饮食偏好</a><label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"><input className="size-4" type="checkbox" {...form.register('preference_reviewed')} />我已复核以上饮食偏好</label>{form.formState.errors.preference_reviewed?.message ? <p className="text-sm text-destructive" role="alert">{form.formState.errors.preference_reviewed.message}</p> : null}</>}</section>
    <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"><input className="size-4" type="checkbox" {...form.register('save_profile')} />将本次身体资料和目标保存到个人资料</label>
    <p className="text-sm text-muted-foreground">生成前会由系统计算目标区间，并校验餐单是否符合已确认约束。</p>
    {pageError ? <Alert variant="destructive"><AlertDescription>{pageError}</AlertDescription></Alert> : null}
    {statusMessage ? <p aria-live="polite" className="text-sm text-muted-foreground">{statusMessage}</p> : null}
    <Button className="h-11 w-full" disabled={loading || form.formState.isSubmitting || showPreferenceLoadError} ref={submitButtonRef} type="submit">{form.formState.isSubmitting ? '正在生成餐单…' : '生成今日餐单'}</Button>
  </form>
}

function Choice({ label, value, ...inputProps }: { label: string; value: string } & ComponentProps<'input'>) {
  return <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"><input className="size-4" type="radio" value={value} {...inputProps} />{label}</label>
}

function FieldError({ children, error, id }: { children: ReactNode; error?: string; id: string }) {
  return <div className="space-y-2">{children}{error ? <p className="text-sm text-destructive" id={id} role="alert">{error}</p> : null}</div>
}
