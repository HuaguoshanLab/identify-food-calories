import { ChevronLeft } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'

import { routePaths } from '@/routePaths'

type AppHeaderProps = {
  backLabel?: string
  backTo?: string
  title: string
}

/**
 * Detail routes use an explicit destination instead of browser history so direct links stay usable.
 */
export function AppHeader({ backLabel = '返回我的', backTo = routePaths.me, title }: AppHeaderProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [title])

  return (
    <header className="flex h-[calc(52px+env(safe-area-inset-top))] shrink-0 items-end border-b bg-background px-1">
      <Link
        aria-label={backLabel}
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none"
        to={backTo}
      >
        <ChevronLeft aria-hidden="true" size={22} strokeWidth={2} />
      </Link>
      <h1 ref={headingRef} tabIndex={-1} className="min-w-0 flex-1 truncate py-3 text-center text-base font-semibold leading-6">{title}</h1>
      <span aria-hidden="true" className="h-11 w-11 shrink-0" />
    </header>
  )
}
