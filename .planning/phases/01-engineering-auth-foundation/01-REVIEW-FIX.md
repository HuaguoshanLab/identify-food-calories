---
phase: 01-engineering-auth-foundation
fixed_at: 2026-08-27T11:03:35Z
review_path: .planning/phases/01-engineering-auth-foundation/01-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-08-27T11:03:35Z  
**Source review:** `.planning/phases/01-engineering-auth-foundation/01-REVIEW.md`  
**Iteration:** 1

**Summary:**

- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: 生产构建固定请求用户本机的 API

**Files modified:** `frontend/src/auth/api.ts`, `frontend/vite.config.ts`, `frontend/package.json`, `frontend/src/auth/AuthSession.test.tsx`, `frontend/README.md`, `frontend/src/auth/README.md`  
**Commit:** b936b81  
**Applied fix:** 浏览器默认改为同源 `/api/v1`；显式外部地址在生产构建和运行时都要求 HTTPS；Vite dev/preview 仅在服务器侧代理本地 API，并新增 bundle 不含回环 API 地址的断言。

### CR-02: 多标签页正常启动会触发 refresh 重放并撤销整个会话

**Files modified:** `frontend/src/auth/AuthProvider.tsx`, `frontend/src/auth/refreshCoordinator.ts`, `frontend/src/auth/AuthSession.test.tsx`, `frontend/src/auth/refreshCoordinator.test.ts`, `frontend/src/auth/README.md`  
**Commit:** a88a81b  
**Status:** fixed: requires human verification  
**Applied fix:** 页面内共享 refresh flight，跨同源标签页使用 Web Locks 串行化 HttpOnly refresh Cookie 的轮换；服务端真实 token replay 的 family revoke 未被放宽。测试覆盖独立 Provider 同时 bootstrap 与隔离标签页运行时的锁串行化。

### WR-01: 注册 context 的 Cookie 写端点绕过了已有的精确 Origin 校验

**Files modified:** `backend/app/auth/api.py`, `backend/tests/auth/test_registration_verification.py`  
**Commit:** a89db0f  
**Applied fix:** `/register/verify` 与 `/register/resend` 在读取或变更 registration context 前复用精确 Origin/Referer 校验；测试覆盖缺失来源、伪造 Referer 与合法 Origin，并保持真实 PostgreSQL/Mailpit 注册流程通过。

---

_Fixed: 2026-08-27T11:03:35Z_  
_Fixer: the agent (gsd-code-fixer)_  
_Iteration: 1_
