import { useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { AdminHeader } from './AdminHeader'
import { AdminSidebar } from './AdminSidebar'
import { AdminTabs } from './AdminTabs'
import { adminRouteMeta } from './adminNavigation'

type NavigationKind = 'mobile' | 'desktop'
type AdminShellProps = PropsWithChildren<Readonly<{ onLogout?: () => void }>>

function navigationKind(width: number): NavigationKind {
  return width >= 1024 ? 'desktop' : 'mobile'
}

export function AdminShell({ children, onLogout }: AdminShellProps) {
  const { accessToken, clearSession } = useAdminAuth()
  const [kind, setKind] = useState<NavigationKind>(() => navigationKind(window.innerWidth))
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.innerWidth < 1280)
  const navigationTrigger = useRef<HTMLButtonElement>(null)
  const mainRef = useRef<HTMLElement>(null)
  const location = useLocation()
  const desktop = kind === 'desktop'

  useEffect(() => {
    const onResize = () => {
      const nextKind = navigationKind(window.innerWidth)
      setKind(nextKind)
      if (nextKind === 'desktop') setNavigationOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (!navigationOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setNavigationOpen(false)
        navigationTrigger.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [navigationOpen])

  useEffect(() => {
    if (!navigationOpen) return
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = originalOverflow }
  }, [navigationOpen])

  async function logout() {
    const token = accessToken
    clearSession()
    onLogout?.()
    if (token) {
      // The local clear is intentionally first; a failed network revocation must not retain data.
      await fetch('/api/v1/auth/logout', { credentials: 'include', headers: { Authorization: `Bearer ${token}` }, method: 'POST' }).catch(() => undefined)
    }
  }

  const collapsed = desktop && sidebarCollapsed
  const sidebarWidth = collapsed ? 'lg:pl-[76px]' : 'lg:pl-[248px]'
  const closeNavigation = () => {
    setNavigationOpen(false)
    navigationTrigger.current?.focus()
  }

  return <div data-navigation={kind} data-sidebar-collapsed={collapsed} data-testid="admin-shell" className="admin-shell-root min-h-dvh overflow-x-hidden bg-slate-50 text-foreground lg:h-dvh lg:overflow-hidden">
    <a className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-lg focus:bg-white focus:p-3 focus:shadow-lg" href="#admin-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a>

    {desktop ? <div className={`fixed inset-y-0 left-0 z-40 transition-[width] duration-200 ${collapsed ? 'w-[76px]' : 'w-[248px]'}`}><AdminSidebar collapsed={collapsed} onCollapse={() => setSidebarCollapsed(true)} /></div> : null}

    {!desktop && navigationOpen ? <div className="fixed inset-0 z-50 bg-slate-950/45 backdrop-blur-[2px]" onMouseDown={closeNavigation}>
      <div aria-label="后台导航" aria-modal="true" className="h-full w-[min(280px,86vw)] shadow-2xl" id="admin-navigation-drawer" onMouseDown={(event) => event.stopPropagation()} role="dialog">
        <AdminSidebar drawer onClose={closeNavigation} onNavigate={() => setNavigationOpen(false)} />
      </div>
    </div> : null}

    <div className={`min-w-0 transition-[padding] duration-200 lg:h-dvh lg:overflow-hidden ${sidebarWidth}`}>
      <div className="sticky top-0 z-30">
        <AdminHeader breadcrumbs={adminRouteMeta(location.pathname).breadcrumbs} collapsed={collapsed} desktop={desktop} navigationTriggerRef={navigationTrigger} onLogout={() => void logout()} onNavigationToggle={() => {
          if (desktop) setSidebarCollapsed((value) => !value)
          else setNavigationOpen(true)
        }} />
        <AdminTabs />
      </div>
      <main id="admin-main" ref={mainRef} tabIndex={-1} className="min-w-0 lg:h-[calc(100dvh-6.75rem)] lg:overflow-hidden">{children ?? <Outlet />}</main>
    </div>
  </div>
}
