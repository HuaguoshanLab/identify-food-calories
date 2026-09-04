---
phase: 06-user-dashboard-admin
plan: 27
subsystem: admin-auth
tags: [react, typescript, tanstack-query, zod, msw, vitest, rbac]
requires:
  - phase: 06-17
    provides: in-memory admin session and strict probe guard boundary
  - phase: 06-22
    provides: public login/identity handoff and admin shell routes
  - phase: 06-24
    provides: independent admin application contract and security verification baseline
provides:
  - ID-only in-memory admin identity after public login
  - strict Bearer admin-probe gate before private route rendering
  - cache-clearing 401/403/no-token/invalid-probe recovery contract
affects: [admin-auth, admin-e2e, phase-06-verification]
tech-stack:
  added: []
  patterns: [token-only-identity, probe-before-private-render, fail-closed-query-cache]
key-files:
  created:
    - admin-frontend/src/auth/AdminRouteGuard.test.tsx
  modified:
    - admin-frontend/src/auth/AdminAuthProvider.tsx
    - admin-frontend/src/auth/AdminLoginPage.tsx
    - admin-frontend/src/auth/AdminLoginPage.test.tsx
    - admin-frontend/src/auth/AdminRouteGuard.tsx
    - admin-frontend/src/features/config/ConfigSummaryPage.test.tsx
key-decisions:
  - "`/users/me` only confirms an active authenticated identity; its role never grants or denies admin SPA access."
  - "Only a strict successful Bearer `/api/v1/admin/probe` may render private children; all other outcomes clear private cache and fail closed."
patterns-established:
  - "Admin memory sessions retain only `{ id }` plus the runtime access token; identity changes compare IDs only."
  - "A no-token guard clears TanStack Query before redirecting, preventing a stale private cache from leaking into login or forbidden UX."
requirements-completed: [ADM-01, ARC-08]
duration: 12min
completed: 2026-09-04
---

# Phase 06 Plan 27: Token-only Admin Identity and Probe Guard Summary

**Admin login now establishes only an in-memory token plus user ID, while a strict database-backed Bearer probe is the sole frontend gate for private admin rendering.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-04T05:57:39Z
- **Completed:** 2026-09-04T06:09:37Z
- **Tasks:** 2/2
- **Files modified:** 6

## Accomplishments

- Removed `role` from `AdminIdentity`; active `user` and `admin` identity responses now follow the same public-login handoff and cannot decide admin access before the guard probe.
- Kept the access token entirely in React memory and preserved safe registered `/admin/*` return navigation; inactive or malformed identity responses remain on the login-safe path.
- Added independent Guard coverage for strict Bearer probe success, 403 forbidden, 401/no-token/network failure, invalid DTO rejection, session clearing, Query cache clearing, and non-rendering private children.
- Updated the shared ConfigSummary authenticated fixture to the ID-only session contract without weakening its existing successful probe coverage.

## Task Commits

1. **Task 1: 收窄 AdminIdentity，使登录只建立 token-only 认证交接** — `0121e05` (`test`), `66f277b` (`feat`)
2. **Task 2: 让 Guard 的真实 Bearer probe 成为唯一前端授权体验边界** — `ba36a88` (`test`), `7052097` (`fix`), `12c2bef` (`test`)

## Files Created/Modified

- `admin-frontend/src/auth/AdminAuthProvider.tsx` — ID-only session identity and identity-change cache boundary.
- `admin-frontend/src/auth/AdminLoginPage.tsx` — public login now checks active identity only, then establishes the in-memory token/ID handoff.
- `admin-frontend/src/auth/AdminLoginPage.test.tsx` — proves active user/admin handoffs are identical and safe return paths stay in memory.
- `admin-frontend/src/auth/AdminRouteGuard.tsx` — clears Query cache for no-token failures while preserving strict probe-before-children behavior.
- `admin-frontend/src/auth/AdminRouteGuard.test.tsx` — regression suite for success, forbidden, authentication failure, network failure, strict DTO rejection, and no persistence writes.
- `admin-frontend/src/features/config/ConfigSummaryPage.test.tsx` — shared guard fixture no longer carries a role field.

## Decisions Made

- `/users/me.role` remains parsed as part of the public identity response contract but is intentionally discarded: frontend role data is neither a grant nor a denial of admin access.
- The guard remains a UX boundary only. Every admin endpoint still requires its own current PostgreSQL RBAC check.
- When the guard finds no in-memory token, it clears TanStack Query before redirecting. This closes the stale-cache path left between a prior session and a safe login route.

## Verification

- `cd admin-frontend && npm test -- src/auth/AdminLoginPage.test.tsx src/auth/AdminRouteGuard.test.tsx src/features/config/ConfigSummaryPage.test.tsx` — **3 files, 10 tests passed**.
- `cd admin-frontend && npm run typecheck` — **passed**.
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` — **passed**.
- `git diff --check` — **passed**.

## Browser Verification

Not performed. This plan needs a running real public backend plus real user/admin credentials to verify normal-user probe 403 without forging a token. The execution scope explicitly prohibited starting or manipulating persistent external environments, so no browser path was claimed as accepted. MSW/Vitest coverage is not presented as a browser substitute.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- After Task 1, typecheck correctly reported the old ConfigSummary fixture's removed `role` field. Task 2 updated that planned fixture, then typecheck passed.

## Known Stubs

None. The changed production paths use the real public login, identity, and admin-probe contracts; no empty/mock value flows to private UI rendering.

## Threat Flags

None. The plan reduces privilege-confusion and stale-cache exposure without adding endpoints, file access, schema changes, or a new trust boundary.

## Next Phase Readiness

- Plan 06-28 can exercise a real normal-user Bearer `/api/v1/admin/probe` 403 path without relying on `/users/me.role` or forged frontend permission state.
- Real-browser verification remains outstanding until a safe public backend and legitimate test credentials are available.

## Self-Check: PASSED

- Confirmed all six production/test artifacts and this summary exist.
- Confirmed task commits `0121e05`, `66f277b`, `ba36a88`, `7052097`, and `12c2bef` exist in Git history.
- Confirmed the working-tree diff has no whitespace errors.
