import { ArrowLeft } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

type AppHeaderProps = {
  title: string
}

/**
 * Detail routes must preserve the user's actual navigation path instead of rewriting it.
 */
export function AppHeader({ title }: AppHeaderProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true })
  }, [title, pathname])

  return (
    <header className="z-20 shrink-0 border-b border-border/60 bg-background pt-[env(safe-area-inset-top)]">
      <div className="relative flex h-12 items-center px-1">
        <button
          aria-label="返回上一页"
          className="inline-flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted"
          onClick={() => navigate(-1)}
          type="button"
        >
          <ArrowLeft aria-hidden="true" size={20} strokeWidth={2} />
        </button>
        <h1 ref={headingRef} tabIndex={-1} className="shell-heading absolute left-1/2 max-w-[60%] -translate-x-1/2 truncate text-center text-[18px] font-semibold leading-6">{title}</h1>
      </div>
    </header>
  )
}
