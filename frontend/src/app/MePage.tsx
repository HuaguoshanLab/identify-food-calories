import { Brain, CircleUserRound, MonitorSmartphone } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { routePaths } from '@/routePaths'

import { SettingsLinkRow } from './SettingsLinkRow'

export function MePage() {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <section>
      <h1 ref={headingRef} tabIndex={-1} className="text-[28px] font-bold leading-9 tracking-tight">我的</h1>
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
        <SettingsLinkRow
          description="查看和管理会影响后续建议的偏好。"
          icon={Brain}
          title="饮食偏好与记忆"
          to="/app/me/memories"
        />
      </div>
    </section>
  )
}
