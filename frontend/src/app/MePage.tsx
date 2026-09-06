import { Brain, CircleUserRound, MonitorSmartphone, Ruler } from 'lucide-react'

import { useAuth } from '@/auth/useAuth'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

import { routePaths } from '@/routePaths'

import { SettingsLinkRow } from './SettingsLinkRow'

export function MePage() {
  const { user } = useAuth()

  return (
    <section className="space-y-3">
      {user ? <Card>
        <CardContent className="flex items-center gap-3">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-muted text-primary">
            <CircleUserRound aria-hidden="true" className="size-6" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-base font-semibold">我的账号</p>
            <p className="mt-0.5 break-all text-[13px] leading-5 text-muted-foreground">{user.email}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="outline">{user.role === 'admin' ? '管理员' : '普通用户'}</Badge>
              <Badge variant="outline">{user.is_active ? '账号正常' : '账号停用'}</Badge>
            </div>
          </div>
        </CardContent>
      </Card> : null}
      <Card className="gap-0 py-0">
        <SettingsLinkRow
          description="查看、编辑或删除身体资料和饮食目标"
          icon={Ruler}
          title="个人资料"
          to={routePaths.profile}
        />
        <SettingsLinkRow
          description="查看邮箱、账号状态与角色"
          icon={CircleUserRound}
          title="账号资料"
          to={routePaths.account}
        />
        <SettingsLinkRow
          description="查看并管理已登录设备"
          icon={MonitorSmartphone}
          title="登录会话"
          to={routePaths.sessions}
        />
        <SettingsLinkRow
          description="查看和管理会影响后续建议的偏好。"
          icon={Brain}
          title="饮食偏好与记忆"
          to="/app/me/memories"
        />
      </Card>
    </section>
  )
}
