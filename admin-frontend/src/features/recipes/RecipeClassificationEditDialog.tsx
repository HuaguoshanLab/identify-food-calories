import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { RecipeDialog } from './RecipeDialog'
import { mealSlotsSchema, mealSlotLabels, classificationSchema, ingredientTagLabels, purposeLabels, roleLabels, reviewClassifications, type RecipeCandidate } from './api'

const schema = classificationSchema.extend({ meal_slots: mealSlotsSchema, evidence: z.string().trim().min(1, '请填写分类依据').max(500), reason: z.string().trim().min(1, '请填写修改原因').max(500) })
export function RecipeClassificationEditDialog({ item, accessToken, onClose, onSuccess, onSecurityError }: Readonly<{
  item: RecipeCandidate; accessToken: string; onClose: () => void; onSuccess: () => void; onSecurityError: (error: unknown) => boolean
}>) {
  const { register, handleSubmit, formState: { isSubmitting, errors } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { meal_slots: item.meal_slots, version: 'recipe-classification.v1', purpose: item.classification?.purpose ?? 'unknown', role: item.classification?.role ?? 'unknown', ingredient_tags: item.classification?.ingredient_tags ?? [], evidence: item.classification?.evidence ?? '', basis: 'admin_review', reason: '' } })
  const request = useRef({ payload: '', key: '' })
  const [error, setError] = useState('')
  const submit = handleSubmit(async ({ reason, meal_slots, ...classification }) => {
    const entries = [{ id: item.id, revision: item.revision, catalog_food_name: item.catalog_food_name, classification, meal_slots }]
    const payload = JSON.stringify({ entries, reason })
    if (request.current.payload !== payload) request.current = { payload, key: crypto.randomUUID() }
    setError('')
    try { await reviewClassifications(accessToken, entries, reason, request.current.key); onSuccess() }
    catch (failure) { if (!onSecurityError(failure)) setError('保存未确认，可重试；若版本冲突，请关闭并刷新列表后重新编辑。') }
  })
  return <RecipeDialog title={`编辑分类：${item.catalog_food_name}`} description="保存后用于新配餐；待确认不参选。用途决定能否整餐参选，午晚餐组合使用主食、蛋白质菜和蔬菜。标签只记录已知食材，不代表完整配料。" busy={isSubmitting} onClose={onClose} footer={<><button onClick={onClose} disabled={isSubmitting}>取消</button><button form="classification-edit" type="submit" disabled={isSubmitting} className="rounded bg-blue-600 px-4 py-2 text-white">保存修改</button></>}>
    <form id="classification-edit" className="space-y-4" onSubmit={submit}>
      <fieldset disabled={isSubmitting}><legend>适用餐次（多选）</legend><div className="flex gap-4 pt-2">{Object.entries(mealSlotLabels).map(([value, label]) => <label key={value}><input type="checkbox" value={value} {...register('meal_slots')} /> {label}</label>)}</div></fieldset>
      <div><label htmlFor="classification-purpose">配餐用途</label><select id="classification-purpose" {...register('purpose')} className="ml-3 rounded border p-2" disabled={isSubmitting}>{Object.entries(purposeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
      <div><label htmlFor="classification-role">餐内角色</label><select id="classification-role" {...register('role')} className="ml-3 rounded border p-2" disabled={isSubmitting}>{Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
      <fieldset disabled={isSubmitting}><legend>已知食材标签（多选）</legend><div className="grid grid-cols-3 gap-2 pt-2">{Object.entries(ingredientTagLabels).map(([value, label]) => <label key={value}><input type="checkbox" value={value} {...register('ingredient_tags')} /> {label}</label>)}</div></fieldset>
      <label className="block">分类依据<textarea {...register('evidence')} disabled={isSubmitting} className="block w-full rounded border p-2" /></label>
      <label className="block">修改原因<textarea {...register('reason')} disabled={isSubmitting} className="block w-full rounded border p-2" /></label>
      {Object.values(errors).map((error, index) => <p role="alert" key={index}>{error.message}</p>)}{error && <p role="alert">{error}</p>}
    </form>
  </RecipeDialog>
}
