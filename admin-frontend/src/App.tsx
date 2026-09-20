import { lazy, Suspense } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'

import { AdminLoginPage } from './auth/AdminLoginPage'
import { AdminRouteGuard } from './auth/AdminRouteGuard'
import { AdminShell } from './layouts/AdminShell'

const AdminAuditPage = lazy(() => import('./features/audit/AuditPage').then((module) => ({ default: module.AdminAuditPage })))
const AdminCatalogListPage = lazy(() => import('./features/catalog/CatalogListPage').then((module) => ({ default: module.AdminCatalogListPage })))
const AdminCatalogLifecyclePage = lazy(() => import('./features/catalog/CatalogLifecyclePage').then((module) => ({ default: module.AdminCatalogLifecyclePage })))
const AdminRuntimeConfigSummaryPage = lazy(() => import('./features/config/ConfigSummaryPage').then((module) => ({ default: module.AdminRuntimeConfigSummaryPage })))
const AdminOverviewRoute = lazy(() => import('./features/overview/AdminOverviewPage').then((module) => ({ default: module.AdminOverviewRoute })))
const AdminRunsPage = lazy(() => import('./features/runs/RunsPage').then((module) => ({ default: module.AdminRunsPage })))
const AdminRolesPage = lazy(() => import('./features/system/RolesPage').then((module) => ({ default: module.AdminRolesPage })))
const AdminUsersPage = lazy(() => import('./features/system/UsersPage').then((module) => ({ default: module.AdminUsersPage })))
const RecipeListPage = lazy(() => import('./features/recipes/RecipeListPage').then((module) => ({ default: module.RecipeListPage })))
const VectorRetrievalPage = lazy(() => import('./features/vector-retrieval/VectorRetrievalPage').then((module) => ({ default: module.VectorRetrievalPage })))

function ForbiddenPage() { return <main className="admin-runtime-root mx-auto max-w-2xl" aria-labelledby="admin-forbidden-title"><h1 className="text-[28px] font-semibold" id="admin-forbidden-title">无后台访问权限</h1><p className="mt-4">你的当前账号没有管理权限。请使用管理员账号登录。</p><div className="mt-6 flex gap-3"><Link className="rounded-md border px-4 py-2" to="/admin/login">重新登录</Link><a className="rounded-md border px-4 py-2" href="/app">返回用户端</a></div></main> }

/**
 * 此处只保留后台路由装配边界，避免在启动层混入领域请求或用户 H5 路由。
 * 页面各自在 feature API 层完成严格 DTO 校验；guard 只改善 UX，不能取代 DB RBAC。
 */
export function App() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-muted-foreground" role="status">正在加载后台页面…</p>}>
    <Routes>
      <Route path="/admin/login" element={<AdminLoginPage />} />
      <Route path="/admin/forbidden" element={<ForbiddenPage />} />
      <Route element={<AdminRouteGuard><AdminShell /></AdminRouteGuard>}>
        <Route path="/admin/overview" element={<AdminOverviewRoute />} />
        <Route path="/admin/catalog" element={<AdminCatalogListPage />} />
        <Route path="/admin/recipes" element={<RecipeListPage />} />
        <Route path="/admin/vector-retrieval" element={<VectorRetrievalPage />} />
        <Route path="/admin/catalog/:draftId/lifecycle" element={<AdminCatalogLifecyclePage />} />
        <Route path="/admin/runs" element={<AdminRunsPage />} />
        <Route path="/admin/model-configs" element={<AdminRuntimeConfigSummaryPage />} />
        <Route path="/admin/audit" element={<AdminAuditPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/roles" element={<AdminRolesPage />} />
      </Route>
      <Route path="*" element={<Navigate replace to="/admin/overview" />} />
    </Routes>
    </Suspense>
  )
}
