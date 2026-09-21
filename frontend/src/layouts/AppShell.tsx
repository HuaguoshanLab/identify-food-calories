import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { BottomNavigation } from './BottomNavigation'
import { MobileFrame } from './MobileFrame'
import { PageScrollArea } from './PageScrollArea'
import { TabHeader } from './TabHeader'

/**
 * Tab roots share one scrolling main landmark. The navigation stays a flex sibling so content
 * never has to guess its bottom padding or use a brittle fixed-position offset.
 */
export function AppShell() {
  const { pathname } = useLocation()
  const scrollRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0
  }, [pathname])

  return (
    <MobileFrame>
      <a
        className="sr-only rounded-md bg-background px-4 py-2 text-sm font-semibold text-foreground shadow-sm ring-1 ring-border focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-30 focus:outline-none"
        href="#main-content"
      >
        跳到主要内容
      </a>
      <TabHeader />
      <PageScrollArea className="min-[375px]:px-5" contentId="main-content" ref={scrollRef}>
        <Outlet />
      </PageScrollArea>
      <BottomNavigation />
    </MobileFrame>
  )
}
