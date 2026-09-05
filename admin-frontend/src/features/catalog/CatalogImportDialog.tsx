import { zodResolver } from '@hookform/resolvers/zod'
import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { FileUp } from 'lucide-react'

import { CatalogApiError, type CatalogCsvPreview, importCatalogCsv, lifecycleReasonSchema, previewCatalogCsv } from './api'
import { CatalogDialog } from './CatalogDialog'

export function CatalogImportDialog({ accessToken, onClose, onSuccess, onSecurityError }: Readonly<{
  accessToken: string; onClose: () => void; onSuccess: (count: number) => void;
  onSecurityError: (error: unknown) => boolean
}>) {
  const [csvText, setCsvText] = useState('')
  const [preview, setPreview] = useState<CatalogCsvPreview>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const requestVersion = useRef(0)
  const command = useRef<{ signature: string; key: string } | undefined>(undefined)
  const form = useForm<{ reason: string }>({ resolver: zodResolver(lifecycleReasonSchema), defaultValues: { reason: '' } })

  async function chooseFile(file: File | undefined) {
    const version = ++requestVersion.current
    setPreview(undefined)
    setCsvText('')
    setError('')
    command.current = undefined
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv') || file.size > 1_048_576) {
      setError('请选择不超过 1 MB 的 CSV 文件。')
      return
    }
    setBusy(true)
    try {
      const text = await file.text()
      const result = await previewCatalogCsv(accessToken, text)
      if (requestVersion.current !== version) return
      setCsvText(text)
      setPreview(result)
    } catch (requestError) {
      if (requestVersion.current === version && !onSecurityError(requestError)) {
        setError('文件校验失败。请使用 UTF-8 CSV 和下载的模板，每次不超过 500 条；也可稍后重试。')
      }
    } finally {
      if (requestVersion.current === version) setBusy(false)
    }
  }

  async function confirm(values: { reason: string }) {
    if (!preview || preview.errors.length || busy) return
    const signature = JSON.stringify([csvText, values.reason])
    if (command.current?.signature !== signature) command.current = { signature, key: crypto.randomUUID() }
    setBusy(true)
    setError('')
    try {
      const result = await importCatalogCsv(accessToken, csvText, values.reason, command.current.key)
      onSuccess(result.imported_count)
    } catch (requestError) {
      if (!onSecurityError(requestError)) setError(requestError instanceof CatalogApiError && requestError.status === 409
        ? '导入请求发生冲突，请重新选择文件后检查。'
        : '暂时无法完成导入。重试相同文件和原因不会重复新增。')
    } finally { setBusy(false) }
  }

  return <CatalogDialog busy={busy} onClose={onClose} title="导入营养目录" description="先校验文件，再确认新增草稿。">
    <div className="rounded-lg border border-dashed bg-muted/30 p-5">
      <FileUp aria-hidden className="mb-3 text-blue-600" size={24} />
      <label className="block text-sm font-medium" htmlFor="catalog-csv-file">选择 CSV 文件</label>
      <input accept=".csv,text/csv" className="mt-3 block w-full text-sm file:mr-3 file:rounded file:border file:bg-card file:px-3 file:py-2" disabled={busy} id="catalog-csv-file" onChange={(event) => void chooseFile(event.target.files?.[0])} type="file" />
      <p className="mt-3 text-xs leading-5 text-muted-foreground">使用 UTF-8 编码，最多 500 条、1 MB。多个别名用 | 分隔。授权状态填写“待确认”“已授权”或“已撤销”。</p>
    </div>
    <p className="mt-4 text-sm text-muted-foreground">导入只新增草稿，不覆盖现有目录，也不会自动发布。请避免重复导入同一批数据。</p>
    {busy && <p className="mt-4 text-sm" role="status">正在处理，请稍候…</p>}
    {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
    {preview && <section aria-label="导入校验结果" className="mt-5">
      <p className="font-medium" role="status">共 {preview.total_rows} 条，{preview.valid_rows} 条校验通过{preview.errors.length ? `，${preview.errors.length} 处错误` : ''}。</p>
      {preview.errors.length > 0 ? <div className="mt-3 max-h-64 overflow-auto rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
        <p className="mb-2 font-medium">请修正全部错误后重新选择文件，本次尚未导入。</p>
        <ul className="space-y-2">{preview.errors.map((issue, index) => <li key={`${issue.row}-${index}`}>第 {issue.row} 行 · {issue.field}：{issue.message}</li>)}</ul>
      </div> : <><div className="mt-3 overflow-x-auto rounded-md border"><table className="w-full text-left text-sm"><caption className="sr-only">待导入目录预览，最多显示前五条</caption><thead className="bg-muted/50"><tr><th className="p-3">菜品名称</th><th className="p-3">能量 / 100g</th><th className="p-3">来源</th></tr></thead><tbody>{preview.rows.slice(0, 5).map((row, index) => <tr className="border-t" key={index}><td className="p-3">{row.canonical_name}</td><td className="p-3">{row.energy_kcal_per_100g} kcal</td><td className="p-3">{row.source_name}</td></tr>)}</tbody></table></div>{preview.total_rows > 5 && <p className="mt-2 text-xs text-muted-foreground">仅展示前 5 条，确认后将导入全部 {preview.total_rows} 条。</p>}</>}
    </section>}
    <form className="mt-5" onSubmit={form.handleSubmit((values) => void confirm(values))}>
      <label className="block text-sm font-medium" htmlFor="catalog-import-reason">导入原因</label>
      <textarea className="mt-2 w-full rounded-md border bg-card px-3 py-2 text-sm" disabled={busy} id="catalog-import-reason" rows={3} {...form.register('reason')} />
      {form.formState.errors.reason && <p className="text-sm text-red-700" role="alert">请填写导入原因（最多 500 字）。</p>}
      <div className="mt-6 flex justify-end gap-3"><button className="h-9 rounded-md border px-4 text-sm" disabled={busy} onClick={onClose} type="button">取消</button><button className="h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50" disabled={busy || !preview || preview.errors.length > 0} type="submit">确认导入{preview && !preview.errors.length ? ` ${preview.total_rows} 条` : ''}</button></div>
    </form>
  </CatalogDialog>
}
