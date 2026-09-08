import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { adminRouteMeta } from './adminNavigation'

type OpenTab = Readonly<{ label: string, path: string }>

const overviewTab: OpenTab = { label: '运行概览', path: '/admin/overview' }

export function AdminTabs() {
  const location = useLocation()
  const navigate = useNavigate()
  const currentPath = `${location.pathname}${location.search}`
  const [tabs, setTabs] = useState<OpenTab[]>(() => currentPath === overviewTab.path ? [overviewTab] : [overviewTab, { label: adminRouteMeta(location.pathname).label, path: currentPath }])

  useEffect(() => {
    setTabs((openTabs) => openTabs.some(({ path }) => path === currentPath)
      ? openTabs
      : [...openTabs, { label: adminRouteMeta(location.pathname).label, path: currentPath }])
  }, [currentPath, location.pathname])

  function closeTab(path: string) {
    const index = tabs.findIndex((tab) => tab.path === path)
    const nextTabs = tabs.filter((tab) => tab.path !== path)
    setTabs(nextTabs)
    if (path === currentPath) {
      const fallback = nextTabs[Math.max(0, index - 1)] ?? overviewTab
      void navigate(fallback.path)
    }
  }

  return <div aria-label="已打开页面" className="flex h-11 items-end gap-1 overflow-x-auto border-b bg-slate-50 px-3 pt-2 sm:px-5" role="tablist">
    {tabs.map((tab) => {
      const active = tab.path === currentPath
      return <div className={`group flex h-9 shrink-0 items-center rounded-t-lg border border-b-0 transition-colors ${active ? 'border-slate-200 bg-white text-slate-900' : 'border-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-800'}`} key={tab.path}>
        <Link aria-selected={active} className="flex h-full cursor-pointer items-center pl-3 text-sm font-medium" role="tab" to={tab.path}>{tab.label}</Link>
        {tab.path !== overviewTab.path ? <button aria-label={`关闭${tab.label}`} className="mx-1 grid size-7 cursor-pointer place-items-center rounded-md text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-800" onClick={() => closeTab(tab.path)} type="button"><X aria-hidden="true" size={14} /></button> : <span className="w-3" />}
      </div>
    })}
  </div>
}
