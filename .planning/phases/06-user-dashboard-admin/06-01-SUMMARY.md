---
phase: 06-user-dashboard-admin
plan: "01"
subsystem: database
tags: [fastapi, sqlalchemy, alembic, postgresql, zoneinfo, meal-records]
requires:
  - phase: 05-diet-planning-subgraph
    provides: confirmed meal records and the existing linear 0011/0012 migrations
provides:
  - persisted submitted-IANA-timezone and local-date attribution for meal records
  - one-time, tenant-scoped historical backfill with audit evidence
  - a single Alembic successor migration at revision 0013
affects: [06-02-dashboard-api, 06-04-records-page, dashboard-aggregation]
tech-stack:
  added: []
  patterns: [ZoneInfo validation in service transactions, persisted local-date projections, PostgreSQL audit-backed backfill]
key-files:
  created: [backend/migrations/versions/0013_dashboard_time_attribution.py, backend/tests/integration/test_record_local_time_attribution.py]
  modified: [backend/app/records/service.py, backend/app/records/api.py, backend/app/records/models.py]
key-decisions:
  - "用户确认的 dashboard 时区只是一种当前统计口径，不表示恢复历史所在地。"
  - "保存和编辑使用请求提交的 IANA 时区，将 consumed_at 固化为不可漂移的 local date。"
  - "Phase 5 已占用 0011/0012，因此本计划经授权采用 0013 并接在 0012 后。"
patterns-established:
  - "历史统计投影由 Service 在同一业务事务内持久化，Repository 只做 tenant-filtered query/add/flush。"
  - "一次性用户确认同时写偏好、仅本人未归属记录的 backfill 与审计行；唯一约束处理竞态。"
requirements-completed: [UI-02]
duration: 14min
completed: 2026-09-02
---

# Phase 06 Plan 01: Dashboard Time Attribution Summary

**以提交 IANA 时区冻结餐食本地日，并以用户一次性确认和审计回填既有记录的看板统计事实。**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-02T08:54:00Z
- **Completed:** 2026-09-02T09:08:24Z
- **Tasks:** 3/3
- **Files modified:** 18

## Accomplishments

- 新建和编辑餐食必须提交可由 `ZoneInfo` 解析的 IANA 时区；Service 基于 `consumed_at` 持久化 `consumed_time_zone`、`consumed_local_date` 与来源。
- 增加受认证保护的一次性统计时区确认 API；只回填当前用户未归属、未软删的历史记录，并写入单独审计证据，绝不表述为历史所在地恢复。
- 真实 PostgreSQL 测试覆盖上海跨午夜、历史回填、跨租户隔离和已有餐食 API 回归；Alembic 只保留 `0013` 单 head。

## Verification

- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/records/test_record_service.py tests/integration/test_record_local_time_attribution.py tests/integration/test_meal_records.py tests/unit/test_meal_record_api.py -q` — 13 passed。
- `uv run ruff check app/records tests/records/test_record_service.py tests/integration/test_record_local_time_attribution.py tests/integration/test_meal_records.py tests/unit/test_meal_record_api.py` — passed。
- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run alembic upgrade head`、`alembic heads`、`alembic history --verbose` — passed，唯一 head 为 `0013`，前驱为 `0012`。

## Task Commits

1. **Task 1: 写确认时区、本地日与回填 RED 契约** — `5464ab9` (`test`)
2. **Task 2: 持久化统计口径和餐食归属** — `1b980f6` (`feat`)
3. **Task 3: 固定 0011 的线性迁移前驱** — `3823739` (`chore`)

## Files Created/Modified

- `backend/migrations/versions/0013_dashboard_time_attribution.py` — 本地日字段、统计时区确认与回填审计 schema。
- `backend/app/records/models.py` — 餐食归属字段和确认/审计 ORM。
- `backend/app/records/service.py` — IANA 校验、日期派生、一次性回填和并发冲突映射。
- `backend/app/records/api.py` — 受保护的时区确认 endpoint 与 400/409 HTTP 语义。
- `backend/tests/integration/test_record_local_time_attribution.py` — 真实 PostgreSQL 的回填与租户隔离证明。

## Decisions Made

- 用户确认的时区是“当前用户确认的统计口径”；DTO、模型名和文案均不声称能恢复历史所在地。
- `consumed_at` 是归档事实，`created_at` 不参与任何本地日计算；补记因此归属真实用餐日期。
- 确认 preference 与审计表均由唯一 `user_id` 约束保证一次性语义，Service 将并发唯一冲突映射为可解释的 409。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 修正已被 Phase 5 占用的迁移编号**
- **Found during:** Task 2
- **Issue:** 现有仓库已提交 `0011_controlled_recipes.py` 和 `0012_activate_controlled_recipes_v2.py`；按原计划再创建 `0011` 会产生 duplicate revision 和 multiple heads。
- **Fix:** 经用户授权，创建 `0013_dashboard_time_attribution.py`，显式以 `0012` 为 `down_revision`，并保留单一线性链。
- **Files modified:** `backend/migrations/versions/0013_dashboard_time_attribution.py`、迁移目录 README。
- **Verification:** 隔离 PostgreSQL `alembic upgrade head`、`heads` 和 `history --verbose` 均通过，唯一 head 为 `0013`。
- **Committed in:** `1b980f6`、`3823739`

**2. [Rule 1 - Regression] 更新既有餐食 API 集成测试的必填时区请求**
- **Found during:** Task 2
- **Issue:** 新 API 契约要求保存/编辑餐食提交 IANA 时区，已有真实 PostgreSQL 回归测试仍发送旧 payload。
- **Fix:** 令回归测试明确提交 `UTC`，继续验证原有保存、幂等、编辑、删除与跨租户链路。
- **Files modified:** `backend/tests/integration/test_meal_records.py`
- **Verification:** 真实 PostgreSQL 回归测试通过。
- **Committed in:** `1b980f6`

---

**Total deviations:** 2 auto-fixed（1 blocking、1 regression）。
**Impact on plan:** 未扩大产品范围；迁移顺延是避免破坏既有 schema 历史所必需的修复。

## Issues Encountered

- `uv run mypy app/records` 在未修改的 `_validated_snapshot` 动态字典逻辑报出四个既有类型错误；已记录于 `deferred-items.md`，不影响本计划的测试、迁移或静态检查结果。

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-02 可使用 `MealRecord.consumed_local_date` 进行服务器端看板聚合；历史记录需先通过统计时区确认 API 回填。
- 后续 Phase 6 迁移必须从 `0013` 继续顺延，不能复用计划中已过期的 revision 编号。

## Self-Check: PASSED

- 已确认 `backend/migrations/versions/0013_dashboard_time_attribution.py` 与 `backend/tests/integration/test_record_local_time_attribution.py` 存在。
- 已确认 `5464ab9`、`1b980f6` 与 `3823739` 均在 Git 历史中存在。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
