import { Navigate, Route, Routes } from 'react-router-dom'

import { AdminRouteGuard } from './auth/AdminRouteGuard'
import { AdminRuntimeConfigSummaryPage } from './features/config/ConfigSummaryPage'

function AdminRuntimeRoot() {
  return (
    <main className="admin-runtime-root" aria-label="管理后台">
      <h1>管理后台</h1>
    </main>
  )
}

/**
 * 此处只保留后台路由装配边界，避免在启动层混入领域请求或用户 H5 路由。
 * 受保护的真实页面由后续计划在同一独立路由树中注册。
 */
export function App() {
  return (
    <Routes>
      <Route path="/admin/login" element={<AdminRuntimeRoot />} />
      <Route path="/admin/forbidden" element={<main className="admin-runtime-root"><h1>无后台访问权限</h1></main>} />
      <Route path="/admin/model-configs" element={<AdminRouteGuard><AdminRuntimeConfigSummaryPage /></AdminRouteGuard>} />
      <Route path="*" element={<Navigate replace to="/admin/model-configs" />} />
    </Routes>
  )
}
