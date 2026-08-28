import { CalendarDays, NotebookText, ScanLine, UserRound, type LucideIcon } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { routePaths } from '@/routePaths'

type NavigationItem = {
  icon: LucideIcon
  label: string
  to: string
}

const navigationItems: readonly NavigationItem[] = [
  { icon: ScanLine, label: '分析', to: routePaths.analyze },
  { icon: NotebookText, label: '记录', to: routePaths.records },
  { icon: CalendarDays, label: '计划', to: routePaths.plans },
  { icon: UserRound, label: '我的', to: routePaths.me },
]

/**
 * Route state, rather than local click state, is the single source of truth for the active tab.
 * This keeps refreshes, deep links and keyboard navigation in sync with the visible selection.
 */
export function BottomNavigation() {
  return (
    <nav
      aria-label="主要导航"
      className="shrink-0 border-t bg-background pb-[max(0.5rem,env(safe-area-inset-bottom))]"
    >
      <div className="grid h-16 grid-cols-4">
        {navigationItems.map(({ icon: Icon, label, to }) => (
          <NavLink
            key={to}
            className={({ isActive }) => [
              'inline-flex min-h-11 flex-col items-center justify-center gap-1 text-xs leading-4 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none',
              isActive ? 'font-semibold text-primary' : 'font-normal',
            ].join(' ')}
            end
            to={to}
          >
            <Icon aria-hidden="true" className="h-[22px] w-[22px]" strokeWidth={2} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
