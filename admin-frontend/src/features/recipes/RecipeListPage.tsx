import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { RecipeRoleDialog } from './RecipeRoleDialog'
import { RecipeDialog } from './RecipeDialog'
import { RecipeImportDialog } from './RecipeImportDialog'
import { recipeMealRoleLabels, RecipeCandidateApiError, type RecipeCandidateOperation, changeRecipeCandidates, downloadRecipeCandidates, listRecipeCandidates } from './api'

const button = 'inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border bg-card px-3 text-sm hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50'
const labels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐', pending: '待审核', enabled: '已启用', disabled: '已停用' } as const
const statusStyles = { pending: 'bg-amber-50 text-amber-700', enabled: 'bg-emerald-50 text-emerald-700', disabled: 'bg-slate-100 text-slate-700' }
const maxBulkSelection = 1000

export function RecipeListPage() {
  const queryClient = useQueryClient()
  const { accessToken, clearSession } = useAdminAuth()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [selected, setSelected] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [roleOpen, setRoleOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [operation, setOperation] = useState<RecipeCandidateOperation>()
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['recipe-candidates', page, pageSize], queryFn: () => listRecipeCandidates(accessToken!, page, pageSize), enabled: Boolean(accessToken), retry: false })

  useEffect(() => {
    if (query.error instanceof RecipeCandidateApiError && query.error.status === 401) clearSession()
  }, [clearSession, query.error])

  const items = query.data?.items ?? []
  const total = query.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / pageSize))
  useEffect(() => {
    if (query.data && page > pages) setPage(pages)
  }, [page, pages, query.data])
  const selectedItems = items.filter(item => selected.includes(item.id))
  const allSelected = items.length > 0 && selectedItems.length === items.length

  function toggleCurrentPage() {
    const idsOnPage = new Set(items.map(item => item.id))
    setSelected(current => allSelected
      ? current.filter(id => !idsOnPage.has(id))
      : [...new Set([...current, ...idsOnPage])])
  }

  async function selectAll() {
    if (!accessToken) return
    setBusy(true); setError(''); setNotice('')
    try {
      const first = await listRecipeCandidates(accessToken, 1, 100)
      if (first.total > maxBulkSelection) {
        setError(`一次最多全选 ${maxBulkSelection} 条，请缩小范围后操作。`)
        return
      }
      const responses = await Promise.all(
        Array.from({ length: Math.ceil(first.total / 100) - 1 }, (_, index) => listRecipeCandidates(accessToken, index + 2, 100)),
      )
      setSelected([...new Set([first, ...responses].flatMap(response => response.items.map(item => item.id)))])
    } catch (requestError) {
      if (!securityError(requestError)) setError('暂时无法读取全部菜谱候选，请稍后重试。')
    } finally { setBusy(false) }
  }

  function securityError(requestError: unknown) {
    if (!(requestError instanceof RecipeCandidateApiError)) return false
    if (requestError.status === 401) { clearSession(); return true }
    if (requestError.status === 403) { setError('当前账号没有菜谱管理权限。'); return true }
    return false
  }

  async function download(template = false) {
    if (!accessToken) return
    setBusy(true); setError('')
    try { await downloadRecipeCandidates(accessToken, template); setNotice(template ? '菜谱导入模板已下载。' : '菜谱候选已导出。') }
    catch (requestError) { if (!securityError(requestError)) setError('暂时无法下载文件，请稍后重试。') }
    finally { setBusy(false) }
  }

  async function confirmOperation() {
    if (!accessToken || !operation || !selected.length || !reason.trim()) return
    setBusy(true); setError('')
    try {
      await changeRecipeCandidates(accessToken, operation, selected, reason.trim(), crypto.randomUUID())
      setSelected([]); setReason(''); setOperation(undefined)
      setNotice(`已${operation === 'enable' ? '启用' : operation === 'disable' ? '停用' : '删除'} ${selected.length} 条菜谱候选。`)
      await queryClient.invalidateQueries({ queryKey: ['recipe-candidates'] })
    } catch (requestError) {
      if (!securityError(requestError)) setError(requestError instanceof RecipeCandidateApiError && requestError.status === 409 ? '数据已变化，请刷新列表后重新选择。' : '操作结果未确认，请刷新列表核对后再重试。')
    } finally { setBusy(false) }
  }

  if (!accessToken) return <p className="p-6">登录已失效，请重新登录。</p>
  if (query.error instanceof RecipeCandidateApiError && query.error.status === 403) return <section className="p-6"><h2 className="text-xl font-semibold">无后台访问权限</h2><p className="mt-2">请使用管理员账号登录。</p></section>

  return <section aria-label="菜谱管理" className="space-y-5 p-4 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:gap-5 lg:space-y-0 lg:overflow-hidden lg:p-6">
    {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{notice}</p>}
    {error && <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">{error}</p>}
    <section className="min-w-0 rounded-lg border bg-card lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-hidden" aria-labelledby="recipe-list-title">
      <div className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div><h2 className="text-base font-semibold" id="recipe-list-title">菜谱管理</h2><p className="mt-1 text-xs text-muted-foreground">候选菜必须关联当前合格的营养目录；已启用的单独候选可直接参选；午餐、晚餐也可由主食、蛋白质菜与蔬菜搭配。</p></div>
        <div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={() => setImportOpen(true)} type="button">导入</button><button className={button} disabled={busy} onClick={() => void download()} type="button">导出</button><button className={button} disabled={busy} onClick={() => void download(true)} type="button">下载模板</button><button aria-label="刷新菜谱候选" className={button} disabled={busy || query.isFetching} onClick={() => void query.refetch()} type="button">刷新</button></div>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t px-5 py-3 text-sm" aria-label="批量操作">
        <span aria-live="polite">已选 {selected.length} 条</span>
        <button className={button} disabled={busy || query.isFetching || !total || total > maxBulkSelection} onClick={() => void selectAll()} type="button">全选全部（{total}）</button>
        <button className={button} disabled={busy || query.isFetching || !selected.length} onClick={() => setRoleOpen(true)} type="button">设置餐内角色</button>
        <button className={button} disabled={busy || query.isFetching || !selected.length} onClick={() => setOperation('enable')} type="button">批量启用</button>
        <button className={button} disabled={busy || query.isFetching || !selected.length} onClick={() => setOperation('disable')} type="button">批量停用</button>
        <button className="inline-flex h-9 items-center justify-center rounded-md border border-red-200 px-3 text-sm text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50" disabled={busy || query.isFetching || !selected.length} onClick={() => setOperation('delete')} type="button">批量删除</button>
        <button className="text-blue-600 hover:underline disabled:opacity-50" disabled={busy || !selected.length} onClick={() => setSelected([])} type="button">清空选择</button>
      </div>
      <div className="min-h-0 overflow-auto lg:flex-1" role="region" aria-label="菜谱候选表格" tabIndex={0}>
        <table aria-busy={query.isFetching} className="w-full whitespace-nowrap text-left text-sm"><caption className="sr-only">菜谱候选列表</caption>
          <thead className="sticky top-0 z-10 border-y bg-slate-50 text-xs text-muted-foreground shadow-[0_1px_0_var(--border)]"><tr><th className="px-4 py-3" scope="col"><input aria-label="全选当前页" checked={allSelected} className="size-4 cursor-pointer accent-blue-600" disabled={busy || query.isFetching || !items.length} onChange={toggleCurrentPage} ref={element => { if (element) element.indeterminate = selectedItems.length > 0 && !allSelected }} type="checkbox" /></th>{['目录菜品', '餐次', '餐内角色', '单份克数', '份量说明', '做法', '口味', '状态'].map(label => <th className="px-4 py-3 font-medium" key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody className="divide-y">
            {query.isPending ? <tr><td className="p-12 text-center text-muted-foreground" colSpan={9}>正在加载菜谱候选…</td></tr> : query.isError ? <tr><td className="p-12 text-center" colSpan={9}><p role="alert">暂时无法加载菜谱候选。</p><button className={`${button} mt-3`} onClick={() => void query.refetch()} type="button">重试</button></td></tr> : !items.length ? <tr><td className="p-14 text-center" colSpan={9}><p className="font-medium">暂无菜谱候选</p><p className="mt-2 text-xs text-muted-foreground">下载模板后批量导入；导入行必须关联当前合格的营养目录。</p></td></tr> : items.map(item => <tr className="hover:bg-muted/20" key={item.id}><td className="px-4 py-3"><input aria-label={`选择 ${item.catalog_food_name}`} checked={selected.includes(item.id)} className="size-4 cursor-pointer accent-blue-600" disabled={busy || query.isFetching} onChange={event => setSelected(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} type="checkbox" /></td><td className="px-4 py-3 font-medium">{item.catalog_food_name}</td><td className="px-4 py-3">{labels[item.meal_slot]}</td><td className="px-4 py-3">{recipeMealRoleLabels[item.meal_role]}</td><td className="admin-numeric px-4 py-3">{item.portion_grams}g</td><td className="px-4 py-3">{item.portion_description}</td><td className="px-4 py-3">{item.method_tags.join('、')}</td><td className="px-4 py-3">{item.flavour_tags.join('、')}</td><td className="px-4 py-3"><span className={`inline-flex rounded px-2 py-1 text-xs ${statusStyles[item.status]}`}>{labels[item.status]}</span></td></tr>)}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-4 border-t px-5 py-4 text-xs text-muted-foreground">
        <span aria-live="polite">{total && !query.isError ? `第 ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} 条 / ` : ''}共 {query.isError ? '—' : total} 条</span>
        <label className="flex items-center gap-2">每页<select aria-label="每页条数" className="h-8 rounded border bg-card px-2" disabled={busy} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1) }} value={pageSize}>{[10, 20, 50, 100].map(size => <option key={size} value={size}>{size} 条</option>)}</select></label>
        <nav aria-label="菜谱分页" className="flex items-center gap-2"><button aria-label="上一页" className="rounded border p-1.5 disabled:opacity-30" disabled={page <= 1 || query.isFetching || busy} onClick={() => setPage(page - 1)} type="button"><ChevronLeft size={15} /></button><span className="admin-numeric rounded border border-blue-300 px-2.5 py-1 text-blue-600">{page}</span><span>/ {pages}</span><button aria-label="下一页" className="rounded border p-1.5 disabled:opacity-30" disabled={page >= pages || query.isFetching || query.isError || busy} onClick={() => setPage(page + 1)} type="button"><ChevronRight size={15} /></button></nav>
      </div>
    </section>
    {roleOpen && <RecipeRoleDialog accessToken={accessToken} ids={selected} onClose={() => setRoleOpen(false)} onSecurityError={securityError} onSuccess={count => { setRoleOpen(false); setSelected([]); setNotice(`已更新 ${count} 条菜谱的餐内角色。`); void queryClient.invalidateQueries({ queryKey: ['recipe-candidates'] }) }} />}
    {importOpen && <RecipeImportDialog accessToken={accessToken} onClose={() => setImportOpen(false)} onSecurityError={securityError} onSuccess={(count) => { setImportOpen(false); setNotice(`成功导入 ${count} 条菜谱候选。`); void queryClient.invalidateQueries({ queryKey: ['recipe-candidates'] }) }} />}
    {operation && <RecipeDialog busy={busy} description={`将对已选 ${selected.length} 条菜谱候选执行操作；该原因将写入审计记录。`} onClose={() => setOperation(undefined)} title={operation === 'enable' ? '批量启用菜谱' : operation === 'disable' ? '批量停用菜谱' : '批量删除菜谱'} footer={<><button className={button} disabled={busy} onClick={() => setOperation(undefined)} type="button">取消</button><button className={operation === 'delete' ? 'h-9 rounded-md bg-red-600 px-4 text-sm text-white disabled:opacity-50' : 'h-9 rounded-md bg-blue-600 px-4 text-sm text-white disabled:opacity-50'} disabled={busy || !reason.trim()} onClick={() => void confirmOperation()} type="button">{busy ? '正在处理…' : '确认操作'}</button></>}><label className="block text-sm" htmlFor="recipe-bulk-reason">操作原因</label><textarea className="mt-2 w-full rounded-md border bg-card px-3 py-2 text-sm" disabled={busy} id="recipe-bulk-reason" maxLength={500} onChange={event => setReason(event.target.value)} placeholder="填写操作原因（必填，写入审计记录）" rows={3} value={reason} />{operation === 'delete' && <p className="mt-3 text-sm text-red-700">删除后不会出现在新餐单中，也不能从后台恢复。</p>}</RecipeDialog>}
  </section>
}
