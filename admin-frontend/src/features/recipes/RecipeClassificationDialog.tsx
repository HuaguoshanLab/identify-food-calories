import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { RecipeDialog } from './RecipeDialog'
import { previewClassifications, saveClassifications, purposeLabels, roleLabels, ingredientTagLabels } from './api'

const formSchema = z.object({ reason: z.string().trim().min(1, '请填写原因').max(500) })
export function RecipeClassificationDialog({ accessToken, ids, onClose, onSuccess, onSecurityError }: Readonly<{
  accessToken: string; ids: string[]; onClose: () => void; onSuccess: (count: number) => void; onSecurityError: (error: unknown) => boolean
}>) {
  const [reviewUnknown, setReviewUnknown] = useState(false)
  const preview = useQuery({ queryKey: ['recipe-classification-preview', ids, reviewUnknown], queryFn: () => previewClassifications(accessToken, ids, reviewUnknown), retry: false, staleTime: 0 })
  const { register, handleSubmit, formState: { isSubmitting, errors } } = useForm<z.infer<typeof formSchema>>({ resolver: zodResolver(formSchema), defaultValues: { reason: '' } })
  const request = useRef({ payload: '', key: '' })
  const [error, setError] = useState('')
  const submit = handleSubmit(async ({ reason }) => {
    if (!preview.data?.entries.length) return
    const payload = JSON.stringify({ entries: preview.data.entries, reason })
    if (request.current.payload !== payload) request.current = { payload, key: crypto.randomUUID() }
    setError('')
    try { const result = await saveClassifications(accessToken, preview.data.entries, reason, request.current.key, reviewUnknown); onSuccess(result.changed_count) }
    catch (failure) { if (!onSecurityError(failure)) setError('保存未确认；可重试。若数据版本已变化，请关闭后重新预览。') }
  })
  return <RecipeDialog title="补齐三维分类" description="根据菜名及参考资料补齐分类。只填未分类记录，保存后用于新配餐，不改变份量或历史；食材标签不代表完整配料。" busy={isSubmitting} onClose={onClose} footer={<><button type="button" onClick={onClose} disabled={isSubmitting}>取消</button><button className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50" type="submit" form="classification-form" disabled={isSubmitting || !preview.data?.entries.length}>保存分类</button></>}>
    <form id="classification-form" onSubmit={submit} className="space-y-4">
      <label className="block"><input type="checkbox" checked={reviewUnknown} onChange={event => setReviewUnknown(event.target.checked)} disabled={isSubmitting} /> 同时复核角色待确认的菜谱（仅保存有明确新依据的分类）</label>
      {preview.isPending && <p role="status">正在生成分类预览…</p>}
      {preview.isError && <p role="alert">预览失败，请关闭后重试；登录失效时请重新登录。</p>}
      {preview.data && <><p role="status">待补齐 {preview.data.entries.length} 条，已分类跳过 {preview.data.skipped_count} 条；其中 {preview.data.entries.filter(item => item.classification.role === 'unknown').length} 条角色待确认。</p>
        <div className="max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{['菜品', '配餐用途', '餐内角色', '食材标签', '依据'].map(label => <th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{preview.data.entries.map(item => <tr key={item.id}><td className="p-2">{item.catalog_food_name}</td><td>{purposeLabels[item.classification.purpose]}</td><td>{roleLabels[item.classification.role]}</td><td>{item.classification.ingredient_tags.map(tag => ingredientTagLabels[tag]).join('、') || '待确认'}</td><td className="p-2 text-xs">{item.classification.evidence}</td></tr>)}</tbody></table></div></>}
      <label className="block">修改原因<textarea {...register('reason')} className="mt-2 block w-full rounded border p-2" disabled={isSubmitting} /></label>
      {errors.reason && <p role="alert">{errors.reason.message}</p>}{error && <p role="alert">{error}</p>}
    </form>
  </RecipeDialog>
}
