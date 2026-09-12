import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { activateVectorBuild, createVectorBuild, listVectorBuilds, retryVectorBuild, type VectorBuild, VectorRetrievalApiError, vectorBuildIdentity } from './api'

const button = 'inline-flex h-9 items-center justify-center rounded-md border bg-card px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50'
const primary = 'inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50'
const labels = { pending: '等待处理', processing: '处理中', partial_failure: '部分失败', ready: '已完成' } as const
type Operation = { kind: 'create' } | { kind: 'retry' | 'activate', build: VectorBuild }

function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) }

export function hasRunningVectorBuild(builds: readonly VectorBuild[]) {
  return builds.some(build => build.status === 'pending' || build.status === 'processing' || build.pending_count > 0)
}

export function VectorRetrievalPage() {
  const { accessToken, clearSession } = useAdminAuth()
  const client = useQueryClient()
  const [operation, setOperation] = useState<Operation>()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['vector-space-builds'], queryFn: () => listVectorBuilds(accessToken!), enabled: Boolean(accessToken), retry: false, refetchInterval: current => hasRunningVectorBuild(current.state.data?.items ?? []) ? 5_000 : false })

  function handleSecurityError(cause: unknown) {
    if (!(cause instanceof VectorRetrievalApiError)) return false
    if (cause.status === 401) { clearSession(); return true }
    if (cause.status === 403) { setError('当前账号没有向量检索管理权限。'); return true }
    return false
  }
  async function submit() {
    if (!accessToken || !operation || !reason.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (operation.kind === 'create') {
        await createVectorBuild(accessToken, { reason: reason.trim() }, crypto.randomUUID())
        setNotice('已冻结名称快照并创建构建任务；它不会自动切换用户侧检索。')
      } else if (operation.kind === 'retry') {
        const result = await retryVectorBuild(accessToken, operation.build, { reason: reason.trim() }, crypto.randomUUID())
        setNotice(result.reset_count ? `已重新排队 ${result.reset_count} 个失败任务。` : '没有可重试的失败任务。')
      } else {
        await activateVectorBuild(accessToken, operation.build, { reason: reason.trim() }, crypto.randomUUID())
        setNotice('已激活经验证的向量空间。')
      }
      setOperation(undefined); setReason('')
      await client.invalidateQueries({ queryKey: ['vector-space-builds'] })
    } catch (cause) {
      if (!handleSecurityError(cause)) setError(cause instanceof VectorRetrievalApiError && cause.status === 409 ? '服务端安全校验未通过或数据已变化，请刷新后核对。' : '操作结果未确认，请刷新记录后再试。')
    } finally { setBusy(false) }
  }
  if (!accessToken) return <main className="p-6">登录已失效，请重新登录。</main>
  if (query.error instanceof VectorRetrievalApiError && query.error.status === 403) return <main className="p-6"><h1 className="text-xl font-semibold">无后台访问权限</h1><p className="mt-2">当前账号不能查看向量检索管理信息。</p></main>
  return <main aria-label="向量检索管理" className="space-y-5 p-4 lg:p-6">
    {notice ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm" role="status">{notice}</p> : null}
    {error ? <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">{error}</p> : null}
    <section className="rounded-lg border bg-card p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-xl font-semibold">向量检索管理</h1><p className="mt-2 max-w-3xl text-sm text-muted-foreground">构建只冻结当前合格目录的名称快照并排队。激活必须由后端重新验证完成证据及冻结评测发布，页面不会自行放行。</p></div><button className={primary} disabled={busy || query.isFetching} onClick={() => { setReason(''); setOperation({ kind: 'create' }) }} type="button">创建 DashScope 构建</button></div><p className="mt-4 rounded border bg-muted/30 p-3 text-xs text-muted-foreground">本次构建身份：{vectorBuildIdentity.embedding_model} · {vectorBuildIdentity.embedding_dimension} 维 · {vectorBuildIdentity.adapter_version} · {vectorBuildIdentity.retrieval_version}</p></section>
    <section className="min-w-0 rounded-lg border bg-card"><div className="flex items-center justify-between gap-3 p-5"><div><h2 className="font-semibold">构建记录</h2><p className="mt-1 text-xs text-muted-foreground">仅在存在等待或处理中的构建时每 5 秒更新；已完成或失败后停止自动请求，可手动刷新。DashScope 或其他非冻结评测身份可以建立和查看任务，但不会显示激活按钮；需先完成相应评测发布。</p></div><button aria-label="刷新构建记录" className={button} disabled={busy || query.isFetching} onClick={() => void query.refetch()} type="button">刷新</button></div><div className="overflow-x-auto" role="region" aria-label="向量构建表格" tabIndex={0}><table aria-busy={query.isFetching} className="w-full whitespace-nowrap text-left text-sm"><caption className="sr-only">向量空间构建记录</caption><thead className="border-y bg-muted/40 text-xs text-muted-foreground"><tr>{['创建时间', '模型/版本', '任务进度', '状态', '空间', '操作'].map(text => <th className="px-4 py-3" key={text} scope="col">{text}</th>)}</tr></thead><tbody className="divide-y">{query.isPending ? <tr><td className="p-12 text-center" colSpan={6}>正在读取构建记录…</td></tr> : query.isError ? <tr><td className="p-12 text-center" colSpan={6}><p role="alert">暂时无法读取构建记录。</p><button className={`${button} mt-3`} onClick={() => void query.refetch()} type="button">重试</button></td></tr> : !query.data?.items.length ? <tr><td className="p-12 text-center" colSpan={6}>尚无向量构建。创建不会自动激活。</td></tr> : query.data.items.map(build => <tr key={build.id}><td className="px-4 py-3 text-xs">{formatDate(build.requested_at)}</td><td className="px-4 py-3"><div>{build.embedding_model}</div><div className="mt-1 text-xs text-muted-foreground">{build.adapter_version} · {build.retrieval_version}</div></td><td className="px-4 py-3">{build.completed_count} 完成 / {build.pending_count} 等待 / {build.failed_count} 失败<br /><span className="text-xs text-muted-foreground">共 {build.expected_name_count}</span></td><td className="px-4 py-3">{labels[build.status]}</td><td className="px-4 py-3">{build.is_active ? '当前激活' : '未激活'}</td><td className="px-4 py-3">{build.failed_count > 0 ? <button className={button} disabled={busy} onClick={() => { setReason(''); setOperation({ kind: 'retry', build }) }} type="button">重试失败项</button> : null}{build.activation_ready && !build.is_active ? <button className={`${primary} ml-2`} disabled={busy} onClick={() => { setReason(''); setOperation({ kind: 'activate', build }) }} type="button">激活</button> : null}</td></tr>)}</tbody></table></div></section>
    {operation ? <section aria-label="确认向量操作" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4" role="dialog"><div className="w-full max-w-lg rounded-lg bg-card p-5 shadow-xl"><h2 className="text-lg font-semibold">{operation.kind === 'create' ? '创建向量构建' : operation.kind === 'retry' ? '重试失败任务' : '激活向量空间'}</h2><p className="mt-2 text-sm text-muted-foreground">{operation.kind === 'activate' ? '服务端会再次验证完成证据和冻结评测发布；失败时不会切换用户检索。' : '操作原因将写入管理员审计记录。'}</p><label className="mt-4 block text-sm" htmlFor="vector-reason">操作原因<textarea className="mt-2 w-full rounded border p-2" disabled={busy} id="vector-reason" maxLength={500} onChange={event => setReason(event.target.value)} rows={3} value={reason} /></label><div className="mt-5 flex justify-end gap-2"><button className={button} disabled={busy} onClick={() => setOperation(undefined)} type="button">取消</button><button className={primary} disabled={busy || !reason.trim()} onClick={() => void submit()} type="button">{busy ? '正在提交…' : '确认操作'}</button></div></div></section> : null}
  </main>
}
