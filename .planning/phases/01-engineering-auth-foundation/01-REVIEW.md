---
phase: 01-engineering-auth-foundation
reviewed: 2026-08-27T10:52:32Z
depth: standard
files_reviewed: 99
files_reviewed_list:
  - backend/alembic.ini
  - backend/app/__init__.py
  - backend/app/accounts/__init__.py
  - backend/app/accounts/api.py
  - backend/app/accounts/ports.py
  - backend/app/accounts/repository.py
  - backend/app/accounts/schemas.py
  - backend/app/accounts/service.py
  - backend/app/admin/__init__.py
  - backend/app/admin/api.py
  - backend/app/admin/cli.py
  - backend/app/admin/models.py
  - backend/app/admin/ports.py
  - backend/app/admin/repository.py
  - backend/app/admin/schemas.py
  - backend/app/admin/service.py
  - backend/app/auth/__init__.py
  - backend/app/auth/api.py
  - backend/app/auth/models.py
  - backend/app/auth/ports.py
  - backend/app/auth/repository.py
  - backend/app/auth/schemas.py
  - backend/app/auth/security.py
  - backend/app/auth/service.py
  - backend/app/core/__init__.py
  - backend/app/core/config.py
  - backend/app/core/database.py
  - backend/app/main.py
  - backend/app/notifications/__init__.py
  - backend/app/notifications/ports.py
  - backend/app/notifications/smtp.py
  - backend/migrations/env.py
  - backend/migrations/script.py.mako
  - backend/migrations/versions/0001_auth_foundation.py
  - backend/migrations/versions/0002_login_attempts.py
  - backend/migrations/versions/0003_admin_audit.py
  - backend/pyproject.toml
  - backend/tests/accounts/test_account_recovery.py
  - backend/tests/architecture/test_directory_contract.py
  - backend/tests/auth/test_login_me_api.py
  - backend/tests/auth/test_login_me_service.py
  - backend/tests/auth/test_login_rate_limit_service.py
  - backend/tests/auth/test_phase1_security_contract.py
  - backend/tests/auth/test_refresh_api.py
  - backend/tests/auth/test_refresh_service.py
  - backend/tests/auth/test_registration_verification.py
  - backend/tests/conftest.py
  - backend/tests/integration/test_admin_audit.py
  - backend/tests/integration/test_auth_database_protocols.py
  - backend/tests/integration/test_auth_migration.py
  - backend/tests/integration/test_refresh_concurrency.py
  - backend/tests/unit/test_runtime_foundation.py
  - backend/tests/unit/test_test_database_guards.py
  - docker-compose.yml
  - frontend/components.json
  - frontend/eslint.config.js
  - frontend/index.html
  - frontend/package.json
  - frontend/playwright.config.ts
  - frontend/src/App.test.tsx
  - frontend/src/App.tsx
  - frontend/src/auth/AuthContext.ts
  - frontend/src/auth/AuthForms.test.tsx
  - frontend/src/auth/AuthProvider.tsx
  - frontend/src/auth/AuthSession.test.tsx
  - frontend/src/auth/ForgotPasswordPage.tsx
  - frontend/src/auth/LoginPage.tsx
  - frontend/src/auth/ProtectedRoutes.test.tsx
  - frontend/src/auth/PublicPages.tsx
  - frontend/src/auth/PublicRoutes.test.tsx
  - frontend/src/auth/RegisterPage.tsx
  - frontend/src/auth/RegisterVerifyPage.tsx
  - frontend/src/auth/ResetPasswordPage.tsx
  - frontend/src/auth/RevokeSessionDialog.tsx
  - frontend/src/auth/RouteGuards.tsx
  - frontend/src/auth/SessionList.tsx
  - frontend/src/auth/api.ts
  - frontend/src/auth/returnTo.ts
  - frontend/src/auth/schemas.ts
  - frontend/src/auth/useAuth.ts
  - frontend/src/components/ui/alert-dialog.tsx
  - frontend/src/components/ui/alert.tsx
  - frontend/src/components/ui/badge.tsx
  - frontend/src/components/ui/button.tsx
  - frontend/src/components/ui/card.tsx
  - frontend/src/components/ui/components.test.tsx
  - frontend/src/components/ui/input.tsx
  - frontend/src/components/ui/label.tsx
  - frontend/src/components/ui/separator.tsx
  - frontend/src/components/ui/skeleton.tsx
  - frontend/src/components/ui/utils.test.ts
  - frontend/src/components/ui/utils.ts
  - frontend/src/main.tsx
  - frontend/src/styles.css
  - frontend/src/test-setup.ts
  - frontend/tests/e2e/auth-skeleton.spec.ts
  - frontend/tests/e2e/health.spec.ts
  - frontend/tsconfig.json
  - frontend/vite.config.ts
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-08-27T10:52:32Z  
**Depth:** standard  
**Files Reviewed:** 99  
**Status:** issues_found

## Summary

认证、刷新轮换、密码恢复、数据库权威 RBAC、前端路由和测试基础设施均已逐文件审查。服务端的 JWT 结构校验、数据库角色回读、refresh 行锁、密码恢复事务和 admin 审计方向是对的，但发布与会话边界仍有两个不能上线的问题：生产 SPA 只能请求用户自己的 `127.0.0.1`，而同一浏览器的多个标签会把正常 refresh 竞争当成令牌盗用，撤销整个会话家族。

## Blockers

### CR-01: 生产构建固定请求用户本机的 API

**Classification:** BLOCKER  
**File:** `frontend/src/auth/api.ts:1`  
**Issue:** `apiBaseUrl` 被硬编码为 `http://127.0.0.1:8000/api/v1`。Vite 会把该常量编译进产物；用户访问任何 HTTPS/生产域名时，认证、恢复、refresh 和会话 API 都会发往“该用户自己的回环地址”，而不是部署的后端。生产 CORS、Secure Cookie 与后端的 fail-closed 配置因此完全无法让 SPA 工作。

**Fix:** 将 API 基址改为构建时显式注入的 `VITE_API_BASE_URL`（或由同源反向代理提供的相对 `/api/v1`），并在启动/构建时拒绝缺失或非 HTTPS 的生产值；为生产构建增加一个断言，确认 bundle 不含 `127.0.0.1:8000`。

```ts
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export function apiUrl(path: string) {
  return new URL(path, `${apiBaseUrl.replace(/\/$/, '')}/`).toString()
}
```

### CR-02: 多标签页正常启动会触发 refresh 重放并撤销整个会话

**Files:** `frontend/src/auth/AuthProvider.tsx:54-84`; `backend/app/auth/service.py:206-228`  
**Classification:** BLOCKER  
**Issue:** 每个 `AuthProvider` 挂载都会自动调用 `/auth/refresh`，但 `refreshFlight` 只存在于单个 React Provider。两个同源标签页（或 StrictMode 开发期的重复挂载）可同时携带同一个共享 HttpOnly refresh cookie；一个请求轮换成功后，另一个请求看到已消费 token，后端按 221-228 行撤销整个 session family。结果是正常打开/刷新两个标签页把用户所有该设备会话踢下线。这不是攻击重放，而是客户端未协调造成的必现自我拒绝服务。

**Fix:** 在同源标签页之间协调 refresh，而不是只在单个 Provider 内单飞。可用 `BroadcastChannel`/SharedWorker 传递仅驻留内存的新的 access token，并以 `navigator.locks` 或等价跨标签锁确保只有一个 tab 发起轮换；补充两个独立 Provider/浏览器 tab 同时 bootstrap 的集成测试。不要通过放宽后端对真实 refresh 重放的 family revoke 来掩盖客户端竞争。

```ts
// 伪代码：锁和结果必须跨 tab，而非 useRef。
await navigator.locks.request('food-agent-refresh', async () => {
  // leader refreshes once, then BroadcastChannel posts the runtime-only access token.
  // followers wait for that event instead of submitting the stale shared cookie.
})
```

## Warnings

### WR-01: 注册 context 的 Cookie 写端点绕过了已有的精确 Origin 校验

**Classification:** WARNING  
**File:** `backend/app/auth/api.py:124-208`  
**Issue:** `/register/verify` 会消费 challenge 并删除 HttpOnly context cookie，`/register/resend` 会使旧 challenge 失效、发送邮件并写入新 cookie，但两个端点没有调用 `_request_origin_is_allowed`。同一模块的 refresh/logout/session mutation 和 accounts recovery mutation 都实行精确 Origin/Referer 检查。`SameSite=strict` 只能覆盖跨站，不覆盖同站的恶意 sibling origin；其中无请求体的 `resend` 可被同站 HTML form POST 调用，导致攻击者反复作废用户刚收到的验证码并触发邮件发送。

**Fix:** 在这两个路由读取或修改 registration context 前复用 `_request_origin_is_allowed` 并返回统一 `CSRF_ORIGIN_INVALID`，同时添加缺失 Origin、伪造 Referer、合法 Origin 的 API 合约测试。

```python
if not _request_origin_is_allowed(request):
    return _error(
        status_code=status.HTTP_403_FORBIDDEN,
        code="CSRF_ORIGIN_INVALID",
        message="请求来源无效。",
    )
```

---

_Reviewed: 2026-08-27T10:52:32Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
