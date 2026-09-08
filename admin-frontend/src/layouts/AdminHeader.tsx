import { Bell, ChevronRight, LogOut, Menu, PanelLeftOpen, Search, UserRound } from 'lucide-react'
import { useEffect, useRef, useState, type RefObject } from 'react'

type AdminHeaderProps = Readonly<{
  breadcrumbs: readonly string[]
  collapsed: boolean
  desktop: boolean
  onLogout: () => void
  onNavigationToggle: () => void
  navigationTriggerRef: RefObject<HTMLButtonElement | null>
}>

export function AdminHeader({ breadcrumbs, collapsed, desktop, navigationTriggerRef, onLogout, onNavigationToggle }: AdminHeaderProps) {
  const [sessionOpen, setSessionOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sessionOpen) return
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setSessionOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSessionOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [sessionOpen])

  return <header className="flex h-16 items-center justify-between gap-3 border-b bg-white px-4 sm:px-5 lg:px-6">
    <div className="flex min-w-0 items-center gap-3">
      <button aria-label={desktop ? (collapsed ? '展开侧边栏' : '折叠侧边栏') : '打开导航'} className="grid size-10 shrink-0 cursor-pointer place-items-center rounded-lg border border-slate-200 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950" onClick={onNavigationToggle} ref={navigationTriggerRef} type="button">
        {desktop && collapsed ? <PanelLeftOpen aria-hidden="true" size={19} /> : <Menu aria-hidden="true" size={20} />}
      </button>
      <nav aria-label="面包屑" className="min-w-0">
        <ol className="flex min-w-0 items-center gap-1.5 text-sm">
          <li className="hidden text-slate-500 sm:block">后台首页</li>
          {breadcrumbs.map((crumb, index) => <li className="flex min-w-0 items-center gap-1.5" key={`${crumb}-${index}`}>
            <ChevronRight aria-hidden="true" className="hidden shrink-0 text-slate-300 sm:block" size={15} />
            <span aria-current={index === breadcrumbs.length - 1 ? 'page' : undefined} className={`truncate ${index === breadcrumbs.length - 1 ? 'font-medium text-slate-900' : 'hidden text-slate-500 sm:block'}`}>{crumb}</span>
          </li>)}
        </ol>
      </nav>
    </div>

    <div className="flex shrink-0 items-center gap-1 sm:gap-2">
      <button aria-label="全局搜索，暂未开放" className="grid size-10 place-items-center rounded-lg text-slate-300" disabled title="暂未开放" type="button"><Search aria-hidden="true" size={19} /></button>
      <button aria-label="通知，暂未开放" className="grid size-10 place-items-center rounded-lg text-slate-300" disabled title="暂未开放" type="button"><Bell aria-hidden="true" size={19} /></button>
      <div className="relative" ref={menuRef}>
        <button aria-expanded={sessionOpen} aria-haspopup="menu" aria-label="打开会话菜单" className="flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-2 transition-colors hover:bg-slate-50 sm:pr-3" onClick={() => setSessionOpen((open) => !open)} type="button">
          <span className="grid size-7 place-items-center rounded-md bg-slate-900 text-white"><UserRound aria-hidden="true" size={16} /></span>
          <span className="hidden text-sm font-medium text-slate-700 sm:inline">管理员</span>
        </button>
        {sessionOpen ? <div className="absolute right-0 z-40 mt-2 min-w-44 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-900/10" role="menu">
          <div className="border-b px-3 py-2 text-xs text-slate-500">当前后台会话</div>
          <button className="mt-1 flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-100" onClick={onLogout} role="menuitem" type="button"><LogOut aria-hidden="true" size={16} />退出登录</button>
        </div> : null}
      </div>
    </div>
  </header>
}
