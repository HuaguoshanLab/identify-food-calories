import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { deleteMealRecord, getMealRecord, updateMealRecord } from '../api/client'
import { localMealTime, mealSlotLabels, mealMetadataEditSchema, type MealMetadataEditForm } from '../api/mealMetadata'

export function MealRecordEditPage() {
  const { recordId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { request } = useAuth()
  const [loaded, setLoaded] = useState(false)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const { register, handleSubmit, reset, formState: { errors } } = useForm<MealMetadataEditForm>({
    resolver: zodResolver(mealMetadataEditSchema), defaultValues: { mealSlot: '', consumedAt: '' },
  })
  useEffect(() => {
    let active = true
    void getMealRecord(request, recordId).then((record) => {
      if (!active) return
      reset({ mealSlot: record.meal_slot ?? '', consumedAt: localMealTime(new Date(record.consumed_at)) })
      setLoaded(true)
    }).catch(() => { if (active) setError('无法加载记录。') })
    return () => { active = false }
  }, [recordId, request, reset])

  async function save(values: MealMetadataEditForm) {
    if (saving || !loaded) return
    setSaving(true); setError('')
    try {
      await updateMealRecord(request, recordId, { consumedAt: new Date(values.consumedAt).toISOString(), mealSlot: values.mealSlot || null })
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate(`/app/records/${recordId}`, { replace: true })
    } catch { setError('保存失败，请检查用餐时间或稍后重试。') } finally { setSaving(false) }
  }
  async function remove() {
    if (saving || !loaded) return
    setSaving(true)
    try {
      await deleteMealRecord(request, recordId)
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate('/app/records', { replace: true, state: { notice: '已删除' } })
    } catch { setError('删除失败，请稍后重试。') } finally { setSaving(false); setOpen(false) }
  }
  return <section className="space-y-4">
    <div><p className="text-sm text-muted-foreground">修改餐次或用餐时间不会重算已保存的营养快照。</p></div>
    {!loaded && !error ? <p className="text-sm text-muted-foreground">正在加载记录…</p> : null}
    <form className="space-y-4" onSubmit={handleSubmit(save)} noValidate>
      <fieldset className="space-y-4" disabled={saving || !loaded}>
        <div className="space-y-2"><Label htmlFor="meal-slot">餐次</Label><select className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base" id="meal-slot" {...register('mealSlot')}><option value="">未分类</option>{Object.entries(mealSlotLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div className="space-y-2"><Label htmlFor="consumed-at">用餐时间</Label><Input className="h-11" id="consumed-at" max={localMealTime()} type="datetime-local" {...register('consumedAt')} aria-invalid={Boolean(errors.consumedAt)} aria-describedby="edit-time-help" /><p className="text-[13px] text-muted-foreground" id="edit-time-help">按当前设备时区填写；修改时间不会自动改变餐次。</p></div>
        {errors.consumedAt ? <p className="text-sm text-destructive" role="alert">{errors.consumedAt.message}</p> : null}
        <Button className="h-11 w-full" disabled={saving || !loaded} type="submit">{saving ? '正在保存…' : '保存修改'}</Button>
      </fieldset>
    </form>
    {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
    <div className="border-t border-border pt-4"><h2 className="font-semibold text-destructive">危险操作</h2><p className="mt-1 text-sm text-muted-foreground">删除后，这条餐食记录将无法恢复。</p><Button className="mt-3 h-11 w-full" disabled={saving || !loaded} onClick={() => setOpen(true)} type="button" variant="destructive">删除餐食记录</Button></div>
    <AlertDialog onOpenChange={setOpen} open={open}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>删除这条餐食记录？</AlertDialogTitle><AlertDialogDescription>删除后，这条记录将无法恢复。</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>取消</AlertDialogCancel><AlertDialogAction disabled={saving} onClick={() => void remove()} variant="destructive">确认删除</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </section>
}
