---
phase: 06-user-dashboard-admin
plan: "03"
subsystem: database
tags: [fastapi, sqlalchemy, alembic, postgresql, diet-planning, dashboard]
requires:
  - phase: 06-user-dashboard-admin
    provides: frozen local-date facts and the unique 0013 migration head
provides:
  - revocable, owner-bound validated planning completion projections
  - a dashboard target eligibility port with no profile ORM exposure
  - profile-revision invalidation and cross-user database constraints
affects: [06-02-dashboard-api, 06-04-records-page, dashboard-aggregation]
tech-stack:
  added: []
  patterns: [validated completion projection, composite tenant foreign keys, fail-closed Agent completion writer]
key-files:
  created: [backend/migrations/versions/0014_planning_completion_projection.py, backend/app/dashboard/ports.py, backend/tests/integration/test_planning_completion_projection.py]
  modified: [backend/app/planning/models.py, backend/app/planning/service.py, backend/app/planning/repository.py, backend/app/agent/service.py]
key-decisions:
  - "Dashboard target eligibility is granted only by an unrevoked projection created from a validated persisted-profile planning run."
  - "Profile mutation increments a revision and revokes the active target projection in the same transaction."
  - "0014 is the only valid successor to Phase 06-01's 0013 migration; 0011/0012 remain Phase 5 history."
patterns-established:
  - "Agent completion receives a narrow planning writer port; it never reads planning ORM directly."
  - "Composite user/profile/thread/run foreign keys prevent an otherwise valid ID from crossing tenants."
requirements-completed: [UI-02]
duration: 16min
completed: 2026-09-02
---

# Phase 06 Plan 03: 可撤销完成计划投影 Summary

**已校验且持久化个人资料的规划完成会原子写入可撤销投影，dashboard 只能读取资格、目标区间和版本。**

## Performance

- **Duration:** 16 min
- **Started:** 2026-09-02T09:43:52Z
- **Completed:** 2026-09-02T09:59:37Z
- **Tasks:** 3/3
- **Files modified:** 25

## Accomplishments

- 新增 `PlanningCompletionProjection`、`0014` Alembic migration 以及复合外键，数据库同时约束 user、profile、thread 和 run 的同租户归属。
- `AgentService` 仅在 `completed_validated` 的持久化 profile 规划路径中，通过窄 writer port 与 run 完成状态同一事务写入投影；写入失败时安全失败，不授予资格。
- profile 更新或软删除会增加 revision 并在同一事务撤销投影；dashboard target port 只返回 `eligible`、目标区间与版本，不读取 `PlanningProfile` ORM。

## Verification

- `cd backend && uv run python tests/run_pg.py --env-file .env.test.example -- uv run alembic upgrade head` — passed。
- `cd backend && uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/planning/test_completion_projection_service.py tests/integration/test_planning_completion_projection.py tests/dashboard/test_dashboard_target_port.py tests/integration/test_diet_planning_agent_api.py -q` — 11 passed。
- `cd backend && uv run ruff check app/planning app/dashboard app/agent tests/planning/test_completion_projection_service.py tests/integration/test_planning_completion_projection.py tests/dashboard/test_dashboard_target_port.py tests/integration/test_diet_planning_agent_api.py` — passed。
- `cd backend && uv run python tests/run_pg.py --env-file .env.test.example -- uv run alembic heads` — `0014 (head)`，唯一 head。
- `cd backend && uv run python tests/run_pg.py --env-file .env.test.example -- uv run alembic history --verbose` — 验证 `0014 → 0013 → 0012` 的单一线性链。

## Task Commits

1. **Task 1: 写资格生产、撤销与窄 port RED 测试** — `1eac323` (`test`)
2. **Task 2: 实现可撤销 projection 和最小读取 port** — `be119cb` (`feat`)
3. **Task 3: 固定线性迁移前驱** — `0b948da` (`chore`)

## Files Created/Modified

- `backend/migrations/versions/0014_planning_completion_projection.py` — 以 `0013` 为唯一前驱建立 projection、revision 与复合租户外键。
- `backend/app/planning/models.py`、`ports.py`、`repository.py`、`service.py` — 规划投影的 ORM、窄 Port、tenant-filtered 查询、生产和撤销事务。
- `backend/app/dashboard/ports.py` — dashboard 可消费的严格资格 DTO；无资格时结构上不可能包含目标数值。
- `backend/app/agent/service.py`、`api.py` — 在完成已校验规划时注入 writer 并与 run 状态原子提交。
- `backend/tests/planning/test_completion_projection_service.py`、`backend/tests/integration/test_planning_completion_projection.py` — fake-service 与真实 PostgreSQL 的撤销、回滚、孤儿和跨用户约束证据。

## Decisions Made

- `save_profile=false` 的完成规划仍可完成，但不会生成目标资格投影；没有持久化完整资料就不能向 dashboard 授予目标数据。
- projection 固化完成时确定性计算出的 ranges；读取端还同时检查 profile revision、软删除状态、run 状态及 tenant joins。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 顺延已过期的迁移编号**
- **Found during:** Task 2
- **Issue:** 原计划要求创建 `0012_planning_completion_projection.py`，但 Phase 5 已占用 `0011`/`0012`，且 06-01 已合法占用 `0013`；复用会产生 duplicate revision/multiple heads。
- **Fix:** 按用户授权创建 `0014_planning_completion_projection.py`，明确 `down_revision = "0013"`。
- **Files modified:** `backend/migrations/versions/0014_planning_completion_projection.py`、migration README。
- **Verification:** 隔离 PostgreSQL 的 `alembic upgrade head`、`heads` 与 `history --verbose` 均通过，唯一 head 为 `0014`。
- **Committed in:** `be119cb`、`0b948da`

**2. [Rule 2 - Missing Critical] 接通 validated completion 的真实生产事务**
- **Found during:** Task 2
- **Issue:** 计划列出的 planning/dashboard 文件不包含唯一掌握 validated completion、run、thread 和 user 的 `agent/service.py`。不扩展该入口只会留下永远无法触发的投影。
- **Fix:** 经用户确认，将 `PlanningCompletionProjectionWriter` 注入 AgentService，仅对已保存 profile 的 validated planning completion 写投影；失败 fail closed。
- **Files modified:** `backend/app/agent/service.py`、`backend/app/agent/api.py`、`backend/tests/integration/test_diet_planning_agent_api.py` 及关联 README。
- **Verification:** 真实公开 diet-planning API 回归确认 completed run 产生 owner-bound projection；未保存 profile 的完成规划不产生投影。
- **Committed in:** `be119cb`

---

**Total deviations:** 2 auto-fixed（1 blocking、1 missing critical）。
**Impact on plan:** 两项均为防止数据库分叉和死投影的正确性修复；没有扩大产品功能范围。

## Issues Encountered

- 初次直接运行 pytest 未配置 `APP_ENV=test`；已使用项目规定的 `tests/run_pg.py --env-file .env.test.example` 执行真实 PostgreSQL 测试。
- 首轮集成 fixture 未按外键层级提交 user/thread/run，测试立即暴露该错误；修正 fixture 顺序后，外键约束与跨租户拒绝均通过。

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-02 可以将 `SqlAlchemyPlanningProfileRepository.get_dashboard_target_eligibility` 注入 dashboard service；不得查询 `PlanningProfile` 或自行计算目标。
- 后续 Phase 6 migration 必须接续 `0014`，不得创建或复用旧 revision。

## Self-Check: PASSED

- 已确认 `backend/migrations/versions/0014_planning_completion_projection.py`、`backend/app/dashboard/ports.py` 与 projection 集成测试均存在。
- 已确认 `1eac323`、`be119cb` 和 `0b948da` 均在 Git 历史中存在。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
