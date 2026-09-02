---
phase: 06-user-dashboard-admin
plan: 12
subsystem: admin-api-database
tags: [fastapi, pydantic, sqlalchemy, alembic, postgresql, rbac, audit, idempotency]
requires:
  - phase: 06-11
    provides: database-authoritative admin RBAC and append-only generic admin audit foundation
provides:
  - Strict, revisioned catalog draft create and optimistic patch commands
  - Server-computed field diffs, change-set evidence, immutable draft snapshots, and idempotent command replay
  - One-head Alembic migration chain through 0017
affects: [06-user-dashboard-admin, catalog-review-publish, admin-frontend]
tech-stack:
  added: []
  patterns: [strict command DTO, DB-RBAC, server-derived audit diff, If-Match revision, idempotency-key replay]
key-files:
  created: [backend/migrations/versions/0017_catalog_drafts.py, backend/tests/admin/test_catalog_draft_service.py, backend/tests/integration/test_catalog_draft_repository.py, backend/tests/unit/test_admin_catalog_api.py]
  modified: [backend/app/admin/models.py, backend/app/admin/schemas.py, backend/app/admin/repository.py, backend/app/admin/service.py, backend/app/admin/api.py]
key-decisions:
  - "Catalog draft mutations store only server-computed shallow scalar diffs; raw client diff JSON is never accepted or returned as the draft projection."
  - "Idempotency is represented by an append-only change set with a request hash, so key reuse with a different command is rejected."
  - "The authorized migration renumbering uses 0017 with 0016 as sole predecessor because 0015 and 0016 were already occupied; Alembic remains single-head."
patterns-established:
  - "Admin mutation: strict Pydantic command → current DB RBAC → repository flushes mutation/change-set/revision/audit → one Service commit or rollback."
  - "Catalog PATCH: required If-Match revision plus Idempotency-Key; changed fields are recomputed from persisted state."
requirements-completed: [ADM-02, ADM-05]
duration: 12min
completed: 2026-09-02
---

# Phase 06 Plan 12: Catalog Draft Workflow Summary

**Revisioned nutrition catalog drafts with strict commands, server-computed audit evidence, optimistic concurrency, and a single Alembic 0017 head.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-02T11:58:00Z
- **Completed:** 2026-09-02T12:10:02Z
- **Tasks:** 3/3
- **Files modified:** 16

## Accomplishments

- Added strict create and patch contracts for names, aliases, per-100g nutrients, HTTPS provenance, authorization state, reason, unknown fields, `If-Match`, and `Idempotency-Key`.
- Added mutable draft state, append-only server-derived change sets, per-revision immutable snapshots, and matching generic admin audit entries in one transaction.
- Added safe create/patch endpoints that reload administrator authority from PostgreSQL and expose only the minimal draft projection.
- Continued the existing Alembic chain with `0017_catalog_drafts.py` from `0016`; `alembic heads` reports only `0017`.

## Task Commits

1. **Task 1: 写 catalog draft RED 契约** — `d8424aa` (`test`)
2. **Task 2: 实现 revision 化目录草稿 API** — `5df50dd` (`feat`), `63813c8` (`test`)
3. **Task 3: 固定迁移线性前驱** — `197a2ba` (`chore`)

## Files Created/Modified

- `backend/migrations/versions/0017_catalog_drafts.py` — draft/change-set/revision schema with `0016` as its sole predecessor.
- `backend/app/admin/models.py` — draft, change-set, and immutable revision ORM state.
- `backend/app/admin/schemas.py` — strict request DTOs and safe draft response projection.
- `backend/app/admin/repository.py` and `ports.py` — flush-only draft persistence operations.
- `backend/app/admin/service.py` — DB-RBAC, idempotency hash/replay, server field diff, optimistic revision and atomic audit behavior.
- `backend/app/admin/api.py` — protected `POST`/`PATCH /api/v1/admin/catalog-drafts` translations.
- `backend/tests/{admin,integration,unit}/test_*catalog*` — fake-service, PostgreSQL and HTTPX contracts.

## Decisions Made

- The client may submit new field values but never an audit diff; the Service derives changed scalar fields from persisted draft state.
- A change-set records the command key and request hash. Retrying the same command returns its draft; reusing the key for different input is a `409` conflict.
- The planned `0015` filename was unavailable. Per user authorization, the migration is `0017_catalog_drafts.py` and depends only on existing head `0016`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Preserved the occupied Alembic lineage**
- **Found during:** Task 2/3
- **Issue:** `0015` and `0016` already existed, so creating the planned `0015_catalog_drafts.py` would create a duplicate revision and break the single-head migration contract.
- **Fix:** Created `0017_catalog_drafts.py` with `down_revision = "0016"`, updated migration indexes, and documented the authorized succession.
- **Files modified:** `backend/migrations/versions/0017_catalog_drafts.py`, migration README indexes.
- **Verification:** `alembic heads` reports only `0017`; verbose history shows `0017 → 0016 → 0015`.
- **Committed in:** `5df50dd`, `197a2ba`

**2. [Rule 2 - Missing Critical] Added request-hash checking for idempotency-key reuse**
- **Found during:** Task 2
- **Issue:** A unique key alone could replay a previously successful command for different request data, hiding a client bug and weakening command integrity.
- **Fix:** Persisted a server-computed request hash on the append-only change set and reject mismatched reuse with `409`.
- **Files modified:** `backend/app/admin/models.py`, `backend/app/admin/service.py`, `backend/migrations/versions/0017_catalog_drafts.py`.
- **Verification:** service contract test covers replay; targeted service/API/PostgreSQL tests pass.
- **Committed in:** `5df50dd`

---

**Total deviations:** 2 auto-fixed (1 Rule 2, 1 Rule 3).
**Impact on plan:** Both changes preserve correctness and security; no new external dependency or architectural expansion was introduced.

## Issues Encountered

- The plan's bare `APP_ENV=test uv run alembic upgrade head` command lacks the mandatory `TEST_DATABASE_URL` in this shell. The repository-required `tests/run_pg.py --env-file .env.test.example` wrapper supplied the isolated, validated test environment instead.

## Verification

- `uv run pytest tests/admin/test_catalog_draft_service.py tests/unit/test_admin_catalog_api.py -q` — 7 passed.
- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run alembic upgrade head` — passed.
- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/integration/test_catalog_draft_repository.py -q` — 1 passed.
- `uv run ruff check app/admin tests/admin/test_catalog_draft_service.py tests/integration/test_catalog_draft_repository.py tests/unit/test_admin_catalog_api.py` — passed.
- `uv run mypy app/admin` — passed (8 source files).
- `uv run alembic heads` — only `0017 (head)`.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Catalog review/publish work can consume safe draft projections and immutable revision evidence.
- A real browser workflow remains a later admin-frontend acceptance responsibility; this backend-only plan has no user-visible page to verify.

## Self-Check: PASSED

- Found `backend/migrations/versions/0017_catalog_drafts.py` and all three catalog draft test files.
- Found task commits `d8424aa`, `5df50dd`, `197a2ba`, and `63813c8`.
