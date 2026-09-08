import { ChevronDown, Leaf, PanelLeftClose, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

import { adminNavigation } from './adminNavigation'

type AdminSidebarProps = Readonly<{
  collapsed?: boolean
  drawer?: boolean
  onClose?: () => void
  onCollapse?: () => void
  onNavigate?: () => void
}>

export function AdminSidebar({ collapsed = false, drawer = false, onClose, onCollapse, onNavigate }: AdminSidebarProps) {
  const location = useLocation()
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({ content: true, operations: true, 'system-management': true })

  return <aside aria-label="后台侧边栏" className="flex h-full flex-col bg-slate-950 text-slate-200">
    <div className={`flex h-16 shrink-0 items-center border-b border-white/10 ${collapsed ? 'justify-center px-2' : 'justify-between px-4'}`}>
      <NavLink aria-label="饮食健康管理后台首页" className="flex min-w-0 items-center gap-3" onClick={onNavigate} to="/admin/overview">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-400 text-slate-950 shadow-sm"><Leaf aria-hidden="true" size={20} strokeWidth={2.4} /></span>
        {!collapsed ? <span className="min-w-0"><span className="block truncate text-sm font-semibold text-white">饮食健康</span><span className="block truncate text-[11px] tracking-[0.18em] text-slate-400">ADMIN CONSOLE</span></span> : null}
      </NavLink>
      {drawer ? <button aria-label="关闭导航" autoFocus className="grid size-9 cursor-pointer place-items-center rounded-lg text-slate-400 transition-colors hover:bg-white/10 hover:text-white" onClick={onClose} type="button"><X aria-hidden="true" size={19} /></button> : null}
    </div>

    <nav aria-label="后台导航" className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
      {adminNavigation.map((group, groupIndex) => {
        const expanded = openGroups[group.id] ?? true
        return <section className={groupIndex ? 'mt-5 border-t border-white/8 pt-5' : ''} key={group.id}>
          {group.label && !collapsed ? <button aria-expanded={expanded} className="mb-2 flex w-full cursor-pointer items-center justify-between rounded-md px-3 py-1 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 transition-colors hover:text-slate-300" onClick={() => setOpenGroups((groups) => ({ ...groups, [group.id]: !expanded }))} type="button">
            <span>{group.label}</span><ChevronDown aria-hidden="true" className={`transition-transform duration-200 ${expanded ? '' : '-rotate-90'}`} size={14} />
          </button> : null}
          {(!group.label || collapsed || expanded) ? <div className="grid gap-1">
            {group.items.map(({ icon: Icon, label, to }) => <NavLink
              aria-current={(location.pathname === to || (to === '/admin/catalog' && location.pathname.startsWith('/admin/catalog/'))) ? 'page' : undefined}
              className={({ isActive }) => `group flex min-h-11 cursor-pointer items-center rounded-lg text-sm transition-colors duration-200 ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'} ${(isActive || (to === '/admin/catalog' && location.pathname.startsWith('/admin/catalog/'))) ? 'bg-emerald-400/14 font-medium text-emerald-300 ring-1 ring-inset ring-emerald-300/15' : 'text-slate-400 hover:bg-white/[0.07] hover:text-slate-100'}`}
              key={to}
              onClick={onNavigate}
              title={collapsed ? label : undefined}
              to={to}
            >
              <Icon aria-hidden="true" className="shrink-0" size={19} strokeWidth={1.9} />
              {!collapsed ? <span className="truncate">{label}</span> : <span className="sr-only">{label}</span>}
            </NavLink>)}
          </div> : null}
        </section>
      })}
    </nav>

    {!drawer && !collapsed ? <div className="border-t border-white/10 p-3">
      <button aria-label="折叠侧边栏" className="flex min-h-10 w-full cursor-pointer items-center gap-3 rounded-lg px-3 text-sm text-slate-400 transition-colors hover:bg-white/[0.07] hover:text-white" onClick={onCollapse} type="button"><PanelLeftClose aria-hidden="true" size={18} /><span>收起导航</span></button>
    </div> : null}
  </aside>
}
