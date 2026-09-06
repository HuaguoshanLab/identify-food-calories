import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { AppHeader } from './AppHeader'
import { MobileFrame } from './MobileFrame'
import { PageScrollArea } from './PageScrollArea'

type DetailLayoutProps = {
  title: string
}

/**
 * Detail pages are intentionally outside AppShell: a return header and tab bar must never compete.
 */
export function DetailLayout({ title }: DetailLayoutProps) {
  const { pathname } = useLocation()
  const scrollRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0
  }, [pathname])

  return (
    <MobileFrame>
      <AppHeader title={title} />
      <PageScrollArea className="pb-[calc(16px+env(safe-area-inset-bottom))]" contentId="main-content" ref={scrollRef}>
        <Outlet />
      </PageScrollArea>
    </MobileFrame>
  )
}
