---
phase: 05-diet-planning-subgraph
plan: "07"
subsystem: planning-profile-api
tags: [python, fastapi, sqlalchemy, alembic, postgresql, pydantic, tdd]
requires:
  - phase: 05-01
    provides: "版本化规划 profile DTO、公式与目标政策常量"
  - phase: 01-authentication-foundation
    provides: "AuthenticatedPrincipal 与受保护 HTTP 路由模式"
provides:
  - "唯一、最小化、可软删除的 owner-bound PlanningProfile 权威存储"
  - "认证且 tenant-filtered 的 /api/v1/planning/profile CRUD"
  - "公开认证链验证的 A/B 用户隔离、输入闭合与删除后不可读取证据"
affects: [diet-planning-graph, planning-prefill, plans-h5, personal-profile]
tech-stack:
  added: []
  patterns: ["AuthenticatedPrincipal owner boundary", "tenant-filtered soft-delete query", "Service-owned commit and rollback", "fixed-scale Decimal API response"]
key-files:
  created:
    - backend/app/planning/models.py
    - backend/app/planning/repository.py
    - backend/app/planning/api.py
    - backend/migrations/versions/0010_planning_profiles.py
    - backend/tests/integration/test_planning_profile_api.py
  modified:
    - backend/app/planning/schemas.py
    - backend/app/planning/service.py
    - backend/app/main.py
key-decisions:
  - "Profile 只保存身高、体重、年龄、公式变体、活动、目标、目标速度和 policy/formula 版本；偏好始终属于 memory。"
  - "所有 profile 查询都在 SQL 中带 user_id 与 deleted_at predicate，missing/foreign/deleted 统一返回 404。"
  - "数值响应统一量化为数据库 Numeric(6,2) 的两位小数，避免首次保存与重读结果漂移。"
patterns-established:
  - "受保护 singleton 资源不接受客户端 user_id，API 只将 AuthenticatedPrincipal 交给 Service。"
  - "Profile 删除软删除后，Repository 与 planning prefill adapter 复用同一 active-row 过滤。"
requirements-completed: [PLN-01, PLN-06]
duration: 9min
completed: 2026-09-01
---

# Phase 5 Plan 07: 最小化、显式保存的个人资料持久化与公开 API Summary

**以 PostgreSQL 最小化资料表、tenant-filtered Service 和认证 CRUD 提供唯一可删除的规划 prefill 权威来源，偏好不再有第二个存储入口。**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-01T07:44:39Z
- **Completed:** 2026-09-01T07:53:17Z
- **Tasks:** 2/2
- **Files modified:** 17

## Accomplishments

- 新增 `planning_profiles` Alembic schema：DB range/enum check、每用户一个 active row 的 partial unique index、软删除和可逆 downgrade。
- 通过 `AuthenticatedPrincipal` 提供 `GET/PUT/PATCH/DELETE /api/v1/planning/profile`；API 不接受客户端 `user_id`，Service 负责事务，Repository 在 SQL 中证明所有权。
- profile 仅持久化生成与调整必需的身体与目标字段及规则版本；忌口、口味、原始反馈、Provider 数据和医疗叙述均被闭合 DTO 与 schema 排除。
- 使用真实 PostgreSQL、Mailpit、公开注册登录 A/B 链路覆盖 401、422、跨用户 404、软删除及删除后的 profile/prefill 不可读；并补充 fake repository Service 事务测试。

## Task Commits

Each task was committed atomically:

1. **Task 1: 写 owner-scoped profile CRUD 的 RED 集成合同** — `f6a2096` (`test`)
2. **Task 2: 实现最小化 profile 存储、API 与运行时注册** — `761107b` (`feat`)

## Files Created/Modified

- `backend/app/planning/models.py`、`repository.py` — 最小 profile ORM、active-row 过滤和 planning prefill 映射。
- `backend/app/planning/schemas.py`、`service.py`、`ports.py` — closed HTTP DTO、profile CRUD port 及 Service transaction boundary。
- `backend/app/planning/api.py`、`backend/app/main.py` — 已认证的 singleton profile endpoint 与 router 注册。
- `backend/migrations/versions/0010_planning_profiles.py` — 完整 upgrade/downgrade 的 PostgreSQL schema。
- `backend/tests/integration/test_planning_profile_api.py`、`backend/tests/planning/test_planning_profile_service.py` — 公开 A/B HTTPX 合同与 fake repository Service 合同。
- `backend/app/planning/README.md`、`backend/app/README.md`、`backend/migrations/versions/README.md`、`backend/tests/**/README.md` — 目录职责、允许依赖和文件索引。

## Decisions Made

- profile 数据最小化为 body/target 值与两个版本标识；偏好继续由 `PreferenceMemoryLedger`/Memory Service 管理。
- foreign、missing 与 soft-deleted profile 保持同一 404，避免 endpoint 成为 profile 存在性 oracle。
- `PUT` 是唯一的显式完整保存入口，`PATCH` 只能修改既有 active profile，删除后不能静默复活资料。

## Verification

- `APP_ENV=test ... uv run alembic downgrade 0009 && ... uv run alembic upgrade head` — passed。
- `APP_ENV=test ... uv run pytest tests/planning/test_planning_service.py tests/planning/test_planning_profile_service.py tests/integration/test_planning_profile_api.py tests/architecture/test_directory_contract.py -q` — 28 passed。
- `uv run ruff check app/planning app/main.py tests/planning/test_planning_profile_service.py tests/integration/test_planning_profile_api.py` — passed。
- `uv run mypy app/planning` — passed（7 source files）。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 固定首次保存与数据库重读的测量值精度**
- **Found during:** Task 2（实现最小化 profile 存储、API 与运行时注册）
- **Issue:** `PUT` 直接序列化请求 Decimal，而后续 `GET` 从 `Numeric(6,2)` 读取，导致同一资料出现 `170.0` 与 `170.00` 两种公开表示。
- **Fix:** `PlanningProfileResponse` 对身高和体重统一量化到两位小数，并将公开合同锁定为稳定表示。
- **Files modified:** `backend/app/planning/schemas.py`、`backend/tests/integration/test_planning_profile_api.py`
- **Verification:** 公开 CRUD 测试先暴露差异，修复后 profile Green 套件通过。
- **Committed in:** `761107b`（part of task commit）

**2. [Rule 2 - AGENTS.md 测试/目录合同] 补充 fake repository Service 证据与直接父目录索引**
- **Found during:** Task 2（实现最小化 profile 存储、API 与运行时注册）
- **Issue:** 计划只列出真实 HTTPX 合同，但项目硬规则还要求 Service 有 fake repository 单测，且新增文件必须同步目录及父目录 README 索引。
- **Fix:** 新增 profile Service fake-port 测试，并更新 planning、tests、migrations 与 app 的目录索引。
- **Files modified:** `backend/tests/planning/test_planning_profile_service.py`、相关 README。
- **Verification:** fake-port 测试、架构目录合同和完整 scoped regression 均通过。
- **Committed in:** `761107b`（part of task commit）

---

**Total deviations:** 2 auto-fixed（Rule 1: 1；Rule 2: 1）。
**Impact on plan:** 两项均是响应一致性或项目硬约束所需，没有引入额外业务能力。

## Issues Encountered

- 初次运行 `uv` 时受限沙箱无法访问用户级缓存；授权访问本机缓存后正常执行，不是项目代码问题。
- 全仓 `mypy` 仍报告 Phase 5 之前的 `records`、`memory` 与 `agent` 类型错误；本计划新增/修改的 `app/planning` 范围类型检查为 clean，未修改无关模块。

## Known Stubs

None — 扫描本计划新增或修改的 profile 代码与测试后，没有流向 UI 的空值、占位文案或 mock 数据源。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

规划图和 H5 资料页现在可将 `SqlAlchemyPlanningProfileRepository.get_planning_profile` 作为唯一 profile prefill 来源；删除后的 active-row filter 已阻止资料复活。后续图节点仍必须经其窄 tool/service 边界读取，不能直接查询 ORM。

## Self-Check: PASSED

- 已确认核心新文件 `backend/app/planning/{api.py,models.py,repository.py}`、migration、integration/service 测试存在。
- 已确认任务提交 `f6a2096` 与 `761107b` 存在于 Git 历史。

---
*Phase: 05-diet-planning-subgraph*
*Completed: 2026-09-01*
