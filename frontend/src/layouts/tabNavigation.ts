import { CalendarDays, NotebookText, ScanLine, UserRound } from 'lucide-react'

import { routePaths } from '@/routePaths'

/** 页头和导航共享路由配置，避免名称与选中状态各自漂移。 */
export const tabNavigation = [
  { icon: ScanLine, label: '分析', title: '分析这餐', to: routePaths.analyze },
  { icon: NotebookText, label: '记录', title: '饮食记录', to: routePaths.records },
  { icon: CalendarDays, label: '计划', title: '饮食计划', to: routePaths.plans },
  { icon: UserRound, label: '我的', title: '我的', to: routePaths.me },
] as const
