import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { History } from 'lucide-react'
import { routePaths } from '@/routePaths'

import { tabNavigation } from './tabNavigation'

export function TabHeader() {
  const { pathname } = useLocation()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const current = tabNavigation.find((item) => item.to === pathname)

  useEffect(() => {
    // 仅页面切换移动焦点；SSE 更新、查询参数变化不打断用户输入。
    headingRef.current?.focus({ preventScroll: true })
  }, [pathname])

  if (!current) return null
  const Icon = current.icon

  return (
    <header className="z-20 shrink-0 bg-background pt-[env(safe-area-inset-top)]">
      <div className="flex h-20 items-center gap-3 px-5">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground"><Icon aria-hidden="true" className="size-5" /></span>
        <h1 className="shell-heading min-w-0 truncate text-[22px] font-bold leading-7 tracking-tight" ref={headingRef} tabIndex={-1}>
          {current.title}
        </h1>
        {pathname === routePaths.plans ? <Link aria-label="历史计划" title="历史计划" className="ml-auto flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-xl px-3 text-sm font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" to={routePaths.planHistory}><History aria-hidden="true" className="size-4" /><span>历史</span></Link> : null}
      </div>
    </header>
  )
}
