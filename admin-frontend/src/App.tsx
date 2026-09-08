import { Link, Navigate, Route, Routes } from 'react-router-dom'

import { AdminLoginPage } from './auth/AdminLoginPage'
import { AdminRouteGuard } from './auth/AdminRouteGuard'
import { AdminAuditPage } from './features/audit/AuditPage'
import { AdminCatalogListPage } from './features/catalog/CatalogListPage'
import { AdminCatalogLifecyclePage } from './features/catalog/CatalogLifecyclePage'
import { AdminRuntimeConfigSummaryPage } from './features/config/ConfigSummaryPage'
import { AdminOverviewRoute } from './features/overview/AdminOverviewPage'
import { AdminRunsPage } from './features/runs/RunsPage'
import { RecipeListPage } from './features/recipes/RecipeListPage'
import { AdminShell } from './layouts/AdminShell'

function ForbiddenPage() { return <main className="admin-runtime-root mx-auto max-w-2xl" aria-labelledby="admin-forbidden-title"><h1 className="text-[28px] font-semibold" id="admin-forbidden-title">无后台访问权限</h1><p className="mt-4">你的当前账号没有管理权限。请使用管理员账号登录。</p><div className="mt-6 flex gap-3"><Link className="rounded-md border px-4 py-2" to="/admin/login">重新登录</Link><a className="rounded-md border px-4 py-2" href="/app">返回用户端</a></div></main> }

/**
 * 此处只保留后台路由装配边界，避免在启动层混入领域请求或用户 H5 路由。
 * 页面各自在 feature API 层完成严格 DTO 校验；guard 只改善 UX，不能取代 DB RBAC。
 */
export function App() {
  return (
    <Routes>
      <Route path="/admin/login" element={<AdminLoginPage />} />
      <Route path="/admin/forbidden" element={<ForbiddenPage />} />
      <Route element={<AdminRouteGuard><AdminShell /></AdminRouteGuard>}>
        <Route path="/admin/overview" element={<AdminOverviewRoute />} />
        <Route path="/admin/catalog" element={<AdminCatalogListPage />} />
        <Route path="/admin/recipes" element={<RecipeListPage />} />
        <Route path="/admin/catalog/:draftId/lifecycle" element={<AdminCatalogLifecyclePage />} />
        <Route path="/admin/runs" element={<AdminRunsPage />} />
        <Route path="/admin/model-configs" element={<AdminRuntimeConfigSummaryPage />} />
        <Route path="/admin/audit" element={<AdminAuditPage />} />
      </Route>
      <Route path="*" element={<Navigate replace to="/admin/overview" />} />
    </Routes>
  )
}
