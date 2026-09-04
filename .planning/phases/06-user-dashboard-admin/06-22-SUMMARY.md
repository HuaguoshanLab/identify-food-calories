---
phase: 06-user-dashboard-admin
plan: 22
subsystem: admin-frontend
tags: [react, typescript, zod, tanstack-query, msw, vitest, accessibility, rbac]
requires:
  - phase: 06-17
    provides: 管理员内存 access token、probe guard 与 Query cache 清理
  - phase: 06-18
    provides: DB-RBAC 保护的终态运行 metrics/list projection
  - phase: 06-19
    provides: 严格 runs 页面与 UTC filter HTTP 合约
provides:
  - 公开登录、内存 session、probe guard 与安全 returnTo 的独立后台入口
  - 768px Sheet、1024px 紧凑侧栏、1280px 完整侧栏的可访问 AdminShell
  - server-owned UTC metrics window 的严格 DTO，及直接复用该窗口的 runs 深链接
affects: [06-20, admin-frontend, browser-verification]
tech-stack:
  added: []
  patterns: [memory-only-admin-token, probe-before-shell, strict-overview-dto, utc-deep-link]
key-files:
  created:
    - admin-frontend/src/auth/AdminLoginPage.tsx
    - admin-frontend/src/layouts/AdminShell.tsx
    - admin-frontend/src/features/overview/AdminOverviewPage.tsx
    - admin-frontend/src/features/overview/api.ts
  modified:
    - admin-frontend/src/App.tsx
    - admin-frontend/src/auth/AdminRouteGuard.tsx
    - admin-frontend/src/features/runs/RunsPage.tsx
    - admin-frontend/vite.config.ts
key-decisions:
  - "登录先以严格公开 auth/users DTO 建立内存 token，再由独立 admin probe 确认当前 PostgreSQL 角色；浏览器 role 不作为授权结论。"
  - "metrics service 规范化并回显 UTC window；overview 只复用 response-owned from/to，不重算 percentile、失败率或费用。"
  - "开发代理仅额外公开认证与当前身份路径，以维持 HttpOnly refresh cookie 的同源边界。"
patterns-established:
  - "后台入口：公开登录 → 内存 session → probe guard → AdminShell/Outlet；401/403 立即清空 Query cache。"
  - "后台概览：feature-owned strict Zod API + TanStack Query，所有指标卡使用语义 Link 保留服务端筛选条件。"
requirements-completed: [ADM-01, ADM-03, ARC-08]
duration: 9min
completed: 2026-09-03
---

# Phase 06 Plan 22: 独立后台登录、壳与运行概览 Summary

**独立后台现在通过公开登录和 DB-RBAC probe 进入仅内存会话的可访问 shell，并从严格终态运行投影跳转到同一 UTC 窗口的审计列表。**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-03T12:27:00Z
- **Completed:** 2026-09-03T12:35:46Z
- **Tasks:** 3/3
- **Files modified:** 16

## Accomplishments

- `/admin/login` 以有 label 的邮件/密码表单调用公开 auth/users API；access token 只写入 `AdminAuthProvider` 内存，非 admin 不会发布 session，嵌套路由仍必须经 probe。
- `AdminShell` 提供 skip link、语义 Link 导航、会话菜单和安全登出；768px 为可 Escape 关闭并回焦的 Sheet，1024px 208px 紧凑侧栏，1280px 240px 完整侧栏。
- overview 用严格 Zod + TanStack Query 读取服务端四项终态指标及其明确 UTC `from` / `to`；卡片和审计入口直接带该 response-owned 窗口到 runs，runs 路由可消费该窗口。

## Task Commits

1. **Task 1: 写 admin login、shell 和三断点 RED 测试** — `d866eb0` (`test`)
2. **Task 2: 接线登录路由、AdminShell 与会话菜单** — `3be56e3` (`feat`)
3. **Task 3: 实现 overview 运行指标与 runs 深链接** — `1a4617c` (`feat`)
4. **Rule 3 corrective fix: 代理公开登录 API** — `e3d502d` (`fix`)
5. **用户授权的最小后端扩展：metrics UTC window** — `b8ac995` (`feat`)

## Files Created/Modified

- `admin-frontend/src/auth/AdminLoginPage.tsx` — 严格公开登录、当前身份读取和安全 `returnTo`。
- `admin-frontend/src/auth/AdminRouteGuard.tsx` — 保留受限 admin return path，继续由 server probe 决定 UX。
- `admin-frontend/src/layouts/AdminShell.tsx` — 三断点后台 shell、焦点、语义导航和 session menu。
- `backend/app/admin/{schemas.py,service.py,repository.py}` — server-owned metrics UTC window 的严格 DTO、规范化和安全回显。
- `admin-frontend/src/features/overview/{api.ts,AdminOverviewPage.tsx}` — response-owned metrics Zod contract、TanStack Query 和 UTC 审计深链接。
- `admin-frontend/src/features/runs/RunsPage.tsx` — 消费 overview 传入的 UTC 窗口，避免跳转后口径漂移。
- `admin-frontend/vite.config.ts` — 本地同源代理公开登录/身份边界，不持久化 refresh material。

## Decisions Made

- 前端只把确认后的 admin identity 放入内存；JWT 或 `/users/me` 中的 role 不是 RBAC 授权结论，probe 与每个 admin API 的后端 DB-RBAC 才是权威。
- 服务端在未传入边界时用注入时钟定义 UTC 24 小时窗口，并回显 `from`/`to`；overview 链接只使用这个严格响应，不把浏览器时间伪装为服务端口径。
- 运行指标的数值均由服务端提供，前端只格式化显示，不计算百分位数、失败率或费用。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Query correctness] 冻结 overview UTC window**
- **Found during:** Task 3
- **Issue:** 在 render 中重新创建 window 会不断变更 TanStack Query key，导致 query 重取并可能让卡片与链接的时间范围失配。
- **Fix:** 使用一次性 state initializer 冻结挂载窗口。
- **Files modified:** `admin-frontend/src/features/overview/AdminOverviewPage.tsx`
- **Verification:** overview focused test、完整 Vitest、typecheck 和 build 通过。
- **Committed in:** `1a4617c`

**2. [Rule 2 - Deep-link correctness] runs 消费 overview UTC 参数**
- **Found during:** Task 3
- **Issue:** 既有 runs 页面忽略 URL 查询参数，会在 overview 跳转后创建新的窗口，破坏可审计口径。
- **Fix:** 仅接受有效 UTC `occurred_after`/`occurred_before` 并以其初始化 runs filters；无效输入安全回退默认窗口。
- **Files modified:** `admin-frontend/src/features/runs/RunsPage.tsx`
- **Verification:** focused runs/overview/shell tests、完整 Vitest、typecheck 和 build 通过。
- **Committed in:** `1a4617c`

**3. [Rule 3 - Development integration] 代理公开登录与身份 API**
- **Found during:** Task 2
- **Issue:** 独立 Vite server 原先只代理 `/api/v1/admin`，真实登录需要的 `/api/v1/auth` 与 `/api/v1/users` 会在本地开发 404。
- **Fix:** 增加仅这两个同源公开 API proxy，并更新根 README 的边界说明。
- **Files modified:** `admin-frontend/vite.config.ts`, `admin-frontend/README.md`
- **Verification:** 完整 Vitest、typecheck、production build 通过；真实浏览器成功载入后台登录和未认证 guard 路径。
- **Committed in:** `e3d502d`

**4. [User-authorized minimal backend extension] metrics 回显服务端 UTC 窗口**
- **Found during:** Plan completion review
- **Issue:** 原 metrics 投影只返回聚合数值，overview 只能把客户端生成的 query 参数作为深链接窗口，不能证明服务端实际采用的范围。
- **Fix:** service 规范化缺省为当前 UTC 向前 24 小时，repository 在严格 response 中回显别名字段 `from`/`to`；overview Zod schema 要求该字段并直接用于链接。
- **Files modified:** `backend/app/admin/{schemas.py,service.py,repository.py}`, `backend/tests/{admin,unit,integration}/test_admin_run_*.py`, `admin-frontend/src/features/overview/{api.ts,AdminOverviewPage.tsx,AdminOverviewPage.test.tsx}`
- **Verification:** backend service/API 5 passed、隔离 PostgreSQL repository 1 passed、frontend focused test 4 passed、typecheck、build 与 Ruff 通过。
- **Committed in:** `b8ac995`

---

**Total deviations:** 4（Rule 1: 1，Rule 2: 1，Rule 3: 1，用户授权最小扩展: 1）。
**Impact on plan:** 都是保持 UTC 审计口径、可用真实登录链与缓存/授权边界的必要修复；未加入依赖、未伪造 token 或扩大敏感数据暴露。

## Verification

- `cd admin-frontend && npm test` — 8 files、22 tests passed。
- `cd admin-frontend && npm run typecheck` — passed。
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` — passed。
- `cd backend && uv run pytest tests/admin/test_admin_run_service.py tests/unit/test_admin_run_api.py` — 5 passed。
- `cd backend && tests/run_pg.py ... tests/integration/test_admin_run_metrics_repository.py` — 隔离 PostgreSQL 1 passed。
- `cd backend && uv run ruff check app/admin tests/admin/test_admin_run_service.py tests/unit/test_admin_run_api.py tests/integration/test_admin_run_metrics_repository.py` — passed。
- 内置浏览器：`/admin/login` 成功显示已标记邮箱/密码表单，空提交显示字段错误；直接访问 `/admin/overview` 被 guard 重定向到 `/admin/login?returnTo=%2Fadmin%2Foverview`，未出现后台导航或数据。
- 未执行真实管理员凭据提交、数据库直写、token 伪造或内部函数调用；已认证数据、Sheet 和完整 overview 的浏览器 E2E 仍需具备真实管理员会话的 06-20 验收补充。

## Known Stubs

None. 指标数据、会话和权限均不以本地 mock/placeholder 代替真实公开 API；未认证状态只显示登录入口。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-20 可用真实管理员身份完整验证 login → probe → Shell → overview → filtered runs 路径，以及普通用户和过期 session 的拒绝体验。
- `/runs/metrics` 现在以严格 `from`/`to` 回显实际服务端 UTC 窗口，后续 feature 必须复用这个 response-owned 合约而非浏览器侧时间。

## Self-Check: PASSED

- 已确认 `AdminLoginPage.tsx`、`AdminShell.tsx`、`AdminOverviewPage.tsx`、`overview/api.ts` 和 `overview/README.md` 存在。
- 已确认 `d866eb0`、`3be56e3`、`1a4617c`、`e3d502d`、`b8ac995` 位于 Git 历史，且任务提交没有删除受跟踪文件。
- 已重新运行 backend focused/PG tests、frontend focused tests、typecheck、Ruff 和 production build，全部通过。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
