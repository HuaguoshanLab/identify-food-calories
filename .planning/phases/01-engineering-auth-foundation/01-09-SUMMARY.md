---
phase: 01-engineering-auth-foundation
plan: 09
subsystem: frontend-auth
tags: [react, react-router, tanstack-query, react-hook-form, zod, vite, vitest, accessibility]

requires:
  - phase: 01-engineering-auth-foundation/01-08
    provides: official shadcn/Base UI primitives, shared styling tokens, and frontend quality gates
provides:
  - Public mobile-first landing, legal, login, registration, verification, and recovery-shell routes
  - Server-backed registration verification with masked context, ASCII code validation, resend cooldown, and error recovery
  - Tested user-H5 boundary that excludes all admin routes, navigation, and probes
affects: [01-10, 01-11, 01-13, frontend-auth, authentication-ui]

tech-stack:
  added: []
  patterns: [React Router route boundary, React Hook Form plus Zod input contracts, controlled FastAPI auth adapter, error-code-to-copy mapping]

key-files:
  created: [frontend/src/auth/README.md, frontend/src/auth/PublicPages.tsx, frontend/src/auth/api.ts, frontend/src/auth/schemas.ts, frontend/src/auth/LoginPage.tsx, frontend/src/auth/RegisterPage.tsx, frontend/src/auth/RegisterVerifyPage.tsx, frontend/src/auth/ForgotPasswordPage.tsx, frontend/src/auth/ResetPasswordPage.tsx, frontend/src/auth/AuthForms.test.tsx, frontend/src/auth/PublicRoutes.test.tsx]
  modified: [frontend/README.md, frontend/src/README.md, frontend/src/App.tsx, frontend/src/App.test.tsx]

key-decisions:
  - "用户 H5 只声明公开认证入口与受保护 /app 入口；不创建 admin-frontend、/admin 路由、后台导航或 probe 调用。"
  - "注册验证码上下文只从 HttpOnly Cookie 对应的服务器接口读取 masked_email；邮箱、验证码和密码不进入 URL 或浏览器持久化。"
  - "后端密码恢复 API 尚由 01-13 交付，01-09 只保留安全表单壳和恢复入口，拒绝伪造不存在的网络合约。"

patterns-established:
  - "认证表单使用 React Hook Form + Zod，提交 payload 显式投影，确认密码和 role 不会越过 API 边界。"
  - "验证码为单输入框、6 位 ASCII 数字；重发清码并移回焦点，稳定 error.code 决定可恢复文案。"

requirements-completed: [AUTH-01, AUTH-02, AUTH-06, ARC-01, ARC-07]

duration: 15 min
completed: 2026-08-27
---

# Phase 1 Plan 9: 公开认证表单与路由边界 Summary

**React Router 公开认证流程已交付：用户可进入 landing、法律页、登录、注册和服务器驱动的 6 位邮箱验证，且用户 H5 被测试锁定为无后台表面。**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-27T08:53:00Z
- **Completed:** 2026-08-27T09:07:49Z
- **Tasks:** 2/2
- **Files modified:** 15

## Accomplishments

- 建立 `/`、`/login`、`/register`、`/register/verify`、`/forgot-password`、`/reset-password`、`/privacy`、`/terms` 与受保护 `/app` 入口；全部公开页面使用 UI-SPEC 的移动优先视觉和精确核心文案。
- 注册表单只提交 email/password；验证码页从服务器 pending context 获取掩码邮箱，限制单个 6 位 ASCII code，并覆盖过期、尝试耗尽、context 失效、网络失败与重发冷却。
- Vitest 证明用户 SPA 无 `/admin` 路由、后台导航和 probe 调用；源码也不使用 localStorage、sessionStorage、IndexedDB 或 Mailpit 产品动作。

## Task Commits

1. **Task 1 RED: 建立公开路由与安全路由表** - `c020324` (test)
2. **Task 1 GREEN: 建立公开路由与安全路由表** - `94d60d8` (feat)
3. **Task 2 RED: 实现登录、注册验证与密码恢复表单状态** - `2140cc1` (test)
4. **Task 2 regression correction: 对齐落地页 h1 测试** - `01e6540` (test)
5. **Task 2 GREEN: 实现登录、注册验证与密码恢复表单状态** - `40d4a2c` (feat)

## Files Created/Modified

- `frontend/src/App.tsx` - 用户 H5 的真实 React Router 表，受保护 `/app` 入口跳转登录，绝无后台路由。
- `frontend/src/auth/PublicPages.tsx` - landing、隐私、条款与可聚焦的公开页面布局。
- `frontend/src/auth/api.ts` / `schemas.ts` - 受控 FastAPI 注册、验证和登录适配器，以及运行时表单契约。
- `frontend/src/auth/LoginPage.tsx`, `RegisterPage.tsx`, `RegisterVerifyPage.tsx` - 可访问的认证表单、非枚举 payload、验证码和错误恢复。
- `frontend/src/auth/AuthForms.test.tsx`, `PublicRoutes.test.tsx` - 路由、表单、payload、焦点、重发、错误码和后台缺席证据。
- `frontend/src/auth/ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx` - 等待后端恢复 API 的安全公开入口壳。
- `frontend/README.md`, `frontend/src/README.md`, `frontend/src/auth/README.md` - 同步目录职责、允许依赖和完整索引。

## Decisions Made

- 不伪造 `/auth/forgot` 或 reset API。后端恢复合约由 01-13 交付，提前发送请求只会制造不可验证的死接口。
- 登录响应中的 access token 只停留在 API adapter 调用栈，当前阶段不写任何浏览器持久化；01-11 将以 AuthProvider 建立内存 token 与安全 `returnTo` 生命周期。
- 用户端不承担 RBAC：它只不注册后台表面，实际 admin 探针和 RBAC 留在后端及 Phase 6 独立后台。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression] 修正旧运行壳对 landing 标题层级的错误断言**
- **Found during:** Task 2（全量 Vitest）
- **Issue:** 旧 `App.test.tsx` 把产品名当作 `<h1>`；新 UI-SPEC 要求产品价值标题才是页面主标题，导致全量测试错误失败。
- **Fix:** 改为断言精确 landing value heading，产品名保留为支持性标签。
- **Files modified:** `frontend/src/App.test.tsx`
- **Verification:** 全量 Vitest 5 files / 15 tests passed。
- **Committed in:** `01e6540`

**2. [Rule 1 - Focus bug] 修复 React Hook Form ref 覆盖验证码输入焦点**
- **Found during:** Task 2（重发验证码焦点测试）
- **Issue:** RHF 的 register ref 覆盖了组件 ref，重发成功后焦点仍留在已禁用的重发按钮。
- **Fix:** 改用 RHF `setFocus('code')`，重发后清空旧码并把焦点移回验证码输入；失效码同样支持选中重输。
- **Files modified:** `frontend/src/auth/RegisterVerifyPage.tsx`, `frontend/src/auth/AuthForms.test.tsx`
- **Verification:** 验证码重发、焦点、冷却与错误映射 7 tests passed。
- **Committed in:** `40d4a2c`

---

**Total deviations:** 2 auto-fixed（2 Rule 1）。
**Impact on plan:** 两项修复只恢复 UI-SPEC 标题语义和验证码键盘可用性；没有扩展产品范围。

## Issues Encountered

- Context7 MCP 与 CLI 均不可用，因此没有外部库文档可查询；实现仅使用已锁定版本中已有的 React Router、React Hook Form、Zod 与 TanStack Query API，并由 typecheck、lint 和 Vitest 验证。
- 后端目前没有密码恢复 API。为避免凭空声明网络端点，恢复流程明确停在可操作的公开 shell，等待 01-13 的真实合约。

## Authentication Gates

None.

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| 忘记密码提交只显示安全的服务不可用错误 | `frontend/src/auth/ForgotPasswordPage.tsx:13` | 真实恢复 API、pending context 和原子 session revoke 属于 01-13；本计划不得伪造端点。 |
| 重置密码路由只显示 context-invalid 恢复入口 | `frontend/src/auth/ResetPasswordPage.tsx:5` | 尚无服务器恢复 context，不能从 URL 或浏览器存储重建敏感流程；01-13 会接通。 |

## Threat Flags

None. 本计划只调用既有公开注册/验证/登录端点；没有增加新网络端点、auth trust boundary、文件访问或 schema 变更。

## Verification Evidence

- `npm run test -- PublicRoutes.test.tsx AuthForms.test.tsx` → 2 files / 10 tests passed。
- `npm run test` → 5 files / 15 tests passed，无 skipped tests。
- `npm run typecheck` → passed。
- `npm run lint` → passed。
- `npm run build` → Vite production build passed，159 modules transformed。
- `rg` admin/storage/Mailpit 扫描 → 仅 `auth/README.md` 记录禁止规则，无生产实现命中。
- `git diff --check` → passed。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 01-10 可补齐 refresh/logout/session 后端协议；01-11 可在现有路由和 API adapter 上接入 AuthProvider、数据库权威 `/users/me`、安全 `returnTo` 与会话 UI。
- 01-13 必须替换已跟踪的恢复 shells，接通真实密码恢复 API、masked pending context 与验证码消费协议。

## Self-Check: PASSED

- 计划指定的 11 个认证源文件/测试文件及三个目录 README 均存在。
- `c020324`、`94d60d8`、`2140cc1`、`01e6540`、`40d4a2c` 均可从 Git 历史解析。
- lint、typecheck、全量 Vitest、production build、admin/storage/Mailpit 扫描与 diff 检查全部通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
