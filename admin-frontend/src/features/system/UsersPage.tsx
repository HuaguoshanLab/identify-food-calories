import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { AlertDialog, AlertDialogContent } from '@/components/ui/AlertDialog'
import { changeRole, readUsers, SystemApiError, type AdminUser, type UserFilters } from './api'

function accountStatus(user: AdminUser) {
  if (!user.is_active) return '已停用'
  if (!user.email_verified_at) return '未验证'
  return '正常'
}

export function AdminUsersPage() {
  const { accessToken, clearSession, identity } = useAdminAuth()
  const client = useQueryClient()
  const [draft, setDraft] = useState<UserFilters>({ search: '', role: '', status: '', page: 1, pageSize: 20 })
  const [filters, setFilters] = useState<UserFilters>(draft)
  const [selected, setSelected] = useState<AdminUser>()
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const cancelRef = useRef<HTMLButtonElement>(null)
  const query = useQuery({ enabled: Boolean(accessToken), queryKey: ['admin', 'system', 'users', filters], queryFn: () => readUsers(accessToken as string, filters) })
  const mutation = useMutation({ mutationFn: ({ user, reasonText }: { user: AdminUser, reasonText: string }) => changeRole(accessToken as string, user.id, user.role === 'admin' ? 'user' : 'admin', reasonText), onSuccess: async (result) => { await client.invalidateQueries({ queryKey: ['admin', 'system'] }); setMessage(`角色已从 ${result.before_role} 更新为 ${result.after_role}，操作已记录。`); setSelected(undefined); setReason('') } })
  const secureError = query.error instanceof SystemApiError && [401, 403].includes(query.error.status)
  useEffect(() => { if (secureError) clearSession() }, [clearSession, secureError])
  if (secureError) return <main className="p-8"><h1 className="text-[28px] font-semibold">无后台访问权限</h1></main>
  const totalPages = query.data ? Math.max(1, Math.ceil(query.data.total / query.data.page_size)) : 1
  function submitFilters(event: FormEvent) { event.preventDefault(); setFilters({ ...draft, page: 1 }) }
  return <main className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6 lg:p-8" aria-labelledby="admin-users-title">
    <header><h1 className="text-[28px] font-semibold" id="admin-users-title">管理员管理</h1><p className="mt-1 text-sm text-muted-foreground">查看全部账号并审计地授予或撤销管理员角色。</p></header>
    {message ? <p className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm" role="status">{message}</p> : null}
    <form className="grid gap-3 rounded-lg border bg-card p-4 md:grid-cols-[minmax(15rem,1fr)_12rem_12rem_auto]" onSubmit={submitFilters}>
      <label className="grid gap-1 text-sm" htmlFor="user-search">邮箱<input className="h-10 rounded-md border px-3" id="user-search" onChange={(e) => setDraft({ ...draft, search: e.target.value })} placeholder="搜索邮箱" value={draft.search} /></label>
      <label className="grid gap-1 text-sm" htmlFor="user-role">角色<select className="h-10 rounded-md border px-3" id="user-role" onChange={(e) => setDraft({ ...draft, role: e.target.value as UserFilters['role'] })} value={draft.role}><option value="">全部角色</option><option value="admin">管理员</option><option value="user">普通用户</option></select></label>
      <label className="grid gap-1 text-sm" htmlFor="user-status">状态<select className="h-10 rounded-md border px-3" id="user-status" onChange={(e) => setDraft({ ...draft, status: e.target.value as UserFilters['status'] })} value={draft.status}><option value="">全部状态</option><option value="active">正常</option><option value="inactive">已停用</option><option value="unverified">未验证</option></select></label>
      <button className="h-10 self-end rounded-md bg-primary px-5 text-primary-foreground" type="submit">查询</button>
    </form>
    {query.isLoading ? <p aria-busy="true">正在读取账号…</p> : null}
    {query.isError && !secureError ? <p className="rounded-md border p-4" role="alert">暂时无法读取账号，请稍后重试。</p> : null}
    {query.data ? <section className="overflow-hidden rounded-lg border bg-card" aria-label="账号列表"><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-muted"><tr><th className="px-4 py-3">邮箱</th><th className="px-4 py-3">角色</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">注册时间</th><th className="px-4 py-3 text-right">操作</th></tr></thead><tbody>{query.data.items.map((user) => <tr className="border-t" key={user.id}><td className="px-4 py-3 font-medium">{user.email}</td><td className="px-4 py-3">{user.role === 'admin' ? '管理员' : '普通用户'}</td><td className="px-4 py-3">{accountStatus(user)}</td><td className="px-4 py-3">{new Date(user.created_at).toLocaleDateString('zh-CN')}</td><td className="px-4 py-3 text-right"><button className="rounded-md border px-3 py-2 disabled:cursor-not-allowed disabled:opacity-50" disabled={user.id === identity?.id || (user.role === 'user' && accountStatus(user) !== '正常')} onClick={() => { setSelected(user); setMessage('') }} type="button">{user.role === 'admin' ? '撤销管理员' : '设为管理员'}</button></td></tr>)}</tbody></table></div>{query.data.items.length === 0 ? <p className="p-8 text-center text-muted-foreground">没有符合条件的账号</p> : null}</section> : null}
    {query.data ? <div className="flex items-center justify-between text-sm"><span>共 {query.data.total} 个账号</span><div className="flex items-center gap-2"><button className="rounded-md border px-3 py-2 disabled:opacity-50" disabled={(filters.page ?? 1) <= 1} onClick={() => setFilters({ ...filters, page: (filters.page ?? 1) - 1 })}>上一页</button><span>{filters.page ?? 1} / {totalPages}</span><button className="rounded-md border px-3 py-2 disabled:opacity-50" disabled={(filters.page ?? 1) >= totalPages} onClick={() => setFilters({ ...filters, page: (filters.page ?? 1) + 1 })}>下一页</button></div></div> : null}
    <AlertDialog.Root open={Boolean(selected)} onOpenChange={(open) => { if (!open) { setSelected(undefined); setReason('') } }}><AlertDialogContent initialFocus={cancelRef} aria-labelledby="role-change-title"><AlertDialog.Title className="text-xl font-semibold" id="role-change-title">确认{selected?.role === 'admin' ? '撤销管理员' : '设为管理员'}？</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-muted-foreground">目标账号：{selected?.email}。角色变更会立即影响后台权限，并写入不可变审计。</AlertDialog.Description><label className="mt-4 grid gap-2 text-sm" htmlFor="role-change-reason">变更原因<textarea className="min-h-24 rounded-md border p-3" id="role-change-reason" maxLength={500} onChange={(e) => setReason(e.target.value)} value={reason} /></label>{mutation.error ? <p className="mt-3 text-sm" role="alert">{mutation.error instanceof SystemApiError && mutation.error.status === 409 ? mutation.error.detail ?? '角色变更冲突，请刷新后重试。' : '暂时无法变更角色。'}</p> : null}<div className="mt-6 flex justify-end gap-3"><AlertDialog.Close className="h-10 rounded-md border px-4" ref={cancelRef}>取消</AlertDialog.Close><button className="h-10 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50" disabled={!reason.trim() || mutation.isPending || !selected} onClick={() => selected && mutation.mutate({ user: selected, reasonText: reason.trim() })} type="button">{mutation.isPending ? '正在提交…' : '确认变更角色'}</button></div></AlertDialogContent></AlertDialog.Root>
  </main>
}
