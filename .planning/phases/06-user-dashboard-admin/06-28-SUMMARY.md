---
phase: 06-user-dashboard-admin
plan: 28
subsystem: admin-e2e-testing
tags: [playwright, react, fastapi, postgresql, mailpit, rbac, runtime-config]
requires:
  - phase: 06-26
    provides: database-authoritative catalog command RBAC and lifecycle contracts
  - phase: 06-27
    provides: in-memory Bearer admin guard and normal-user probe rejection
provides:
  - Empty RuntimeConfig v0 can create the first enabled, non-secret policy through the public admin UI.
  - A serial, isolated admin Playwright runner verifies bootstrap, DB-RBAC, config and catalog lifecycle evidence.
  - A real normal-user admin probe 403 path that asserts no private shell or data is rendered.
affects: [admin-rbac, runtime-config, catalog-lifecycle, phase-06-verification]
tech-stack:
  added: []
  patterns: [guarded PostgreSQL E2E startup, Mailpit public-code verification, SPA-only protected navigation, in-memory Bearer observation]
key-files:
  created: [admin-frontend/playwright.config.ts, admin-frontend/tests/e2e/admin-management.spec.ts]
  modified: [admin-frontend/src/features/config/ConfigSummaryPage.tsx, admin-frontend/src/features/config/ConfigSummaryPage.test.tsx, admin-frontend/tests/e2e/README.md, admin-frontend/tests/README.md, admin-frontend/README.md]
key-decisions:
  - "Empty RuntimeConfig is a legal version-0 creation state; the UI sends the same public versioned command with If-Match: 0."
  - "Protected admin E2E navigation uses SPA links after login because a full load intentionally clears the memory-only access token."
  - "The initial-role CLI remains an audited operational boundary and never supplies RuntimeConfig or endpoint authorization evidence."
patterns-established:
  - "Admin E2E owns backend 8003, user SPA 5183, and admin SPA 5184 with HTTP readiness, no server reuse, and SIGTERM cleanup."
  - "Cross-stack admin acceptance creates state only through browser auth, Mailpit public HTTP, the guarded audited bootstrap CLI, and public HTTP APIs."
requirements-completed: [ADM-01, ADM-02, ADM-04, ADM-05, ARC-08]
duration: 13min
completed: 2026-09-04
---

# Phase 06 Plan 28: Isolated Admin Management E2E Summary

**空测试库中的真实后台链路现在证明：验证账户经受审计首位管理员 bootstrap 后，可由内存 Bearer Guard 创建 RuntimeConfig v1、完成目录生命周期，并拒绝普通用户。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-04T06:10:00Z
- **Completed:** 2026-09-04T06:23:15Z
- **Tasks:** 2/2
- **Files modified:** 8

## Accomplishments

- 空 RuntimeConfig 的 404 不再静默阻止提交：页面以 `If-Match: 0`、随机 `Idempotency-Key` 和内存 Bearer 发出公开 POST，并只显示服务端返回的 v1 非密钥摘要。
- 页面在网络请求前拒绝零/负预算；首个版本若未启用同样 fail-closed，既有 401/403 session 清理、409 编辑保留和键盘焦点语义保持有效。
- 新 runner 从受 `run_pg.py` 保护的 `food_agent_test` reset 启动 FastAPI、两个 Vite preview 和 Mailpit，实际通过浏览器验证账户、CLI 首位角色、Guard 200、RuntimeConfig 201、目录草稿/审核/发布/失格和审计。
- 普通用户通过同一真实注册、验证、后台登录链获得 Bearer probe 403，并确认 `/admin/forbidden` 不渲染 AdminShell、目录或概览私有 DOM。

## Task Commits

Each task was committed atomically:

1. **Task 1: 让空 RuntimeConfig 页面通过公共 admin 合约创建首个 enabled policy** — `6835b65` (`test`, TDD RED) and `6dfd479` (`feat`, TDD GREEN)
2. **Task 2: 构建后台专属 runner，并串行验证管理生命周期与普通用户拒绝** — `b52d558` (`test`)
3. **E2E 回归修复：使目录生命周期确认在真实桌面视口可达** — `a71e4f1` (`fix`)

## Files Created/Modified

- `admin-frontend/src/features/config/ConfigSummaryPage.tsx` — treats an absent config as v0, validates positive policy economics, and posts the first public policy version.
- `admin-frontend/src/features/config/ConfigSummaryPage.test.tsx` — locks 404→v0 POST→201 and pre-request zero-budget rejection.
- `admin-frontend/playwright.config.ts` — owns fixed test ports, guarded backend reset, CORS, two previews, readiness, no reuse and SIGTERM cleanup.
- `admin-frontend/tests/e2e/admin-management.spec.ts` — performs the complete public browser/CLI/Guard/config/catalog/normal-user flow without direct database or token shortcuts.
- `admin-frontend/src/features/catalog/CatalogLifecyclePage.tsx` — bounds and scrolls a long lifecycle dialog without changing its alertdialog or focus semantics.
- `admin-frontend/tests/e2e/README.md`, `admin-frontend/tests/README.md`, `admin-frontend/README.md` — document the executable isolation order and bootstrap boundary.

## Decisions Made

- Empty config is not an authorization or seed shortcut. It is a version-0 UI state whose creation still requires the real public admin command and current backend RBAC.
- The spec observes Guard and command response status rather than treating CLI success or `/users/me` identity as proof of admin authorization.
- Post-login protected navigation uses `AdminShell` links, preserving the deliberate memory-only token boundary instead of inserting or persisting a token for tests.

## Verification

- `cd admin-frontend && npm test -- src/features/config/ConfigSummaryPage.test.tsx` — **5 tests passed**.
- `cd admin-frontend && npm run typecheck` — **passed**.
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` — **passed**.
- `cd admin-frontend && npm run test:e2e -- --list` — **1 admin-management Chromium test discovered**.
- `cd admin-frontend && E2E_ADMIN_BACKEND_PORT=8003 E2E_ADMIN_USER_FRONTEND_PORT=5183 E2E_ADMIN_FRONTEND_PORT=5184 npm run test:e2e -- --grep admin-management` — **initially failed**: the review dialog’s submit button was outside its fixed viewport, so no public review POST occurred and the old PASS assertion was incorrect. After `a71e4f1`, the same guarded isolated command **passed** against a freshly reset `food_agent_test`, Mailpit, FastAPI and both Vite previews; it observed review, publish and disqualification POST 200 plus the ordinary-user probe 403.
- `cd admin-frontend && npm test -- src/features/catalog/CatalogLifecyclePage.test.tsx` — **4 tests passed** after the dialog repair.
- `cd admin-frontend && npm run typecheck` — **passed** after the dialog repair.
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` — **passed** after the dialog repair.
- `git diff --check` — **passed**.

## Browser Verification

Playwright Chromium executed the real public path on the isolated product servers: user registration and Mailpit-backed email verification, audited first-admin bootstrap, admin login/probe 200, RuntimeConfig POST 201, catalog lifecycle/audit, and a separate ordinary user's probe 403/forbidden path. No database write, token/cookie injection, browser storage read, internal service call, fixture identity, or real model invocation was used.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Passed the required admin API base to both build and preview processes**
- **Found during:** Task 2
- **Issue:** The preview process omitted `VITE_ADMIN_API_BASE_URL`; the existing fail-closed Vite contract correctly refused to start.
- **Fix:** Explicitly passed `/api/v1/admin` to both admin build and preview commands.
- **Files modified:** `admin-frontend/playwright.config.ts`
- **Verification:** Full isolated E2E runner starts the admin preview and completes its public flow.
- **Committed in:** `b52d558`

**2. [Rule 1 - Bug] Kept protected-route navigation inside the SPA session**
- **Found during:** Task 2
- **Issue:** `page.goto('/admin/catalog')` performed a full reload and intentionally cleared the memory-only Bearer, returning the test to login instead of testing catalog governance.
- **Fix:** Used semantic `AdminShell` links after login for catalog, overview and runs navigation.
- **Files modified:** `admin-frontend/tests/e2e/admin-management.spec.ts`
- **Verification:** The full lifecycle and normal-user rejection E2E pass with no token persistence or injection.
- **Committed in:** `b52d558`

**3. [Rule 1 - Bug] Made long catalog lifecycle confirmations reachable in the declared desktop viewport**
- **Found during:** Post-plan E2E regression verification
- **Issue:** The project-level Desktop Chrome device preset silently overrode the declared 1280×900 viewport with 1280×720. Even at 1280×900, the lifecycle alertdialog had no height bound or overflow, so the full server diff pushed the confirmation button outside the fixed dialog viewport. The browser therefore did not click it and emitted no review POST.
- **Fix:** Explicitly retained the 1280×900 project viewport; constrained the dialog to `max-h-[calc(100dvh-2rem)]` with vertical scrolling; and made the E2E scroll the real confirmation into view and assert it is in the viewport before clicking.
- **Files modified:** `admin-frontend/playwright.config.ts`, `admin-frontend/src/features/catalog/CatalogLifecyclePage.tsx`, `admin-frontend/tests/e2e/admin-management.spec.ts`
- **Verification:** The same isolated browser flow now observed real review, publish and disqualification POST 200 responses, then completed the normal-user 403/forbidden path.
- **Committed in:** `a71e4f1`

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs).
**Impact on plan:** All fixes preserve the plan's fail-closed configuration and runtime-only token boundaries; the third repair restores a real user-visible confirmation path rather than bypassing it.

## Issues Encountered

- The sandbox initially denied Docker socket access. The plan's isolated runner was then executed only after explicit permission, using its guarded test wrapper; no development database was contacted.
- The original E2E PASS report was false: later independent rerun reproduced a 45-second review-response timeout. Trace evidence showed the confirmation button was outside the dialog viewport, not an API route, status, race, or authorization failure. This was corrected and reverified with `a71e4f1`.

## Known Stubs

None. The changed production path consumes the real public RuntimeConfig API; E2E state comes from actual browser and server interactions, not mock data.

## User Setup Required

None - no external service configuration required. Local E2E requires the documented Docker test dependencies.

## Next Phase Readiness

- Phase verification can now use a repeatable independent-admin E2E artifact for the previously missing management/rejection flow.
- `06-VERIFICATION.md` still needs its separate re-verification workflow; this executor intentionally did not change phase state or roadmap files.

## Self-Check: PASSED

- Confirmed all seven implementation/test/documentation artifacts and this summary exist.
- Confirmed TDD, task and regression-repair commits `6835b65`, `6dfd479`, `b52d558`, and `a71e4f1` exist in Git history.
- Confirmed no whitespace errors in the final diff.

*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-04*
