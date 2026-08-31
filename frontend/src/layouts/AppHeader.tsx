import { ChevronLeft } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

type AppHeaderProps = {
  title: string
}

/**
 * Detail routes must preserve the user's actual navigation path instead of rewriting it.
 */
export function AppHeader({ title }: AppHeaderProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    headingRef.current?.focus()
  }, [title])

  return (
    <header className="flex h-[calc(52px+env(safe-area-inset-top))] shrink-0 items-end border-b bg-background px-1">
      <button
        aria-label="返回上一页"
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none"
        onClick={() => navigate(-1)}
        type="button"
      >
        <ChevronLeft aria-hidden="true" size={22} strokeWidth={2} />
      </button>
      <h1 ref={headingRef} tabIndex={-1} className="min-w-0 flex-1 truncate py-3 text-center text-base font-semibold leading-6">{title}</h1>
      <span aria-hidden="true" className="h-11 w-11 shrink-0" />
    </header>
  )
}
