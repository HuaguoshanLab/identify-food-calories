---
phase: 06-user-dashboard-admin
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, postgresql, dashboard, keyset-pagination, pydantic]
requires:
  - phase: 06-user-dashboard-admin
    provides: persisted meal local dates and revocable PlanningCompletionProjection eligibility
provides:
  - authenticated overview with current-day totals, seven persisted-local-date slots, and projection-backed target eligibility
  - tenant-filtered history grouped by local date with signed opaque keyset cursors
  - strict dashboard DTOs that omit target values whenever eligibility is false
affects: [06-04-records-page, dashboard-aggregation, user-dashboard]
tech-stack:
  added: []
  patterns: [consumer-owned narrow planning target port, persisted-snapshot aggregation, signed three-column keyset cursor]
key-files:
  created: [backend/app/dashboard/api.py, backend/app/dashboard/repository.py, backend/app/dashboard/schemas.py, backend/app/dashboard/service.py, docs/learning/phase-06-dashboard-read-api.md]
  modified: [backend/app/main.py, backend/app/dashboard/ports.py, backend/tests/dashboard/test_dashboard_service.py, backend/tests/integration/test_dashboard_repository.py, backend/tests/unit/test_dashboard_api.py]
key-decisions:
  - "Dashboard targets are only obtained from the injected PlanningCompletionTargetPort; dashboard service and repository never read PlanningProfile."
  - "History cursor signs the persisted consumed_local_date, consumed_at, and UUID tiebreaker with the application secret."
patterns-established:
  - "Dashboard SQL proves user ownership, excludes soft deletes, and requires persisted local dates before aggregation or pagination."
  - "Public DTOs use extra=forbid and response_model_exclude_none so unavailable target values cannot leak as null placeholders."
requirements-completed: [UI-02]
duration: 13min
completed: 2026-09-02
---

# Phase 06 Plan 02: Projection-backed Dashboard Read API Summary

**用户看板现在从已确认餐食快照提供今日、七日和历史事实，并只通过可撤销的完成计划投影显示目标区间。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-02T10:30:52Z
- **Completed:** 2026-09-02T10:43:00Z
- **Tasks:** 2/2
- **Files modified:** 24

## Accomplishments

- 注册 `/api/v1/dashboard/overview` 与 `/api/v1/dashboard/history`；overview 以七个持久化本地日槽位返回今日 totals、餐数及窄投影目标资格。
- Repository 从 SQL 起点执行 `user_id`、未软删和 `consumed_local_date` 过滤；history 以 local date、时间和 UUID 三元 DESC keyset 分页。
- 目标资格为 false 时响应结构上省略目标值；cursor 使用应用密钥签名，篡改或非法范围返回 422。
- 提供 fake service、HTTPX 与真实 PostgreSQL 回归证据，并补充中文请求链路、测试和常见错误教学材料。

## Verification

- `cd backend && uv run ruff check app/dashboard app/main.py tests/dashboard/test_dashboard_service.py tests/integration/test_dashboard_repository.py tests/integration/test_dashboard_overview_projection.py tests/unit/test_dashboard_api.py` — passed。
- `cd backend && uv run mypy app/dashboard` — passed，6 个 source file 无问题。
- `cd backend && uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/dashboard/test_dashboard_service.py tests/integration/test_dashboard_repository.py tests/integration/test_dashboard_overview_projection.py tests/unit/test_dashboard_api.py -q` — 7 passed；只有既有 Starlette 422 deprecation warning。
- `cd backend && uv run pytest tests/architecture -q` — 1 passed、1 failed；失败是计划外的 `backend/tests/README.md` 缺少既有 `agent/` 目录索引，已写入 `deferred-items.md`。

## Task Commits

1. **Task 1: 编写 projection-backed overview/history cursor RED 契约** — `6f9fb1b` (`test`)
2. **Task 2: 注入 completion projection 并实现 tenant-filtered 聚合 API** — `5315188` (`feat`)

## Files Created/Modified

- `backend/app/dashboard/{api,schemas,repository,service}.py` — 严格 HTTP DTO、认证 read API、SQL 聚合和签名 cursor。
- `backend/app/main.py` — 注册 dashboard router。
- `backend/tests/dashboard/test_dashboard_service.py` — fake repository/Port 的 seven-day、无资格与 cursor 契约。
- `backend/tests/integration/test_dashboard_repository.py`、`test_dashboard_overview_projection.py` — PostgreSQL tenant、软删、UUID tiebreaker 和 projection 降级证据。
- `docs/learning/phase-06-dashboard-read-api.md` — 看板投影边界、请求流、测试命令及典型错误中文教学。

## Decisions Made

- Dashboard 只注入 `PlanningCompletionTargetPort`；`dashboard/service.py` 和 `dashboard/repository.py` 不导入或查询 `PlanningProfile`，从而不可能按 profile 猜测目标。
- Cursor 使用服务端签名而非 offset 或明文 JSON，保持新增记录时的稳定分页，并拒绝篡改位置。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression] 修正真实 PostgreSQL fixture 的外键与唯一约束关系**
- **Found during:** Task 2
- **Issue:** 首轮集成测试为多个餐食复用同一 run，违反 `MealRecord` 的 `(user_id, source_run_id)` 唯一约束；fixture 也未先创建 User/Thread/Run 外键行。
- **Fix:** 为每条 fixture 记录创建合规的 owner-bound User、Thread 和独立 Run。
- **Files modified:** `backend/tests/integration/test_dashboard_repository.py`、`backend/tests/integration/test_dashboard_overview_projection.py`
- **Verification:** guarded PostgreSQL 运行 7 passed。
- **Committed in:** `5315188`

**2. [Rule 2 - Required Documentation] 补齐目录索引与 Phase 6 中文教学材料**
- **Found during:** Task 2
- **Issue:** 根级与后端 `AGENTS.md` 要求新增目录文件同步更新直接父级索引，且每个后端阶段必须交付中文教学文档；原计划文件清单未列出 integration/docs 索引和教学材料。
- **Fix:** 更新 app、dashboard、tests、integration 与 docs 索引，并新增 dashboard read API 教学文档。
- **Files modified:** `backend/tests/integration/README.md`、`docs/README.md`、`docs/learning/README.md`、`docs/learning/phase-06-dashboard-read-api.md` 及关联 README。
- **Verification:** README 内容与实际文件路径一致；dashboard 模块 Ruff/mypy 通过。
- **Committed in:** `5315188`

---

**Total deviations:** 2 auto-fixed（1 regression、1 required documentation）。
**Impact on plan:** 均为真实数据库正确性和仓库硬性文档契约所必需；未扩展产品范围。

## Issues Encountered

- 架构 README 合同发现 `backend/tests/README.md` 漏列一个本计划之前已存在的 `agent/` 目录；因与 dashboard 无关，未越界修改，已记录在 phase `deferred-items.md`。

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-04 可直接消费 `/api/v1/dashboard/overview` 的 strict `today`、`week` 与 `target_eligibility`，以及 `/history` 的 opaque `next_cursor`；不得调用 profile API 推导目标。
- 真实浏览器验收留给前端接入计划；本计划仅交付后端 read contract。

## Self-Check: PASSED

- 已确认 `backend/app/dashboard/api.py` 和 `backend/app/dashboard/repository.py` 存在。
- 已确认 `6f9fb1b` 与 `5315188` 均在 Git 历史中存在。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
