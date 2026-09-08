import type { LucideIcon } from 'lucide-react'
import { BookOpen, ClipboardList, Gauge, History, Salad, Settings2, ShieldCheck, Users } from 'lucide-react'

export type AdminNavigationItem = Readonly<{
  icon: LucideIcon
  label: string
  to: string
}>

export type AdminNavigationGroup = Readonly<{
  id: string
  label?: string
  items: readonly AdminNavigationItem[]
}>

export const adminNavigation: readonly AdminNavigationGroup[] = [
  {
    id: 'system-management',
    label: '系统管理',
    items: [
      { icon: Users, label: '管理员管理', to: '/admin/users' },
      { icon: ShieldCheck, label: '角色管理', to: '/admin/roles' },
    ],
  },
  {
    id: 'workspace',
    items: [{ icon: Gauge, label: '运行概览', to: '/admin/overview' }],
  },
  {
    id: 'content',
    label: '内容管理',
    items: [
      { icon: Salad, label: '营养目录', to: '/admin/catalog' },
      { icon: BookOpen, label: '菜谱管理', to: '/admin/recipes' },
    ],
  },
  {
    id: 'operations',
    label: '系统运行',
    items: [
      { icon: ClipboardList, label: '运行审计', to: '/admin/runs' },
      { icon: Settings2, label: '模型配置', to: '/admin/model-configs' },
      { icon: History, label: '操作审计', to: '/admin/audit' },
    ],
  },
] as const

const allNavigationItems = adminNavigation.flatMap((group) => group.items)

export function adminRouteMeta(pathname: string) {
  if (pathname.startsWith('/admin/catalog/') && pathname.endsWith('/lifecycle')) {
    return {
      breadcrumbs: ['内容管理', '营养目录', '审核与发布'],
      label: '目录审核与发布',
    }
  }

  const item = allNavigationItems.find(({ to }) => pathname === to)
  const group = adminNavigation.find(({ items }) => items.some(({ to }) => to === item?.to))

  return {
    breadcrumbs: [...(group?.label ? [group.label] : []), item?.label ?? '管理后台'],
    label: item?.label ?? '管理后台',
  }
}
