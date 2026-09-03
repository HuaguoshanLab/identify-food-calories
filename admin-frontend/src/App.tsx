import { Navigate, Route, Routes } from 'react-router-dom'

import { AdminRouteGuard } from './auth/AdminRouteGuard'
import { AdminAuditPage } from './features/audit/AuditPage'
import { AdminCatalogDraftPage } from './features/catalog/CatalogDraftPage'
import { AdminRuntimeConfigSummaryPage } from './features/config/ConfigSummaryPage'
import { AdminRunsPage } from './features/runs/RunsPage'

function AdminRuntimeRoot() {
  return (
    <main className="admin-runtime-root" aria-label="管理后台">
      <h1>管理后台</h1>
    </main>
  )
}

/**
 * 此处只保留后台路由装配边界，避免在启动层混入领域请求或用户 H5 路由。
 * 页面各自在 feature API 层完成严格 DTO 校验；guard 只改善 UX，不能取代 DB RBAC。
 */
export function App() {
  return (
    <Routes>
      <Route path="/admin/login" element={<AdminRuntimeRoot />} />
      <Route path="/admin/forbidden" element={<main className="admin-runtime-root"><h1>无后台访问权限</h1></main>} />
      <Route path="/admin/catalog" element={<AdminRouteGuard><AdminCatalogDraftPage /></AdminRouteGuard>} />
      <Route path="/admin/runs" element={<AdminRouteGuard><AdminRunsPage /></AdminRouteGuard>} />
      <Route path="/admin/model-configs" element={<AdminRouteGuard><AdminRuntimeConfigSummaryPage /></AdminRouteGuard>} />
      <Route path="/admin/audit" element={<AdminRouteGuard><AdminAuditPage /></AdminRouteGuard>} />
      <Route path="*" element={<Navigate replace to="/admin/model-configs" />} />
    </Routes>
  )
}
