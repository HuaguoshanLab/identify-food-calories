---
phase: 06-user-dashboard-admin
plan: 07
subsystem: database
tags: [postgresql, alembic, sqlalchemy, cache, weekly-review]
requires:
  - phase: 06-02
    provides: tenant-filtered dashboard aggregates over persisted local dates
provides:
  - deterministic Monday-start weekly facts and low-coverage abstention
  - versioned PostgreSQL weekly-review cache key and minimal result storage
  - advisory-lock claim/finalize path that serializes provider calls per cache key
affects: [weekly-review-api, agent-service, admin-migrations]
tech-stack:
  added: []
  patterns: [facts-first provider gate, versioned cache identity, PostgreSQL advisory transaction lock]
key-files:
  created: [backend/app/dashboard/weekly_review_dto.py, backend/app/dashboard/models.py, backend/migrations/versions/0015_weekly_review_results.py]
  modified: [backend/app/dashboard/repository.py, backend/app/dashboard/service.py]
key-decisions:
  - "Weekly review cache identity contains user, week, facts digest, and all four runtime versions."
  - "Low coverage is a deterministic abstention before any Provider call."
  - "The authorized migration revision is 0015 with 0014 as its sole predecessor."
patterns-established:
  - "Persist only digests, safe advice or abstention code, versions, and optional AgentRun linkage at the Provider boundary."
  - "Use a transaction-scoped advisory lock plus SELECT FOR UPDATE before billable work for a cache key."
requirements-completed: [UI-02]
duration: 32min
completed: 2026-09-02
---

# Phase 06 Plan 07: Weekly Review Facts Cache Summary

**Monday-anchored weekly facts with deterministic low-coverage abstention, minimal versioned cache records, and per-key Provider-call serialization.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-09-02T11:00:00Z
- **Completed:** 2026-09-02T11:32:00Z
- **Tasks:** 3/3
- **Files modified:** 12

## Accomplishments

- Built immutable facts/key/response DTOs that exclude raw facts, prompts, Provider bodies, and reasoning.
- Added `WeeklyReviewResult` plus Alembic `0015`, with a full versioned unique key, digest checks, and safe-payload constraints.
- Added low-coverage zero-call behavior, cache-hit reuse, version misses, and PostgreSQL advisory-lock/row-lock claim logic.

## Task Commits

1. **Task 1: 写 facts、唯一 cache key 和并发 RED 测试** — `ad91ab3` (test)
2. **Task 2: 实现最小结果表和 facts-first cache service** — `61a8a1c` (feat), `364bf39` (fix)
3. **Task 3: 固定线性迁移前驱** — `de08322` (chore)

## Files Created/Modified

- `backend/app/dashboard/weekly_review_dto.py` — strict facts, cache-key, and safe response DTOs.
- `backend/app/dashboard/models.py` — minimal `WeeklyReviewResult` ORM cache record.
- `backend/app/dashboard/repository.py` — terminal-result lookup plus advisory-lock claim/finalize operations.
- `backend/app/dashboard/service.py` — deterministic facts generation, coverage gate, and cache orchestration.
- `backend/migrations/versions/0015_weekly_review_results.py` — sole-head PostgreSQL schema revision.
- `backend/tests/dashboard/test_weekly_review_*.py` — service contracts for coverage and cache invalidation.
- `backend/tests/integration/test_weekly_review_cache_repository.py` — guarded PostgreSQL uniqueness proof.

## Decisions Made

- The cache key deliberately includes `graph_version`, `prompt_version`, `schema_version`, and `runtime_config_version`; any behavior change naturally misses rather than replaying stale advice.
- `OUTCOME_UNKNOWN` remains non-replayable: an uncertain Provider result is never exposed as a cache hit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Serialized Provider claims rather than only duplicate rows**
- **Found during:** Task 2
- **Issue:** A unique insert alone can still allow competing requests to call a billable Provider before one insert loses.
- **Fix:** Added PostgreSQL transaction advisory locking and `SELECT FOR UPDATE` claim/finalize operations.
- **Files modified:** `backend/app/dashboard/repository.py`, `backend/app/dashboard/service.py`
- **Verification:** focused tests and Ruff pass; Alembic reports one head.
- **Committed in:** `364bf39`

**2. [Rule 3 - Blocking] Continued the authorized existing migration chain at 0015**
- **Found during:** Task 3
- **Issue:** Plan text reserved `0013`, but `0013` and `0014` were already committed by dependent Phase 06 work.
- **Fix:** Created `0015_weekly_review_results.py` with `down_revision = "0014"` and documented the hand-off to later migrations.
- **Files modified:** `backend/migrations/versions/0015_weekly_review_results.py`, `backend/migrations/versions/README.md`
- **Verification:** `uv run alembic heads` reports only `0015 (head)`.
- **Committed in:** `61a8a1c`, `de08322`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 3).
**Impact on plan:** Both changes are required to preserve the fee/concurrency boundary and Alembic's single-head invariant.

## Issues Encountered

- The configured isolated PostgreSQL environment is unavailable in this session: `APP_ENV=test uv run alembic upgrade head` stops because `TEST_DATABASE_URL` is unset. Focused tests passed as `2 passed, 2 skipped`; the guarded PostgreSQL uniqueness test must run in the project test environment before release.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Weekly-review API wiring can consume `WeeklyReviewService` without persisting Provider request/response bodies.
- Before release, set the already-required isolated `TEST_DATABASE_URL` and run the guarded migration/integration test.

## Self-Check: PASSED

- Verified DTO, model, migration, and focused test files exist.
- Verified commits `ad91ab3`, `61a8a1c`, `de08322`, and `364bf39` exist in Git history.

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
