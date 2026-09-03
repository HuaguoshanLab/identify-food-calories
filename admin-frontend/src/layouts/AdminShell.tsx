import { useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAdminAuth } from '@/auth/AdminAuthProvider'

type NavigationKind = 'mobile' | 'sheet' | 'compact' | 'full'
type AdminShellProps = PropsWithChildren<Readonly<{ onLogout?: () => void }>>

const navigation = [
  { label: '概览', to: '/admin/overview' },
  { label: '营养目录', to: '/admin/catalog' },
  { label: '运行审计', to: '/admin/runs' },
  { label: '模型配置', to: '/admin/model-configs' },
  { label: '操作审计', to: '/admin/audit' },
] as const

function navigationKind(width: number): NavigationKind {
  if (width >= 1280) return 'full'
  if (width >= 1024) return 'compact'
  if (width >= 768) return 'sheet'
  return 'mobile'
}

function Navigation({ onNavigate }: Readonly<{ onNavigate?: () => void }>) {
  return <nav aria-label="后台导航" className="grid gap-1">
    {navigation.map((item) => <NavLink className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-muted font-medium' : ''}`} key={item.to} onClick={onNavigate} to={item.to}>{item.label}</NavLink>)}
  </nav>
}

export function AdminShell({ children, onLogout }: AdminShellProps) {
  const { accessToken, clearSession } = useAdminAuth()
  const [kind, setKind] = useState<NavigationKind>(() => navigationKind(window.innerWidth))
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [sessionOpen, setSessionOpen] = useState(false)
  const navigationTrigger = useRef<HTMLButtonElement>(null)
  const mainRef = useRef<HTMLElement>(null)
  const location = useLocation()

  useEffect(() => {
    const onResize = () => setKind(navigationKind(window.innerWidth))
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

  async function logout() {
    const token = accessToken
    clearSession()
    onLogout?.()
    if (token) {
      // The local clear is intentionally first; a failed network revocation must not retain data.
      await fetch('/api/v1/auth/logout', { credentials: 'include', headers: { Authorization: `Bearer ${token}` }, method: 'POST' }).catch(() => undefined)
    }
  }

  const title = navigation.find((item) => item.to === location.pathname)?.label ?? '管理后台'
  const sidebarWidth = kind === 'full' ? 'w-[240px]' : 'w-[208px]'
  return <div data-navigation={kind} data-testid="admin-shell" className="admin-runtime-root grid min-h-dvh overflow-x-hidden bg-background text-foreground lg:grid-cols-[auto_1fr]">
    <a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[70] focus:rounded focus:bg-card focus:p-3" href="#admin-main" onClick={() => mainRef.current?.focus()}>跳到主要内容</a>
    {(kind === 'compact' || kind === 'full') ? <aside className={`${sidebarWidth} border-r bg-card p-4`}><p className="mb-6 text-sm font-semibold">饮食健康后台</p><Navigation /></aside> : null}
    <div className="min-w-0"><header className="flex min-h-16 items-center justify-between gap-3 border-b bg-card px-4 lg:px-6"><div className="flex items-center gap-3">{kind === 'sheet' ? <button aria-controls="admin-navigation-sheet" aria-expanded={navigationOpen} aria-label="打开导航" className="h-10 rounded-md border px-3" onClick={() => setNavigationOpen(true)} ref={navigationTrigger} type="button">导航</button> : null}<h1 className="text-xl font-semibold">{title}</h1></div><div className="relative"><button aria-expanded={sessionOpen} aria-haspopup="menu" aria-label="打开会话菜单" className="h-10 rounded-md border px-3" onClick={() => setSessionOpen((open) => !open)} type="button">会话</button>{sessionOpen ? <div className="absolute right-0 z-20 mt-2 min-w-36 rounded-md border bg-card p-1 shadow" role="menu"><button className="w-full rounded px-3 py-2 text-left text-sm hover:bg-muted" onClick={() => void logout()} role="menuitem" type="button">退出登录</button></div> : null}</div></header>
      {kind === 'mobile' ? <section className="border-b bg-muted px-4 py-3 text-sm" aria-label="窄屏后台说明">请在至少 768px 宽度的设备上使用完整后台导航。你仍可安全退出当前会话。</section> : null}
      {kind === 'sheet' && navigationOpen ? <div className="fixed inset-0 z-50 bg-foreground/20" onMouseDown={() => { setNavigationOpen(false); navigationTrigger.current?.focus() }}><aside aria-label="后台导航" aria-modal="true" className="h-full w-[min(20rem,85vw)] border-r bg-card p-4 shadow-xl" id="admin-navigation-sheet" onMouseDown={(event) => event.stopPropagation()} role="dialog" tabIndex={-1}><div className="mb-6 flex items-center justify-between"><p className="font-semibold">后台导航</p><button aria-label="关闭导航" className="h-10 rounded-md border px-3" onClick={() => { setNavigationOpen(false); navigationTrigger.current?.focus() }} type="button">关闭</button></div><Navigation onNavigate={() => setNavigationOpen(false)} /></aside></div> : null}
      <main id="admin-main" ref={mainRef} tabIndex={-1} className="min-w-0">{children ?? <Outlet />}</main>
    </div>
  </div>
}
