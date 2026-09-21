import { Trash2 } from 'lucide-react'
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
  const [itemGrams, setItemGrams] = useState<Array<{ itemId: string; name: string; grams: string }>>([])
  const { register, handleSubmit, reset, formState: { errors } } = useForm<MealMetadataEditForm>({
    resolver: zodResolver(mealMetadataEditSchema), defaultValues: { mealSlot: '', consumedAt: '' },
  })
  useEffect(() => {
    let active = true
    void getMealRecord(request, recordId).then((record) => {
      if (!active) return
      reset({ mealSlot: record.meal_slot ?? '', consumedAt: localMealTime(new Date(record.consumed_at)) })
      setItemGrams(record.items.map((item) => ({ itemId: item.id, name: item.display_name, grams: item.grams.replace(/(\.\d*?[1-9])0+$|\.0+$/, '$1') })))
      setLoaded(true)
    }).catch(() => { if (active) setError('无法加载记录。') })
    return () => { active = false }
  }, [recordId, request, reset])

  async function save(values: MealMetadataEditForm) {
    if (saving || !loaded) return
    setSaving(true); setError('')
    try {
      if (itemGrams.some((item) => !/^\d+(?:\.\d{1,3})?$/.test(item.grams) || Number(item.grams) <= 0 || Number(item.grams) > 2000)) {
        setError('每项份量必须是 0–2000g 之间、最多三位小数的数字。'); setSaving(false); return
      }
      await updateMealRecord(
        request,
        recordId,
        { consumedAt: new Date(values.consumedAt).toISOString(), mealSlot: values.mealSlot || null },
        itemGrams.length ? itemGrams.map(({ itemId, grams }) => ({ itemId, grams })) : undefined,
      )
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
    {!loaded && !error ? <p className="text-sm text-muted-foreground">正在加载记录…</p> : null}
    <form className="space-y-4" onSubmit={handleSubmit(save)} noValidate>
      <fieldset className="space-y-4" disabled={saving || !loaded}>
        <section className="space-y-4 rounded-xl border border-border bg-card p-4"><h2 className="text-base font-semibold">用餐信息</h2>
        <div className="space-y-2"><Label htmlFor="meal-slot">餐次</Label><select className="h-11 w-full rounded-lg border border-input bg-card px-3 text-base" id="meal-slot" {...register('mealSlot')}><option value="">未分类</option>{Object.entries(mealSlotLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div className="space-y-2"><Label htmlFor="consumed-at">用餐时间</Label><Input className="h-11" id="consumed-at" max={localMealTime()} type="datetime-local" {...register('consumedAt')} aria-invalid={Boolean(errors.consumedAt)} aria-describedby="edit-time-help" /><p className="text-[13px] text-muted-foreground" id="edit-time-help">当地时间 · 餐次需单独选择</p></div>
        </section>
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-base font-semibold">食物份量</h2><p className="mt-1 text-xs text-muted-foreground">修改克数，营养自动重算</p>
          <div className="mt-2 divide-y divide-border">{itemGrams.map((item, index) => <div className="flex items-center justify-between gap-3 py-3" key={item.itemId}>
            <Label className="min-w-0 flex-1 break-words text-sm leading-6" htmlFor={`item-grams-${item.itemId}`}>{item.name}<span className="sr-only">份量（克）</span></Label>
            <div className="relative w-28 shrink-0"><Input className="h-11 pr-8 text-right tabular-nums" id={`item-grams-${item.itemId}`} inputMode="decimal" value={item.grams} onChange={(event) => setItemGrams((current) => current.map((entry, position) => position === index ? { ...entry, grams: event.target.value } : entry))} /><span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-muted-foreground">克</span></div>
          </div>)}</div>
          {!itemGrams.length ? <p className="mt-3 text-sm text-muted-foreground">暂无可调整的食物</p> : null}
        </section>
        {errors.consumedAt ? <p className="text-sm text-destructive" role="alert">{errors.consumedAt.message}</p> : null}
        <Button className="h-11 w-full" disabled={saving || !loaded} type="submit">{saving ? '正在保存…' : '保存修改'}</Button>
      </fieldset>
    </form>
    {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
    <div className="border-t border-border pt-2"><Button className="min-h-11 w-full text-destructive hover:bg-destructive/10 hover:text-destructive" disabled={saving || !loaded} onClick={() => setOpen(true)} type="button" variant="ghost"><Trash2 aria-hidden="true" className="size-4" />删除餐食记录</Button></div>
    <AlertDialog onOpenChange={setOpen} open={open}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>删除这条餐食记录？</AlertDialogTitle><AlertDialogDescription>删除后，这条记录将无法恢复。</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>取消</AlertDialogCancel><AlertDialogAction disabled={saving} onClick={() => void remove()} variant="destructive">确认删除</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </section>
}
