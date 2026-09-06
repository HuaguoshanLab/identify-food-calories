import { ChevronLeft } from 'lucide-react'
import { Link, Outlet, type To } from 'react-router-dom'

import { MobileFrame } from './MobileFrame'
import { PageScrollArea } from './PageScrollArea'

type PublicAuthLayoutProps =
  | {
      mode: 'entry'
    }
  | {
      backTo: To
      mode: 'step'
    }

/**
 * Public routes deliberately use explicit destinations. History may be empty after an email link,
 * so `navigate(-1)` would strand users instead of returning to the correct auth step.
 */
export function PublicAuthLayout(props: PublicAuthLayoutProps) {
  const header = props.mode === 'entry' ? (
    <header className="flex h-[calc(52px+env(safe-area-inset-top))] shrink-0 items-end px-4">
      <Link className="inline-flex h-11 items-center text-base font-semibold text-foreground" to="/">
        饮食健康 Agent
      </Link>
    </header>
  ) : (
    <header className="flex h-[calc(52px+env(safe-area-inset-top))] shrink-0 items-end px-1">
      <Link
        aria-label="返回上一步"
        className="inline-flex h-11 w-11 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none"
        to={props.backTo}
      >
        <ChevronLeft aria-hidden="true" size={22} strokeWidth={2} />
      </Link>
    </header>
  )

  return (
    <MobileFrame>
      {header}
      <PageScrollArea className="pt-6 pb-[calc(24px+env(safe-area-inset-bottom))]" contentId="main-content">
        <Outlet />
      </PageScrollArea>
    </MobileFrame>
  )
}
