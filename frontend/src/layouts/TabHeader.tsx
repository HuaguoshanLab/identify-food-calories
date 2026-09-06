import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

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
    <header className="z-20 shrink-0 border-b border-border/60 bg-background pt-[env(safe-area-inset-top)]">
      <div className="flex h-14 items-center gap-2.5 px-4">
        <Icon aria-hidden="true" className="size-5 shrink-0 text-primary" />
        <h1 className="shell-heading min-w-0 truncate text-[20px] font-bold leading-6" ref={headingRef} tabIndex={-1}>
          {current.title}
        </h1>
      </div>
    </header>
  )
}
