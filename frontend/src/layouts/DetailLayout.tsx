import { Outlet } from 'react-router-dom'

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
  return (
    <MobileFrame>
      <AppHeader title={title} />
      <PageScrollArea contentId="main-content">
        <Outlet />
      </PageScrollArea>
    </MobileFrame>
  )
}
