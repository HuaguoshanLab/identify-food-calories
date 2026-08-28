import { CircleUserRound, MonitorSmartphone } from 'lucide-react'

import { routePaths } from '@/routePaths'

import { SettingsLinkRow } from './SettingsLinkRow'

export function MePage() {
  return (
    <section>
      <h1 className="text-[28px] font-bold leading-9 tracking-tight">我的</h1>
      <p className="mt-3 text-[15px] leading-6 text-muted-foreground">查看账号资料和已登录设备。</p>
      <div className="mt-4">
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
      </div>
    </section>
  )
}
