import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { readRoles, SystemApiError } from './api'

export function AdminRolesPage() {
  const { accessToken, clearSession } = useAdminAuth()
  const query = useQuery({ enabled: Boolean(accessToken), queryKey: ['admin', 'system', 'roles'], queryFn: () => readRoles(accessToken as string) })
  const secureError = query.error instanceof SystemApiError && [401, 403].includes(query.error.status)
  useEffect(() => { if (secureError) clearSession() }, [clearSession, secureError])
  if (secureError) return <main className="p-8"><h1 className="text-[28px] font-semibold">无后台访问权限</h1></main>
  return <main className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6 lg:p-8" aria-labelledby="admin-roles-title"><header><h1 className="text-[28px] font-semibold" id="admin-roles-title">角色管理</h1><p className="mt-1 text-sm text-muted-foreground">系统当前使用固定角色。权限由后端执行，这里只展示真实能力。</p></header>{query.isLoading ? <p aria-busy="true">正在读取角色…</p> : null}{query.isError ? <p className="rounded-md border p-4" role="alert">暂时无法读取角色，请稍后重试。</p> : null}<div className="grid gap-4 lg:grid-cols-2">{query.data?.items.map((role) => <section className="rounded-lg border bg-card p-5" key={role.role}><div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold">{role.label}</h2><p className="mt-2 text-sm text-muted-foreground">{role.description}</p></div><span className="rounded-full bg-muted px-3 py-1 text-sm admin-numeric">{role.account_count} 个账号</span></div><h3 className="mt-5 text-sm font-semibold">权限范围</h3><ul className="mt-2 grid gap-2 text-sm">{role.permissions.map((permission) => <li className="flex gap-2" key={permission}><span aria-hidden="true" className="text-primary">✓</span>{permission}</li>)}</ul></section>)}</div><p className="rounded-md border bg-muted p-4 text-sm">当前不支持自定义角色或权限点。角色变更请在“管理员管理”完成。</p></main>
}
