import { useEffect, useMemo, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { deletePlanningProfile, getPlanningProfile, PlanningApiError, planningProfileQueryKey, planningProfileWriteSchema, replacePlanningProfile, type PlanningProfileWrite } from '../api/profile'
import type { PlanningProfile } from '../api/schemas'

const activityLabels: Record<PlanningProfile['activity_level'], string> = {
  sedentary: '久坐',
  light: '轻度活动',
  moderate: '中度活动',
  high: '高度活动',
  very_high: '非常高活动量',
}

const goalLabels: Record<PlanningProfile['goal'], string> = {
  maintain: '维持体重',
  loss: '减重',
  gain: '增重',
}

const speedLabels: Record<PlanningProfile['goal_speed'], string> = {
  maintain: '维持',
  gradual_loss: '循序渐进减重',
  gradual_gain: '循序渐进增重',
}

function toFormValues(profile: PlanningProfile): PlanningProfileWrite {
  return {
    height_cm: String(Number(profile.height_cm)),
    weight_kg: String(Number(profile.weight_kg)),
    age_years: profile.age_years,
    formula_variant: profile.formula_variant,
    activity_level: profile.activity_level,
    goal: profile.goal,
    goal_speed: profile.goal_speed,
  }
}

const emptyProfileFormValues: PlanningProfileWrite = {
  height_cm: '',
  weight_kg: '',
  age_years: undefined as unknown as number,
  formula_variant: undefined as unknown as PlanningProfileWrite['formula_variant'],
  activity_level: undefined as unknown as PlanningProfileWrite['activity_level'],
  goal: undefined as unknown as PlanningProfileWrite['goal'],
  goal_speed: undefined as unknown as PlanningProfileWrite['goal_speed'],
}

/**
 * This page owns only the minimal profile authority. Long-term preferences deliberately stay
 * behind the memory feature link so a second preference writer cannot silently diverge.
 */
export function PersonalProfilePage() {
  const { request } = useAuth()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [pageError, setPageError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const profileQuery = useQuery({ queryKey: planningProfileQueryKey, queryFn: () => getPlanningProfile(request) })
  const profile = profileQuery.data
  const initialValues = useMemo(() => profile ? toFormValues(profile) : null, [profile])

  const updateMutation = useMutation({
    mutationFn: (payload: PlanningProfileWrite) => replacePlanningProfile(request, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(planningProfileQueryKey, updated)
      void queryClient.invalidateQueries({ queryKey: planningProfileQueryKey })
      setEditing(false)
      setPageError('')
      setFieldErrors({})
      setNotice('')
    },
    onError: (error) => {
      if (error instanceof PlanningApiError && Object.keys(error.fieldErrors).length > 0) {
        setFieldErrors(error.fieldErrors)
        setPageError('')
        return
      }
      setPageError(error instanceof PlanningApiError ? error.message : '保存个人资料失败，请稍后重试。')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePlanningProfile(request),
    onSuccess: () => {
      queryClient.setQueryData(planningProfileQueryKey, null)
      void queryClient.invalidateQueries({ queryKey: planningProfileQueryKey })
      void queryClient.invalidateQueries({ queryKey: ['diet-planning'] })
      setDeleteOpen(false)
      setEditing(false)
      setPageError('')
      setFieldErrors({})
      setNotice('个人资料已删除。后续计划不会再读取这些资料。')
    },
    onError: (error) => {
      setDeleteOpen(false)
      setPageError(error instanceof PlanningApiError ? error.message : '删除个人资料失败，请稍后重试。')
    },
  })

  useEffect(() => {
    if (profile !== null || !notice.startsWith('个人资料已删除')) return
    document.querySelector<HTMLHeadingElement>('h1')?.focus()
  }, [notice, profile])

  if (profileQuery.isLoading) return <p className="text-sm text-muted-foreground">正在读取个人资料…</p>
  if (profileQuery.isError) return <ProfileError message="暂时无法读取个人资料，请稍后重试。" onRetry={() => void profileQuery.refetch()} />
  if (!profile && !editing) return <ProfileEmpty notice={notice} onCreate={() => setEditing(true)} />

  return (
    <section className="space-y-4" aria-labelledby="personal-profile-content-title">
      <div>
        <h2 className="text-base font-semibold leading-6" id="personal-profile-content-title">身体资料与目标</h2>
      </div>
      {notice ? <p aria-live="polite" className="text-sm text-muted-foreground">{notice}</p> : null}
      {pageError ? <Alert variant="destructive"><AlertDescription>{pageError}</AlertDescription></Alert> : null}
      {editing
        ? <ProfileEditForm fieldErrors={fieldErrors} initialValues={initialValues ?? emptyProfileFormValues} isSaving={updateMutation.isPending} onCancel={() => { setEditing(false); setPageError(''); setFieldErrors({}) }} onSave={(payload) => { setFieldErrors({}); updateMutation.mutate(payload) }} />
        : <ProfileView profile={profile!} onDelete={() => setDeleteOpen(true)} onEdit={() => { setFieldErrors({}); setEditing(true) }} />}
      <AlertDialog onOpenChange={setDeleteOpen} open={deleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除个人资料？</AlertDialogTitle>
            <AlertDialogDescription>删除个人资料后，后续计划将不再读取这些身体资料和目标。此操作无法撤销。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate()} variant="destructive">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

function ProfileView({ onDelete, onEdit, profile }: { onDelete: () => void; onEdit: () => void; profile: PlanningProfile }) {
  const entries: Array<[string, string]> = [
    ['身高', `${Number(profile.height_cm)} cm`],
    ['体重', `${Number(profile.weight_kg)} kg`],
    ['年龄', `${profile.age_years} 岁`],
    ['估算参数', profile.formula_variant === 'mifflin_st_jeor_male' ? '男性参数' : '女性参数'],
    ['日常活动', activityLabels[profile.activity_level]],
    ['目标', goalLabels[profile.goal]],
    ['目标速度', speedLabels[profile.goal_speed]],
  ]
  return <><dl className="divide-y divide-border rounded-xl border border-border bg-card px-4 shadow-sm">{entries.map(([label, value]) => <div className="flex min-h-12 items-center justify-between gap-4 py-3" key={label}><dt className="shrink-0 text-sm text-muted-foreground">{label}</dt><dd className="min-w-0 break-words text-right text-base font-semibold tabular-nums">{value}</dd></div>)}</dl><a className="inline-flex min-h-11 items-center text-sm text-primary underline-offset-4 hover:underline focus-visible:outline-none" href="/app/me/memories">管理饮食偏好</a><div className="space-y-3 border-t border-border pt-4"><Button className="h-11 w-full" onClick={onEdit} type="button">编辑个人资料</Button><Button className="h-11 w-full" onClick={onDelete} type="button" variant="destructive">删除个人资料</Button></div></>
}

function ProfileEmpty({ notice, onCreate }: { notice: string; onCreate: () => void }) {
  return <section className="space-y-4"><h2 className="text-base font-semibold leading-6">还没有保存个人资料</h2><p className="text-sm leading-5 text-muted-foreground">在这里填写身体资料和目标，保存后即可用于生成餐单。</p>{notice ? <p aria-live="polite" className="text-sm text-muted-foreground">{notice}</p> : null}<a className="inline-flex min-h-11 items-center text-sm text-primary underline-offset-4 hover:underline focus-visible:outline-none" href="/app/me/memories">管理饮食偏好</a><Button className="h-11 w-full" onClick={onCreate}>填写身体资料与目标</Button></section>
}

function ProfileError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <Alert variant="destructive"><AlertDescription>{message}</AlertDescription><Button className="mt-3 h-11" onClick={onRetry} type="button" variant="outline">重新尝试</Button></Alert>
}

function ProfileEditForm({ fieldErrors, initialValues, isSaving, onCancel, onSave }: { fieldErrors: Record<string, string>; initialValues: PlanningProfileWrite; isSaving: boolean; onCancel: () => void; onSave: (values: PlanningProfileWrite) => void }) {
  const form = useForm<PlanningProfileWrite>({ defaultValues: initialValues, resolver: zodResolver(planningProfileWriteSchema) })
  const error = (name: keyof PlanningProfileWrite) => fieldErrors[name] ?? form.formState.errors[name]?.message
  return <form className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-sm" noValidate onSubmit={form.handleSubmit(onSave)}><ProfileField error={error('height_cm')} id="profile-height-error"><Label htmlFor="profile-height">身高</Label><div className="flex items-center gap-2"><Input aria-describedby="profile-height-error" className="h-11 tabular-nums" id="profile-height" inputMode="decimal" min="100" type="number" {...form.register('height_cm')} /><span className="text-sm text-muted-foreground">cm</span></div></ProfileField><ProfileField error={error('weight_kg')} id="profile-weight-error"><Label htmlFor="profile-weight">体重</Label><div className="flex items-center gap-2"><Input aria-describedby="profile-weight-error" className="h-11 tabular-nums" id="profile-weight" inputMode="decimal" min="20" type="number" {...form.register('weight_kg')} /><span className="text-sm text-muted-foreground">kg</span></div></ProfileField><ProfileField error={error('age_years')} id="profile-age-error"><Label htmlFor="profile-age">年龄</Label><div className="flex items-center gap-2"><Input aria-describedby="profile-age-error" className="h-11 tabular-nums" id="profile-age" inputMode="numeric" min="1" type="number" {...form.register('age_years', { valueAsNumber: true })} /><span className="text-sm text-muted-foreground">岁</span></div></ProfileField><fieldset className="space-y-2"><legend className="text-sm font-medium">用于目标估算的身体参数</legend><label className="flex min-h-11 items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"><input type="radio" value="mifflin_st_jeor_male" {...form.register('formula_variant')} />使用男性参数</label><label className="flex min-h-11 items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"><input type="radio" value="mifflin_st_jeor_female" {...form.register('formula_variant')} />使用女性参数</label>{error('formula_variant') ? <p className="text-sm text-destructive" role="alert">{error('formula_variant')}</p> : null}</fieldset><SelectField error={error('activity_level')} id="profile-activity" label="日常活动水平" options={[['sedentary', '久坐'], ['light', '轻度活动'], ['moderate', '中度活动'], ['high', '高度活动'], ['very_high', '非常高活动量']]} registration={form.register('activity_level')} /><SelectField error={error('goal')} id="profile-goal" label="目标" options={[['maintain', '维持体重'], ['loss', '减重'], ['gain', '增重']]} registration={form.register('goal')} /><SelectField error={error('goal_speed')} id="profile-goal-speed" label="目标速度" options={[['maintain', '维持'], ['gradual_loss', '循序渐进减重'], ['gradual_gain', '循序渐进增重']]} registration={form.register('goal_speed')} /><div className="flex gap-3"><Button className="h-11 flex-1" disabled={isSaving} type="submit">{isSaving ? '正在保存…' : '保存个人资料'}</Button><Button className="h-11 flex-1" disabled={isSaving} onClick={onCancel} type="button" variant="outline">取消</Button></div></form>
}

function ProfileField({ children, error, id }: { children: React.ReactNode; error?: string; id: string }) {
  return <div className="space-y-2">{children}{error ? <p className="text-sm text-destructive" id={id} role="alert">{error}</p> : null}</div>
}

function SelectField({ error, id, label, options, registration }: { error?: string; id: string; label: string; options: Array<[string, string]>; registration: ReturnType<ReturnType<typeof useForm<PlanningProfileWrite>>['register']> }) {
  return <ProfileField error={error} id={`${id}-error`}><Label htmlFor={id}>{label}</Label><select aria-describedby={`${id}-error`} className="h-11 w-full rounded-lg border border-input bg-card px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" id={id} {...registration}><option value="">请选择</option>{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select></ProfileField>
}
