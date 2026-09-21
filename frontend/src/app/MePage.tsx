import { Brain, CircleUserRound, MonitorSmartphone, Ruler } from 'lucide-react'

import { useAuth } from '@/auth/useAuth'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { routePaths } from '@/routePaths'
import { SettingsLinkRow } from './SettingsLinkRow'

export function MePage() {
  const { user } = useAuth()

  return (
    <section className="space-y-5">
      {user ? <Card className="border-primary/15 bg-accent/60 py-6">
        <CardContent className="flex items-center gap-4">
          <div className="flex size-16 shrink-0 items-center justify-center rounded-full bg-card text-primary">
            <CircleUserRound aria-hidden="true" className="size-8" strokeWidth={1.5} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-lg font-semibold">我的账号</p>
            <p className="mt-1 break-all text-[13px] leading-5 text-muted-foreground">{user.email}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="outline">{user.role === 'admin' ? '管理员' : '普通用户'}</Badge>
              <Badge variant="outline">{user.is_active ? '账号正常' : '账号停用'}</Badge>
            </div>
          </div>
        </CardContent>
      </Card> : null}
      <div>
        <h2 className="mb-3 px-1 text-sm font-semibold text-muted-foreground">饮食与目标</h2>
        <Card className="gap-0 py-0">
          <SettingsLinkRow description="身体资料与饮食目标" icon={Ruler} title="个人资料" to={routePaths.profile} />
          <SettingsLinkRow description="忌口、过敏原与口味" icon={Brain} title="饮食偏好与记忆" to="/app/me/memories" />
        </Card>
      </div>
      <div>
        <h2 className="mb-3 px-1 text-sm font-semibold text-muted-foreground">账号与安全</h2>
        <Card className="gap-0 py-0">
          <SettingsLinkRow icon={CircleUserRound} title="账号资料" to={routePaths.account} />
          <SettingsLinkRow icon={MonitorSmartphone} title="登录会话" to={routePaths.sessions} />
        </Card>
      </div>
    </section>
  )
}
