---
phase: 06-user-dashboard-admin
plan: "04"
subsystem: ui
tags: [react, typescript, tanstack-query, zod, vitest, dashboard, accessibility]
requires:
  - phase: 06-user-dashboard-admin
    provides: strict dashboard overview/history projections and revocable target eligibility
provides:
  - projection-only H5 records dashboard with today, seven-day trend, and paginated history
  - strict client-side dashboard DTO handling that drops invalid eligibility while retaining trusted totals
affects: [records-page, user-dashboard, phase-06-browser-uat]
tech-stack:
  added: []
  patterns: [feature-owned strict Zod DTOs, TanStack query keys with timezone and cursor dimensions, SVG-plus-semantic-table trend]
key-files:
  created: [frontend/src/features/records/api/dashboard.ts, frontend/src/features/records/components/TodaySummaryCard.tsx, frontend/src/features/records/components/WeeklyTrend.tsx, frontend/src/features/records/components/HistoryMealList.tsx]
  modified: [frontend/src/features/records/components/RecordsPage.tsx, frontend/src/features/records/components/TodaySummaryCard.test.tsx, frontend/src/features/records/components/WeeklyTrend.test.tsx, frontend/src/features/records/components/HistoryMealList.test.tsx]
key-decisions:
  - "Records only reads dashboard overview and history projections; it never consults profile or planning APIs to infer targets."
  - "An invalid eligibility payload is discarded independently, so valid strict totals and meal count remain visible without guessed targets."
patterns-established:
  - "Chart data is expressed both as a keyboard-reachable SVG and a semantic table."
  - "History pagination passes only the opaque server cursor through TanStack Query."
requirements-completed: [UI-02]
duration: 8min
completed: 2026-09-02
---

# Phase 06 Plan 04: Projection-only Records Dashboard Summary

**Records H5 now renders a strict API-backed today summary, accessible seven-day energy trend, and opaque-cursor history without fabricating nutrition targets.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-02T10:48:00Z
- **Completed:** 2026-09-02T10:56:37Z
- **Tasks:** 2/2
- **Files modified:** 14

## Accomplishments

- Replaced the legacy records-list request with `/dashboard/overview` and `/dashboard/history`; no profile or plan endpoint is queried.
- Added the first-screen TodaySummaryCard with overview `totals` and `meal_count`, integer-or-needed-decimal energy formatting, and `tabular-nums` facts.
- Shows macro status only for a valid explicit eligibility target; missing, false, revoked, or malformed eligibility preserves real facts and displays no target bars or percentages.
- Added seven fixed SVG points with keyboard navigation and a matching semantic data table, plus server local-date grouped history with opaque cursor pagination.

## Verification

- `cd frontend && npm test -- --run src/features/records/components/TodaySummaryCard.test.tsx src/features/records/components/WeeklyTrend.test.tsx src/features/records/components/HistoryMealList.test.tsx` — passed, 7 tests.
- `cd frontend && npm run typecheck` — passed.
- `cd frontend && npm run build` — passed; Vite reported the existing >500 kB chunk-size warning.
- `cd frontend && npm run lint` — blocked by the pre-existing, unrelated `react-refresh/only-export-components` violation in `src/features/agent/components/SafeProgressStages.tsx`.
- Codex 内置浏览器验收未完成：macOS 锁屏，自动解锁失败，无法从真实登录和公开 API 进入 `/app/records`。未伪造 token、会话或数据库数据。

## Task Commits

1. **Task 1: 建立 projection-only H5 dashboard strict-client RED 测试** — `1eacc52` (`test`)
2. **Task 2: 实现 summary、trend 和 history 的 projection-only 切片** — `f17fe73` (`feat`)

## Files Created/Modified

- `frontend/src/features/records/api/dashboard.ts` — strict overview/history Zod contracts, query-key factory, and public dashboard requests.
- `frontend/src/features/records/components/{TodaySummaryCard,WeeklyTrend,HistoryMealList}.tsx` — summary, accessible trend, and paginated history presentations.
- `frontend/src/features/records/components/RecordsPage.tsx` — retains the AppShell’s sole scroll root while composing projection-only queries.
- `frontend/src/features/records/components/*.test.tsx` — RED/GREEN coverage for facts, eligibility fallback, SVG/table accessibility, keyboard navigation, and opaque cursors.

## Decisions Made

- Dashboard eligibility is an independently strict nested contract: bad or extra eligibility fields do not become a guessed target and do not erase already validated today facts.
- The existing records detail path is retained, while list rows intentionally expose only the minimal history projection available from the dashboard API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Isolated malformed eligibility from factual overview data**
- **Found during:** Task 2
- **Issue:** Strictly parsing the entire response as one DTO would turn an extra or malformed eligibility field into a whole-card failure, contrary to the required honest fallback that retains overview totals and meal count.
- **Fix:** Parse root/today/week fields strictly, then safe-parse the strict eligibility sub-DTO and omit it on failure.
- **Files modified:** `frontend/src/features/records/api/dashboard.ts`, `frontend/src/features/records/components/TodaySummaryCard.test.tsx`
- **Verification:** Targeted Vitest, TypeScript check, and production build passed.
- **Committed in:** `f17fe73`

---

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** Required for a secure, truthful downgrade; no product scope expansion.

## Issues Encountered

- A first GREEN run revealed invalid test fixture dates and a missing Router provider for history links; fixture and test harness were corrected before the final gate.
- The mandatory real-browser acceptance is blocked by the locked macOS host. This is recorded as incomplete rather than claimed as passed.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Unlock the macOS host and complete real public-API browser UAT for both eligible and ineligible accounts at `/app/records`; do not use seeded DB writes or fabricated tokens.
- The unrelated Fast Refresh lint violation remains outside this plan’s scope.

## Self-Check: PASSED

- Confirmed `frontend/src/features/records/api/dashboard.ts` and `frontend/src/features/records/components/HistoryMealList.tsx` exist.
- Confirmed `1eacc52` and `f17fe73` exist in Git history.

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
