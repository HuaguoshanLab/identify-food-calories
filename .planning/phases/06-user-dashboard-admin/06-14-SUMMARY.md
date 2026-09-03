---
phase: 06-user-dashboard-admin
plan: 14
subsystem: admin-api-database
tags: [fastapi, pydantic, sqlalchemy, alembic, postgresql, rbac, advisory-lock, idempotency]
requires:
  - phase: 06-12
    provides: revisioned catalog drafts and server-derived audit evidence
provides:
  - immutable reviewed catalog publications with a one-row active pointer
  - append-only eligibility events that immediately remove disqualified publications from future nutrition lookup
  - DB-RBAC lifecycle endpoints with If-Match, confirmation, audit evidence, and idempotent replay
affects: [06-15, admin-catalog, nutrition, planning]
tech-stack:
  added: []
  patterns: [postgres advisory publication lock, immutable typed snapshot, append-only eligibility overlay]
key-files:
  created: [backend/migrations/versions/0018_catalog_publication_eligibility.py, backend/tests/admin/test_catalog_lifecycle_service.py, backend/tests/integration/test_catalog_publish_eligibility.py]
  modified: [backend/app/admin/service.py, backend/app/admin/api.py, backend/app/admin/repository.py, backend/app/nutrition/repository.py, backend/app/planning/repository.py]
key-decisions:
  - "Publication serializes per draft with a PostgreSQL transaction-scoped advisory lock, including the first-pointer race."
  - "Publication content uses a typed immutable snapshot; audit diffs remain shallow scalar evidence and never substitute for source content."
  - "The authorized migration is 0018 with 0017 as its sole predecessor, preserving the actual one-head chain."
patterns-established:
  - "Lifecycle command: DB-RBAC → per-draft lock → If-Match → immutable review → publication/pointer/eligibility/audit → one commit."
  - "Future nutrition lookup reads only active publications whose latest append-only eligibility event is eligible."
requirements-completed: [ADM-02, ADM-05]
duration: 25min
completed: 2026-09-03
---

# Phase 06 Plan 14: Catalog Publication Eligibility Summary

**审核冻结的目录内容在 PostgreSQL 锁与幂等保护下发布为不可变快照，失格事件即时剔除后续营养查询而不改写已确认餐食。**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-03T09:53:00Z
- **Completed:** 2026-09-03T10:18:46Z
- **Tasks:** 3/3
- **Files modified:** 16

## Accomplishments

- 增加 review、immutable publication、active pointer 和 append-only eligibility history；发布只接受同 revision 的服务器冻结内容。
- `review`、`publish`、`disqualify` API 都强制当前 PostgreSQL admin RBAC、确认、理由、If-Match（适用时）和 Idempotency-Key，并写入最小化 audit。
- nutrition repository 只将 active + latest eligible publication 投影为未来可计算候选；失格后立即不可读取。planning 的 future recipe SQL 也检查 active publication disqualification，MealRecord 模型和查询完全未改动。
- 真实 PostgreSQL 两线程并发测试证明两个同键 publish 只得到一个 publication/pointer。

## Task Commits

1. **Task 1: 写发布、失格与快照稳定 RED 测试** — `0b10f42` (`test`)
2. **Task 2: 实现 immutable 发布和 eligibility overlay** — `2b4ad16` (`feat`)
3. **Task 3: 固定 0016 的线性迁移前驱** — `906103b` (`chore`)

## Files Created/Modified

- `backend/migrations/versions/0018_catalog_publication_eligibility.py` — publication lifecycle schema，唯一前驱为 `0017`。
- `backend/app/admin/{models,schemas,ports,repository,service,api}.py` — DB-RBAC lifecycle command 和事务协议。
- `backend/app/nutrition/repository.py` — active/eligible publication 的未来候选 SQL guard。
- `backend/app/planning/repository.py` — future recipe eligibility overlay guard。
- `backend/tests/admin/test_catalog_lifecycle_service.py` 与 `backend/tests/integration/test_catalog_publish_eligibility.py` — fake contract、真实 PG publication/eligibility/concurrency 证据。

## Decisions Made

- 每个 draft 使用 transaction-scoped PostgreSQL advisory lock；不存在 pointer 行时也可阻止首发竞争。
- immutable publication snapshot 保持 aliases 列表和每 100g 值的类型化内容；审计仅持有允许列表标量 diff。
- 原计划的 `0016` 已被占用。用户明确授权后采用 `0018 → 0017`，未创建第二个 Alembic head。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐 lifecycle schema 与 port 契约**
- **Found during:** Task 2
- **Issue:** 原 files 列表未包含 `schemas.py`、`ports.py`，无法对 lifecycle HTTP 输入执行运行时校验，也无法维持 Service → Repository 协议。
- **Fix:** 增加 strict confirmed command/publication projection DTO 和 repository capability protocol。
- **Files modified:** `backend/app/admin/schemas.py`、`backend/app/admin/ports.py`。
- **Verification:** targeted PostgreSQL、Ruff、mypy 通过。
- **Committed in:** `2b4ad16`

**2. [Rule 3 - Blocking] 按现有 head 顺延迁移编号**
- **Found during:** Task 2/3
- **Issue:** 计划的 `0016`/`0015` 迁移编号均已占用；复用会破坏 Alembic revision identity 并产生分叉。
- **Fix:** 经用户授权创建 `0018_catalog_publication_eligibility.py`，`down_revision = "0017"`。
- **Files modified:** migration 与 migration README indexes。
- **Verification:** `alembic heads` 仅输出 `0018 (head)`；verbose history 显示 `0018 → 0017 → 0016`。
- **Committed in:** `2b4ad16`、`906103b`

---

**Total deviations:** 2 auto-fixed（Rule 2: 1，Rule 3: 1）。
**Impact on plan:** 均为运行时安全、架构依赖方向和单一迁移链所必需；无新增依赖。

## Issues Encountered

- `uv` 默认缓存目录在 sandbox 外，测试需经受控权限访问已安装依赖缓存；未安装或变更依赖。

## Verification

- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/admin/test_catalog_lifecycle_service.py tests/integration/test_catalog_publish_eligibility.py -q` — 4 passed。
- `uv run ruff check app/admin app/nutrition app/planning tests/admin/test_catalog_lifecycle_service.py tests/integration/test_catalog_publish_eligibility.py` — passed。
- `uv run mypy app/admin app/nutrition app/planning` — passed, 23 source files。
- `uv run alembic heads` — only `0018 (head)`。

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-15 可消费 review/publish/disqualification 的严格 API 与 audit timeline。
- 后续浏览器验收必须以真实管理员会话和公开 API 走完整 lifecycle；本计划是无页面后端工作，未声称完成浏览器验收。

## Self-Check: PASSED

- 已确认 `0018_catalog_publication_eligibility.py`、两个 lifecycle 测试和三个任务提交存在。
