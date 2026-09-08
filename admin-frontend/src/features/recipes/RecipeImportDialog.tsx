import { useRef, useState } from 'react'

import { RecipeDialog } from './RecipeDialog'
import { RecipeCandidateApiError, type RecipeCandidateCsvPreview, importRecipeCandidates, previewRecipeCandidates } from './api'

export function RecipeImportDialog({ accessToken, onClose, onSuccess, onSecurityError }: Readonly<{
  accessToken: string
  onClose: () => void
  onSuccess: (count: number) => void
  onSecurityError: (error: unknown) => boolean
}>) {
  const [csvText, setCsvText] = useState('')
  const [preview, setPreview] = useState<RecipeCandidateCsvPreview>()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const commandKey = useRef('')

  async function chooseFile(file: File | undefined) {
    setCsvText(''); setPreview(undefined); setError(''); commandKey.current = ''
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv') || file.size > 1_048_576) { setError('请选择不超过 1 MB 的 CSV 文件。'); return }
    setBusy(true)
    try {
      const text = await file.text()
      setCsvText(text)
      setPreview(await previewRecipeCandidates(accessToken, text))
    } catch (requestError) {
      if (!onSecurityError(requestError)) setError(requestError instanceof RecipeCandidateApiError && requestError.status === 422 ? '文件格式不符合模板，请下载模板后重新填写。' : '文件校验失败，请稍后重试。')
    } finally { setBusy(false) }
  }

  async function confirm() {
    if (!csvText || !preview || preview.errors.length || !reason.trim() || busy) return
    if (!commandKey.current) commandKey.current = crypto.randomUUID()
    setBusy(true); setError('')
    try { const result = await importRecipeCandidates(accessToken, csvText, reason.trim(), commandKey.current); onSuccess(result.imported_count) }
    catch (requestError) {
      if (!onSecurityError(requestError)) setError(
        requestError instanceof RecipeCandidateApiError && requestError.status === 409
          ? '导入请求冲突，请重新选择文件并核对。'
          : requestError instanceof RecipeCandidateApiError && requestError.detail
            ? requestError.detail
            : '导入结果未确认；使用相同文件和原因重试不会重复新增。',
      )
    } finally { setBusy(false) }
  }

  return <RecipeDialog busy={busy} description="先校验 CSV；所有行都通过后，填写原因确认导入。不会自动创建或猜测营养目录关联。" onClose={onClose} title="导入菜谱候选" footer={<><button className="h-9 rounded-md border px-4 text-sm disabled:opacity-50" disabled={busy} onClick={onClose} type="button">取消</button><button className="h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50" disabled={busy || !preview || Boolean(preview.errors.length) || !reason.trim()} onClick={() => void confirm()} type="button">确认导入{preview && !preview.errors.length ? ` ${preview.total_rows} 条` : ''}</button></>}>
    <div className="rounded-lg border border-dashed bg-muted/30 p-5"><label className="block text-sm font-medium" htmlFor="recipe-csv-file">选择 CSV 文件</label><input accept=".csv,text/csv" className="mt-3 block w-full text-sm file:mr-3 file:rounded file:border file:bg-card file:px-3 file:py-2" disabled={busy} id="recipe-csv-file" onChange={event => void chooseFile(event.target.files?.[0])} type="file" /><p className="mt-3 text-xs leading-5 text-muted-foreground">使用 UTF-8 CSV，最多 500 条、1 MB。做法和口味标签用 | 分隔；餐次支持早餐、午餐、晚餐、加餐。</p></div>
    {busy && <p className="mt-4 text-sm" role="status">正在处理，请稍候…</p>}
    {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
    {preview && <section aria-label="导入校验结果" className="mt-5"><p className="font-medium" role="status">共 {preview.total_rows} 条，{preview.valid_rows} 条校验通过{preview.errors.length ? `，${preview.errors.length} 处错误` : ''}。</p>{preview.errors.length ? <div className="mt-3 max-h-52 overflow-auto rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert"><p className="mb-2 font-medium">请修正全部错误后重新选择文件，本次尚未导入。</p><ul className="space-y-2">{preview.errors.map((issue, index) => <li key={`${issue.row}-${index}`}>第 {issue.row} 行 · {issue.field}：{issue.message}</li>)}</ul></div> : <div className="mt-3 overflow-x-auto rounded border"><table className="w-full text-left text-sm"><thead className="bg-muted/50"><tr><th className="p-3">目录菜品</th><th className="p-3">餐次</th><th className="p-3">单份克数</th><th className="p-3">状态</th></tr></thead><tbody>{preview.rows.slice(0, 5).map((row, index) => <tr className="border-t" key={index}><td className="p-3">{row.catalog_food_name}</td><td className="p-3">{({ breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' } as const)[row.meal_slot]}</td><td className="p-3">{row.portion_grams}g</td><td className="p-3">{row.status === 'pending' ? '待审核' : '已停用'}</td></tr>)}</tbody></table></div>}</section>}
    <label className="mt-5 block text-sm font-medium" htmlFor="recipe-import-reason">导入原因</label><textarea className="mt-2 w-full rounded-md border bg-card px-3 py-2 text-sm" disabled={busy} id="recipe-import-reason" maxLength={500} onChange={event => setReason(event.target.value)} placeholder="填写导入原因（必填，写入审计记录）" rows={3} value={reason} />
  </RecipeDialog>
}
