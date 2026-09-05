# 管理员认证运行时

## 职责

此目录保存管理员身份恢复、登录、探测、登出和路由体验所需的浏览器认证代码。它只改善体验，不能替代后端按 PostgreSQL 当前角色执行的 RBAC。

## 允许依赖

- 允许依赖 React、TanStack Query 和公开 `/api/v1/admin/*` HTTP 合约。
- 后续功能只能通过此目录明确导出的认证接口取得瞬时请求凭据。
- 禁止依赖用户 H5、后端源码、数据库客户端、密钥或任何浏览器持久化身份容器。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `AdminAuthProvider.tsx` | 启动恢复 HttpOnly 会话，access token 仅在内存；epoch 阻止迟到恢复覆盖登录或退出，身份变化清空缓存。 |
| `AdminRouteGuard.tsx` | 等待恢复，再以当前 token 调用后台 probe；401/403 清空会话与缓存，未验证的 token 不渲染私有页。 |
| `AdminLoginPage.tsx` | 受 label/运行时 schema 保护的公开登录页；仅建立内存会话，随后由 probe 确认后台访问。 |
| `session.ts` | 严格认证 DTO、refresh → users/me 恢复、页面内 single-flight 与同源 Web Locks 串行轮换；请求限时，不自动重试。 |
| `AdminSessionRestore.test.tsx` | StrictMode/慢恢复保留原路径、无凭据回登录、普通角色拒绝与清空后的迟到响应。 |

刷新页面时先调用公开 `/api/v1/auth/refresh`（浏览器自动携带 HttpOnly Cookie），再调用 `/api/v1/users/me` 建立身份，最终由 `/api/v1/admin/probe` 校验后台权限。Cookie 缺失、失效或恢复失败时回到带 returnTo 的登录页。Shell 保留已有服务端 logout，不仅清空本地内存。

Web Locks 仅协调同源后台标签；本地5178/5179不同源不共享锁，而Cookie不按端口隔离。不同端口同时登录不同账号或同时轮换仍属于既有跨应用Cookie隔离限制，本次没有修改后端Cookie策略。也未扩展为所有业务请求的401自动重试。
