import { ChevronRight, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

type SettingsLinkRowProps = {
  description: string
  icon: LucideIcon
  title: string
  to: string
}

/**
 * A settings destination is one native link, rather than a clickable wrapper, so touch, keyboard
 * and assistive-technology activation all follow the same Router path.
 */
export function SettingsLinkRow({ description, icon: Icon, title, to }: SettingsLinkRowProps) {
  return (
    <Link
      className="flex min-h-14 items-center gap-3 border-b border-border/60 px-4 py-3.5 last:border-b-0 text-foreground transition-colors hover:bg-muted focus-visible:outline-none"
      to={to}
    >
      <Icon aria-hidden="true" className="h-5 w-5 shrink-0 text-primary" strokeWidth={2} />
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] font-medium leading-6">{title}</span>
        <span className="block text-[13px] leading-5 text-muted-foreground">{description}</span>
      </span>
      <ChevronRight aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" strokeWidth={2} />
    </Link>
  )
}
