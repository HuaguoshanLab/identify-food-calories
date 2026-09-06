import { NavLink } from 'react-router-dom'

import { tabNavigation } from './tabNavigation'

/**
 * Route state, rather than local click state, is the single source of truth for the active tab.
 * This keeps refreshes, deep links and keyboard navigation in sync with the visible selection.
 */
export function BottomNavigation() {
  return (
    <nav
      aria-label="主要导航"
      className="z-20 shrink-0 border-t border-border/70 bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md"
    >
      <div className="grid h-16 grid-cols-4">
        {tabNavigation.map(({ icon: Icon, label, to }) => (
          <NavLink
            key={to}
            className={({ isActive }) => [
              'inline-flex min-h-11 flex-col items-center justify-center gap-1 text-[11px] leading-4 transition-colors hover:text-foreground',
              isActive ? 'font-semibold text-primary' : 'font-normal text-muted-foreground',
            ].join(' ')}
            end
            to={to}
          >
            {({ isActive }) => <>
              <Icon aria-hidden="true" className="h-[22px] w-[22px]" strokeWidth={isActive ? 2.2 : 1.8} />
              <span>{label}</span>
            </>}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
