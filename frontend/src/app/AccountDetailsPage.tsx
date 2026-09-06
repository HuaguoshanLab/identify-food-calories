import { useAuth } from '@/auth/useAuth'

const roleLabels: Record<string, string> = {
  admin: '管理员',
  user: '普通用户',
}

/**
 * Account data is intentionally read-only: `/users/me` is the identity authority and this phase
 * has no profile-editing contract. Adding local draft state here would falsely imply persistence.
 */
export function AccountDetailsPage() {
  const { user } = useAuth()

  // RouteGuards normally renders its identity-recovery boundary before this component. This is a
  // defensive presentation fallback only; it never issues another identity request on its own.
  if (!user) {
    return (
      <section>
        <h2 className="text-xl font-semibold leading-7">无法加载账号信息</h2>
        <p role="alert" className="mt-2 text-[15px] leading-6 text-muted-foreground">请检查网络后重新尝试。</p>
      </section>
    )
  }

  return (
    <section aria-label="账号资料">
      <dl className="divide-y divide-border/60 rounded-xl border border-border bg-card px-4 text-[15px] leading-6 shadow-sm">
        <div className="space-y-1 py-4">
          <dt className="text-[13px] leading-5 text-muted-foreground">邮箱</dt>
          <dd className="break-all font-medium text-foreground">{user.email}</dd>
        </div>
        <div className="space-y-1 py-4">
          <dt className="text-[13px] leading-5 text-muted-foreground">账号状态</dt>
          <dd className="font-medium text-foreground">{user.is_active ? '正常' : '已停用'}</dd>
        </div>
        <div className="space-y-1 py-4">
          <dt className="text-[13px] leading-5 text-muted-foreground">角色</dt>
          <dd className="font-medium text-foreground">{roleLabels[user.role] ?? '普通用户'}</dd>
        </div>
      </dl>
    </section>
  )
}
