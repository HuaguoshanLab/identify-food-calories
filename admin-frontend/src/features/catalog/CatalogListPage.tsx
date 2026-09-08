import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Download, Plus, RefreshCw, Search, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'

import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { CatalogApiError, type CatalogDraft, type CatalogFilters, catalogFilterSchema, downloadCatalogCsv, emptyCatalogFilters, listCatalogDrafts, readCatalogDraft } from './api'
import { CatalogDraftPage } from './CatalogDraftPage'
import { CatalogImportDialog } from './CatalogImportDialog'
import { CatalogRowLifecycle } from './CatalogRowLifecycle'
import { CatalogDialog } from './CatalogDialog'
import { CatalogBulkLifecycle } from './CatalogBulkLifecycle'

const button = 'inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border bg-card px-3 text-sm hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50'
const input = 'h-9 min-w-0 flex-1 rounded-md border bg-card px-3 text-sm'
const statusLabels = { pending: '待确认', authorized: '已授权', revoked: '已撤销' }
const statusStyles = { pending: 'bg-amber-50 text-amber-700', authorized: 'bg-emerald-50 text-emerald-700', revoked: 'bg-red-50 text-red-700' }
const maxBulkSelection = 1000

export function CatalogListPage({ accessToken, onSessionExpired }: Readonly<{ accessToken?: string; onSessionExpired: () => void }>) {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState(emptyCatalogFilters)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editor, setEditor] = useState<{ draft?: CatalogDraft }>()
  const [lifecycle, setLifecycle] = useState<{ draftId: string; action: 'review' | 'publish' }>()
  const [mutating, setMutating] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [forbidden, setForbidden] = useState(false)
  const [expired, setExpired] = useState(false)
  const [selectedDrafts, setSelectedDrafts] = useState<CatalogDraft[]>([])
  const [bulk, setBulk] = useState<{ drafts: CatalogDraft[]; action: 'review' | 'publish' }>()
  const form = useForm<CatalogFilters>({ resolver: zodResolver(catalogFilterSchema), defaultValues: emptyCatalogFilters })
  const list = useQuery({ queryKey: ['catalog-list', filters, page, pageSize],
    queryFn: () => listCatalogDrafts(accessToken!, filters, page, pageSize), enabled: Boolean(accessToken) && !forbidden && !expired, retry: false })

  useEffect(() => {
    if (list.error instanceof CatalogApiError && list.error.status === 401) onSessionExpired()
  }, [list.error, onSessionExpired])

  // A changed filter describes a different set of records, so prior selections are unsafe.
  useEffect(() => { setSelectedDrafts([]) }, [filters])

  function securityError(requestError: unknown) {
    if (!(requestError instanceof CatalogApiError)) return false
    if (requestError.status === 401) { setExpired(true); onSessionExpired(); return true }
    if (requestError.status === 403) { setForbidden(true); return true }
    return false
  }

  async function selectAllDrafts() {
    if (!accessToken) return
    setBusy(true); setError(''); setNotice('')
    try {
      const first = await listCatalogDrafts(accessToken, filters, 1, 100)
      if (first.total > maxBulkSelection) {
        setError(`一次最多全选 ${maxBulkSelection} 条，请缩小筛选范围后操作。`)
        return
      }
      const remaining = await Promise.all(
        Array.from({ length: Math.ceil(first.total / 100) - 1 }, (_, index) => listCatalogDrafts(accessToken, filters, index + 2, 100)),
      )
      setSelectedDrafts([...new Map([first, ...remaining].flatMap(response => response.items).map(draft => [draft.id, draft])).values()])
    } catch (requestError) {
      if (!securityError(requestError)) setError('暂时无法读取全部营养目录，请稍后重试。')
    } finally { setBusy(false) }
  }

  async function edit(draftId: string) {
    setBusy(true)
    setError('')
    try { setEditor({ draft: await readCatalogDraft(accessToken!, draftId) }); setLifecycle(undefined); setNotice('') }
    catch (requestError) { if (!securityError(requestError)) setError('暂时无法读取目录，请刷新后重试。') }
    finally { setBusy(false) }
  }

  async function download(template = false) {
    setBusy(true)
    setError('')
    try { await downloadCatalogCsv(accessToken!, filters, template); setNotice(template ? '导入模板已下载。' : '已按当前查询条件导出 CSV。') }
    catch (requestError) {
      if (!securityError(requestError)) setError(requestError instanceof CatalogApiError && requestError.status === 422
        ? '匹配结果超过 10000 条，请缩小筛选范围后导出。' : '暂时无法下载文件，请稍后重试。')
    } finally { setBusy(false) }
  }

  function saved(message: string) {
    setEditor(undefined)
    setImportOpen(false)
    setLifecycle(undefined)
    setNotice(message)
    void queryClient.invalidateQueries({ queryKey: ['catalog-list'] })
  }

  if (forbidden || (list.error instanceof CatalogApiError && list.error.status === 403)) return <section className="p-6"><h2 className="text-xl font-semibold">无后台访问权限</h2><p className="mt-2">你的当前账号没有管理权限。请使用管理员账号登录。</p></section>
  if (!accessToken || expired || (list.error instanceof CatalogApiError && list.error.status === 401)) return <p className="p-6">登录已失效，请重新登录。</p>
  const total = list.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const locked = busy || mutating
  const visibleDrafts = list.isError ? [] : list.data?.items ?? []
  const selectedIds = new Set(selectedDrafts.map(draft => draft.id))
  const selectedOnPage = visibleDrafts.filter(draft => selectedIds.has(draft.id))
  const allSelected = visibleDrafts.length > 0 && selectedOnPage.length === visibleDrafts.length
  function toggleCurrentPage() {
    const idsOnPage = new Set(visibleDrafts.map(draft => draft.id))
    setSelectedDrafts(current => allSelected
      ? current.filter(draft => !idsOnPage.has(draft.id))
      : [...new Map([...current, ...visibleDrafts].map(draft => [draft.id, draft])).values()])
  }
  function openBulk(action: 'review' | 'publish') {
    if (!selectedDrafts.length || list.isFetching || locked) return
    setNotice('')
    setBulk({ drafts: selectedDrafts, action })
  }
  const editorFormId = `catalog-editor-${editor?.draft?.id ?? 'new'}`

  function openLifecycle(draftId: string, action: 'review' | 'publish') {
    setEditor(undefined)
    setNotice('')
    setError('')
    setLifecycle({ draftId, action })
  }

  const editorForm = editor && <CatalogDraftPage accessToken={accessToken} embedded directSaveFormId={editorFormId} initialDraft={editor.draft} key={editor.draft?.id ?? 'new'} onBusyChange={setMutating} onForbidden={() => setForbidden(true)} onSaved={(draft) => saved(`“${draft.canonical_name}”已保存为草稿，请在该行继续审核、发布。`)} onSessionExpired={onSessionExpired} />

  return <section aria-label="营养目录管理" className="space-y-5 p-4 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:gap-5 lg:space-y-0 lg:overflow-hidden lg:p-6">
    <form aria-label="目录筛选" className="flex flex-wrap items-end gap-x-6 gap-y-4 rounded-lg border bg-card px-5 py-5" onSubmit={form.handleSubmit((values) => { if (mutating) return; setFilters(values); setPage(1); setNotice(''); setEditor(undefined); setLifecycle(undefined) })}>
      <fieldset className="contents" disabled={mutating}>
      <label className="flex min-w-56 flex-1 items-center gap-3 text-sm" htmlFor="catalog-search"><span className="shrink-0">菜品名称</span><input className={input} id="catalog-search" placeholder="搜索名称或别名" {...form.register('search')} /></label>
      <label className="flex min-w-48 flex-1 items-center gap-3 text-sm" htmlFor="catalog-source-filter"><span className="shrink-0">来源</span><input className={input} id="catalog-source-filter" placeholder="请输入来源名称" {...form.register('source')} /></label>
      <label className="flex min-w-44 flex-1 items-center gap-3 text-sm" htmlFor="catalog-status-filter"><span className="shrink-0">授权状态</span><select className={input} id="catalog-status-filter" {...form.register('authorization_status')}><option value="">全部</option><option value="pending">待确认</option><option value="authorized">已授权</option><option value="revoked">已撤销</option></select></label>
      <div className="ml-auto flex gap-2"><button className={button} onClick={() => { form.reset(emptyCatalogFilters); setFilters(emptyCatalogFilters); setPage(1); setNotice(''); setEditor(undefined); setLifecycle(undefined) }} type="button">重置</button><button className="inline-flex h-9 items-center gap-2 rounded-md bg-blue-600 px-4 text-sm text-white hover:bg-blue-700" type="submit"><Search aria-hidden size={15} />查询</button></div>
      {Object.keys(form.formState.errors).length > 0 && <p className="w-full text-sm text-red-700" role="alert">筛选条件过长，请缩短后查询。</p>}
      </fieldset>
    </form>
    {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{notice}</p>}
    {error && <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">{error}</p>}
    <section className="min-w-0 rounded-lg border bg-card lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-hidden" aria-labelledby="catalog-list-title">
      <div className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div><h2 className="text-base font-semibold" id="catalog-list-title">营养目录</h2><p className="mt-1 text-xs text-muted-foreground">统一管理菜品与营养信息 · 营养数值均以每 100g 计</p></div>
        <div className="flex flex-wrap gap-2"><button className="inline-flex h-9 items-center gap-2 rounded-md bg-blue-600 px-3 text-sm text-white hover:bg-blue-700 disabled:opacity-50" disabled={locked} onClick={() => { setEditor({}); setLifecycle(undefined) }} type="button"><Plus aria-hidden size={16} />新增</button><button className={button} disabled={locked} onClick={() => setImportOpen(true)} type="button"><Upload aria-hidden size={15} />导入</button><button className={button} disabled={locked} onClick={() => void download()} type="button"><Download aria-hidden size={15} />导出</button><button className={button} disabled={locked} onClick={() => void download(true)} type="button">下载模板</button><button aria-label="刷新目录" className={button} disabled={list.isFetching || locked} onClick={() => void list.refetch()} type="button"><RefreshCw aria-hidden className={list.isFetching ? 'animate-spin motion-reduce:animate-none' : ''} size={16} /></button></div>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t px-5 py-3 text-sm" aria-label="批量操作">
        <span aria-live="polite">已选 {selectedDrafts.length} 条</span>
        <button className={button} disabled={locked || list.isFetching || !selectedDrafts.length} onClick={() => openBulk('review')} type="button">批量审核</button>
        <button className={button} disabled={locked || list.isFetching || !selectedDrafts.length} onClick={() => openBulk('publish')} type="button">批量发布</button>
        <button className={button} disabled={locked || list.isFetching || !total || total > maxBulkSelection} onClick={() => void selectAllDrafts()} type="button">全选全部（{total}）</button>
        <button className="text-blue-600 hover:underline disabled:opacity-50" disabled={locked || !selectedDrafts.length} onClick={() => setSelectedDrafts([])} type="button">清空选择</button>
        <span className="text-xs text-muted-foreground">审核和发布会逐项核对版本并记录审计。</span>
      </div>
      <div className="min-h-0 overflow-auto lg:flex-1" role="region" aria-label="营养目录表格" tabIndex={0}>
        <table aria-busy={list.isFetching} className="w-full whitespace-nowrap text-left text-sm"><caption className="sr-only">营养目录列表，营养值按每 100g 计</caption>
          <thead className="sticky top-0 z-10 border-y bg-slate-50 text-xs text-muted-foreground shadow-[0_1px_0_var(--border)]"><tr><th className="px-4 py-3" scope="col"><input type="checkbox" aria-label="全选当前页" className="size-4 cursor-pointer accent-blue-600" disabled={locked || list.isFetching || !visibleDrafts.length} checked={allSelected} ref={element => { if (element) element.indeterminate = selectedOnPage.length > 0 && !allSelected }} onChange={toggleCurrentPage} /></th>{['菜品名称', '别名', '能量 (kcal)', '蛋白质 (g)', '脂肪 (g)', '碳水 (g)', '来源', '授权状态', '版本', '更新时间', '操作'].map((label) => <th className="px-4 py-3 font-medium" scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody className="divide-y">
            {list.isPending ? <tr><td className="p-12 text-center text-muted-foreground" colSpan={12}>正在加载目录…</td></tr> : list.isError ? <tr><td className="p-12 text-center" colSpan={12}><p role="alert">暂时无法加载目录，请稍后重试。</p><button className={`${button} mt-3`} onClick={() => void list.refetch()} type="button">重试</button></td></tr> : !list.data?.items.length ? <tr><td className="p-14 text-center" colSpan={12}><p className="font-medium">{Object.values(filters).some(Boolean) ? '没有符合条件的目录' : '暂无营养目录'}</p><p className="mt-2 text-xs text-muted-foreground">{Object.values(filters).some(Boolean) ? '调整筛选条件，或点击重置查看全部。' : '点击“新增”添加菜品，或下载模板后批量导入。'}</p></td></tr> : list.data.items.map((draft) => <tr className="hover:bg-muted/20" key={draft.id}>
              <td className="px-4 py-4"><input type="checkbox" aria-label={`选择 ${draft.canonical_name}`} className="size-4 cursor-pointer accent-blue-600" disabled={locked || list.isFetching} checked={selectedIds.has(draft.id)} onChange={event => setSelectedDrafts(current => event.target.checked ? [...new Map([...current, draft].map(item => [item.id, item])).values()] : current.filter(item => item.id !== draft.id))} /></td>
              <td className="max-w-64 truncate px-4 py-4 font-medium" title={draft.canonical_name}><button className="text-blue-600 hover:underline" disabled={locked} onClick={() => void edit(draft.id)} type="button">{draft.canonical_name}</button></td>
              <td className="max-w-40 truncate px-4 py-4 text-muted-foreground" title={draft.aliases.join('、')}>{draft.aliases.join('、')}</td>
              {[draft.energy_kcal_per_100g, draft.protein_g_per_100g, draft.fat_g_per_100g, draft.carbohydrate_g_per_100g].map((value, index) => <td className="admin-numeric px-4 py-4" key={index}>{Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 })}</td>)}
              <td className="max-w-40 truncate px-4 py-4" title={draft.source_name}>{draft.source_name}</td><td className="px-4 py-4"><span className={`inline-flex rounded px-2 py-1 text-xs ${statusStyles[draft.authorization_status]}`}>{statusLabels[draft.authorization_status]}</span></td><td className="admin-numeric px-4 py-4 text-muted-foreground">v{draft.revision}</td><td className="admin-numeric px-4 py-4 text-xs text-muted-foreground">{new Date(draft.updated_at).toLocaleString('zh-CN', { hour12: false })}</td>
              <td className="sticky right-0 border-l bg-card px-4 py-4"><div className="flex gap-3 text-xs text-blue-600">
                <button className="hover:underline disabled:opacity-50" disabled={locked} onClick={() => void edit(draft.id)} type="button">编辑</button>
                <button className="hover:underline disabled:opacity-50" disabled={locked || Boolean(editor)} onClick={() => openLifecycle(draft.id, 'review')} type="button">审核</button>
                <button className="hover:underline disabled:opacity-50" disabled={locked || Boolean(editor)} onClick={() => openLifecycle(draft.id, 'publish')} type="button">发布</button>
                <Link className="text-muted-foreground hover:underline" to={`/admin/catalog/${draft.id}/lifecycle`}>详情</Link>
              </div></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-4 border-t px-5 py-4 text-xs text-muted-foreground">
        <span>{total && !list.isError ? `第 ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} 条 / ` : ''}共 {list.isError ? '—' : total} 条</span>
        <label className="flex items-center gap-2">每页<select aria-label="每页条数" className="h-8 rounded border bg-card px-2" disabled={mutating} value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); setEditor(undefined); setLifecycle(undefined) }}>{[10, 20, 50, 100].map((size) => <option value={size} key={size}>{size} 条</option>)}</select></label>
        <nav aria-label="目录分页" className="flex items-center gap-2"><button aria-label="上一页" className="rounded border p-1.5 disabled:opacity-30" disabled={page <= 1 || list.isFetching || mutating} onClick={() => { setPage(page - 1); setEditor(undefined); setLifecycle(undefined) }} type="button"><ChevronLeft size={15} /></button><span className="admin-numeric rounded border border-blue-300 px-2.5 py-1 text-blue-600">{page}</span><span>/ {pages}</span><button aria-label="下一页" className="rounded border p-1.5 disabled:opacity-30" disabled={page >= pages || list.isFetching || list.isError || mutating} onClick={() => { setPage(page + 1); setEditor(undefined); setLifecycle(undefined) }} type="button"><ChevronRight size={15} /></button></nav>
      </div>
    </section>
    {editor && <CatalogDialog title={editor.draft ? '编辑营养目录' : '新增营养目录'} description="填写菜品信息，保存为草稿后再审核、发布。" busy={mutating} onClose={() => setEditor(undefined)} footer={<><button className={button} disabled={mutating} onClick={() => setEditor(undefined)} type="button">取消</button><button className="h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50" disabled={mutating} form={editorFormId} type="submit">{mutating ? '正在保存…' : '保存草稿'}</button></>}>{editorForm}</CatalogDialog>}
    {lifecycle && <CatalogDialog title={lifecycle.action === 'review' ? '审核目录草稿' : '发布营养目录版本'} description="核对当前版本，填写原因后确认。" compact busy={mutating} onClose={() => setLifecycle(undefined)}><CatalogRowLifecycle accessToken={accessToken} action={lifecycle.action} draftId={lifecycle.draftId} key={`${lifecycle.draftId}-${lifecycle.action}`} onBusyChange={setMutating} onClose={() => setLifecycle(undefined)} onSecurityError={securityError} onSuccess={saved} /></CatalogDialog>}
    {importOpen && <CatalogImportDialog accessToken={accessToken} onClose={() => setImportOpen(false)} onSecurityError={securityError} onSuccess={(count) => saved(`成功导入 ${count} 条草稿，可在列表中继续编辑、审核与发布。`)} />}
    {bulk && <CatalogBulkLifecycle accessToken={accessToken} drafts={bulk.drafts} action={bulk.action} onClose={() => setBulk(undefined)} onSecurityError={securityError} onChanged={() => { void queryClient.invalidateQueries({ queryKey: ['catalog-list'] }) }} />}
  </section>
}

export function AdminCatalogListPage() {
  const { accessToken, clearSession } = useAdminAuth()
  return <CatalogListPage accessToken={accessToken} onSessionExpired={clearSession} />
}
