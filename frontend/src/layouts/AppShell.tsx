import { Outlet } from 'react-router-dom'

import { BottomNavigation } from './BottomNavigation'
import { MobileFrame } from './MobileFrame'
import { PageScrollArea } from './PageScrollArea'

/**
 * Tab roots share one scrolling main landmark. The navigation stays a flex sibling so content
 * never has to guess its bottom padding or use a brittle fixed-position offset.
 */
export function AppShell() {
  return (
    <MobileFrame>
      <a
        className="sr-only rounded-md bg-background px-4 py-2 text-sm font-semibold text-foreground shadow-sm ring-1 ring-border focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:outline-none"
        href="#main-content"
      >
        跳到主要内容
      </a>
      <PageScrollArea contentId="main-content">
        <Outlet />
      </PageScrollArea>
      <BottomNavigation />
    </MobileFrame>
  )
}
