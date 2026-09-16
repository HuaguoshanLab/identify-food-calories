import { zodResolver } from '@hookform/resolvers/zod'
import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { RecipeDialog } from './RecipeDialog'
import { changeRecipeMealRole, recipeMealRoleLabels, recipeMealRoleSchema } from './api'

const schema = z.object({ mealRole: recipeMealRoleSchema, reason: z.string().trim().min(1, '请填写修改原因。').max(500) })

export function RecipeRoleDialog({ accessToken, ids, onClose, onSuccess, onSecurityError }: Readonly<{
  accessToken: string; ids: string[]; onClose: () => void; onSuccess: (count: number) => void; onSecurityError: (error: unknown) => boolean
}>) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { mealRole: 'standalone', reason: '' } })
  const [error, setError] = useState('')
  const request = useRef({ payload: '', key: '' })
  const submit = handleSubmit(async values => {
    // Retries keep their key; changed form values start a new audited command.
    const payload = JSON.stringify({ ids, ...values })
    if (request.current.payload !== payload) request.current = { payload, key: crypto.randomUUID() }
    setError('')
    try {
      const result = await changeRecipeMealRole(accessToken, ids, values.mealRole, values.reason, request.current.key)
      onSuccess(result.changed_count)
    } catch (failure) {
      if (!onSecurityError(failure)) setError('修改未确认，请重试；若记录已删除，请关闭窗口并刷新列表。')
    }
  })
  return <RecipeDialog busy={isSubmitting} title="设置餐内角色" description={`为已选 ${ids.length} 条候选设置用途。请依据实际菜品信息分类，不确定时保留单独候选。`} onClose={onClose} footer={<><button className="h-9 rounded-md border px-4 text-sm" disabled={isSubmitting} onClick={onClose} type="button">取消</button><button className="h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50" disabled={isSubmitting} form="recipe-role-form" type="submit">保存角色</button></>}>
    <form className="space-y-4" id="recipe-role-form" onSubmit={submit}>
      <div className="text-sm"><label htmlFor="recipe-meal-role">餐内角色</label><select id="recipe-meal-role" className="mt-2 block h-10 w-full rounded border bg-card px-3" disabled={isSubmitting} {...register('mealRole')}>{recipeMealRoleSchema.options.map(role => <option key={role} value={role}>{recipeMealRoleLabels[role]}</option>)}</select></div>
      <p className="rounded border bg-muted/30 p-3 text-sm leading-6">午餐和晚餐可搭配主食、蛋白质菜与蔬菜；缺少任一角色时不会拼餐。其他配菜、饮品暂不参与生成。“单独候选”沿用现有选择方式，不表示营养搭配完整。历史餐单不受影响。</p>
      <label className="block text-sm">修改原因<textarea className="mt-2 block w-full rounded border bg-card p-3" disabled={isSubmitting} maxLength={500} rows={3} aria-invalid={Boolean(errors.reason)} aria-describedby={errors.reason ? 'role-reason-error' : undefined} {...register('reason')} /></label>
      {errors.reason && <p className="text-sm text-red-700" id="role-reason-error" role="alert">{errors.reason.message}</p>}
      {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
    </form>
  </RecipeDialog>
}
