---
phase: 06-user-dashboard-admin
plan: 26
subsystem: admin-rbac-and-planning-ui
tags: [fastapi, postgresql, rbac, idempotency, react, vitest, accessibility]
requires:
  - phase: 06-12
    provides: revisioned catalog drafts with request-hash idempotency
  - phase: 06-14
    provides: immutable catalog publications and eligibility commands
  - phase: 06-06
    provides: strict safe planning snapshot and progress rendering boundary
provides:
  - Current PostgreSQL active-admin verification before all catalog replay reads
  - Regression coverage for normal and demoted actors replaying catalog command keys
  - Accessible candidate-exhaustion planning error distinct from health refusals and adjustment limits
affects: [admin-rbac, catalog-lifecycle, planning-ui, phase-06-verification]
tech-stack:
  added: []
  patterns: [database-authoritative command authorization, replay-after-authorization, safe snapshot error rendering]
key-files:
  created: []
  modified: [backend/app/admin/service.py, backend/tests/admin/test_catalog_draft_service.py, backend/tests/admin/test_catalog_lifecycle_service.py, backend/tests/unit/test_admin_catalog_api.py, frontend/src/features/plans/components/PlanPage.tsx, frontend/src/features/plans/components/PlanPage.test.tsx]
key-decisions:
  - "Catalog idempotency replay is authorized only after reloading the actor's active admin role from PostgreSQL."
  - "A terminal, non-limit planning snapshot uses a focused local error title and the validated safe message; health scope and adjustment-limit paths remain separate."
patterns-established:
  - "Every catalog command reads database-authoritative admin state before advisory locks, replay keys, resource projections, or early returns."
  - "Planning terminal errors use FocusedPlanningAlert only for candidate exhaustion, preserving SafePlanningProgress local stage semantics."
requirements-completed: [ADM-01, UI-03]
duration: 15min
completed: 2026-09-04
---

# Phase 06 Plan 26: Catalog RBAC Replay and Planning Error Recovery Summary

**Catalog command-key replays now require fresh PostgreSQL active-admin authorization, while candidate exhaustion restores a focused, safe “暂时无法生成计划” user error.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-04T13:39:00+08:00
- **Completed:** 2026-09-04T13:54:36+08:00
- **Tasks:** 2/2
- **Files modified:** 6

## Accomplishments

- Moved `require_role(..., UserRole.ADMIN)` ahead of every create, patch, publish, and disqualify replay/resource path; JWT claims and command keys cannot authorize access.
- Added fake-repository service regressions for normal users and demoted/inactive prior admins replaying known create, patch, publish, and disqualify keys; all are denied.
- Expanded HTTP contracts so every catalog command maps an `AdminPermissionDenied` to public `403 ADMIN_PERMISSION_REQUIRED`.
- Restored the terminal candidate-exhaustion alert title and safe description without conflating it with health-scope refusal or `LIMIT_REACHED` behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: 以 replay 攻击回归锁定并修复 catalog command 的数据库 RBAC 顺序** — `bf215e6` (`fix`)
2. **Task 2: 恢复候选耗尽的清晰用户失败标题并跑完整前端门禁** — `b55eae9` (`fix`)

## Files Created/Modified

- `backend/app/admin/service.py` — performs current database RBAC before any catalog command replay, lock, lookup, or early return.
- `backend/tests/admin/test_catalog_draft_service.py` — denies create/patch replay to normal and demoted actors.
- `backend/tests/admin/test_catalog_lifecycle_service.py` — denies publish/disqualify replay to normal and inactive prior admins.
- `backend/tests/unit/test_admin_catalog_api.py` — proves all four route-level RBAC denials use the public forbidden contract.
- `frontend/src/features/plans/components/PlanPage.tsx` — renders a focused candidate-exhaustion alert with only validated safe text.
- `frontend/src/features/plans/components/PlanPage.test.tsx` — locks the title, alert semantics, branch separation, and absence of internal Agent strings.

## Decisions Made

- Database authorization always precedes idempotency handling; a replay key is untrusted input, never a resource-read capability.
- Candidate exhaustion retains the strict snapshot's safe message under a stable local title; it does not reuse the medical-referral UI or the bounded-adjustment UI.

## Verification

- `cd backend && uv run pytest tests/admin/test_catalog_draft_service.py tests/admin/test_catalog_lifecycle_service.py tests/unit/test_admin_catalog_api.py -q` — **15 passed**.
- `cd backend && uv run ruff check app/admin/service.py tests/admin/test_catalog_draft_service.py tests/admin/test_catalog_lifecycle_service.py tests/unit/test_admin_catalog_api.py` — **passed**.
- `cd frontend && npm test -- --run` — **26 files / 139 tests passed**.
- `git diff --check` — **passed**.

## Browser Verification

Not completed. Codex's built-in browser was available, but no user frontend server was running on `127.0.0.1:5178` or `127.0.0.1:5173`. This plan's terminal candidate-exhaustion branch also requires a real safe backend snapshot; using a forged token, direct database write, or internal function call would violate the browser-verification contract. Automated UI coverage above is valid but is not claimed as browser acceptance.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The sandbox could not read the existing `uv` cache. The same repository test commands were rerun with narrowly scoped approval; no dependency was installed or changed.

## Known Stubs

None. The scan found no UI-flowing placeholder, TODO/FIXME, or hardcoded empty presentation value in the files changed by this plan.

## Threat Flags

None. The change reduces an existing authorization bypass and keeps the planning UI within its validated safe snapshot boundary; it introduces no endpoint, file-access path, schema change, or new trust boundary.

## Next Phase Readiness

- The catalog admin boundary is ready for re-verification: replay authorization now follows the same current-database rule as the non-replay mutation path.
- A running end-to-end environment is still needed for the required real-browser verification of candidate exhaustion.

## Self-Check: PASSED

- Confirmed all six modified production/test files exist.
- Confirmed task commits `bf215e6` and `b55eae9` exist in Git history.
- Confirmed the working-tree diff has no whitespace errors.
