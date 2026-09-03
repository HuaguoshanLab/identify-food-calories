---
phase: 06-user-dashboard-admin
plan: 18
subsystem: admin-api-database
tags: [fastapi, sqlalchemy, postgresql, percentile_cont, keyset, rbac, httpx]
requires:
  - phase: 06-11
    provides: database-authoritative administrator RBAC and audit boundary
  - phase: 06-14
    provides: admin repository/service/API layering convention
  - phase: 06-16
    provides: AgentRun and AgentInvocation runtime ledger projections
provides:
  - shared terminal UTC predicate for administrator run metrics and keyset listing
  - PostgreSQL P50/P95/cost aggregates and signed finished-at/UUID run cursors
  - strict, minimum run and invocation evidence API projections
affects: [06-19, 06-20, admin-frontend, agent-runtime]
tech-stack:
  added: []
  patterns: [shared terminal query predicate, PostgreSQL percentile_cont, signed keyset cursor, allowlisted ledger DTO]
key-files:
  created: [backend/tests/admin/test_admin_run_service.py, backend/tests/integration/test_admin_run_metrics_repository.py, backend/tests/unit/test_admin_run_api.py]
  modified: [backend/app/admin/schemas.py, backend/app/admin/ports.py, backend/app/admin/repository.py, backend/app/admin/service.py, backend/app/admin/api.py]
key-decisions:
  - "metrics 与列表从同一个 AgentRun finished_at + terminal-status SQL predicate 派生，不能独立定义窗口。"
  - "管理员 run cursor 使用 HMAC 签名的 finished_at/UUID keyset，而不是 offset 或可伪造位置。"
  - "run 与 invocation DTO 仅允许计数、状态、版本、成本、失败码、节点和安全 digest；不返回用户或 Provider 原文。"
patterns-established:
  - "管理员可读 ledger 路径：数据库当前角色校验 → repository 白名单查询 → strict Pydantic DTO。"
  - "PostgreSQL percentile_cont 聚合与 keyset list 必须调用同一受限 terminal predicate。"
requirements-completed: [ADM-03]
duration: 24min
completed: 2026-09-03
---

# Phase 06 Plan 18: Admin Run Observability Summary

**管理员现可按统一 UTC 终态口径查看运行数、失败率、P50/P95、费用和签名游标分页的最小化 run/invocation 证据。**

## Performance

- **Duration:** 24 min
- **Started:** 2026-09-03T11:48:00Z
- **Completed:** 2026-09-03T12:11:58Z
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments

- `GET /api/v1/admin/runs/metrics` 与 `GET /api/v1/admin/runs` 复用 `finished_at` + terminal status + 相同过滤 SQL predicate；指标由 PostgreSQL 计算 P50/P95、失败率和 Decimal 成本。
- run list 使用 HMAC 签名 `finished_at/UUID` keyset cursor，过滤项限制为 UTC 时间、终态状态、graph version、provider:model、失败 node/code。
- `GET /api/v1/admin/runs/{id}` 仅返回运行和 invocation 的白名单字段；DTO 明确排除 email、原始文本/图片、Provider request/body、Graph State、reasoning、key 与 endpoint。
- 通过 fake service、HTTPX 合约和真实隔离 PostgreSQL 覆盖 RBAC、边界窗口、percentile、cost、分页以及敏感字段扫描。

## Task Commits

1. **Task 1: 写 metrics/runs RED 契约** — `db8cde9` (`test`)
2. **Task 2: 实现 metrics/list/detail API** — `670a681` (`feat`)

## Files Created/Modified

- `backend/app/admin/schemas.py` — bounded run filters、metrics、page、run/invocation 最小 DTO。
- `backend/app/admin/ports.py` — admin repository 的 metrics/list/detail capability contract。
- `backend/app/admin/repository.py` — 共用 terminal predicate、PostgreSQL percentile SQL、keyset 和 invocation 读取。
- `backend/app/admin/service.py` — 当前 DB-RBAC、HMAC cursor 和 DTO 白名单映射。
- `backend/app/admin/api.py` — `/runs/metrics`、`/runs`、`/runs/{id}` 的安全 HTTP 映射。
- `backend/tests/{admin,integration,unit}/test_admin_run_*.py` — RED/HTTPX/真实 PostgreSQL 合约。

## Decisions Made

- metrics/list 复用同一 predicate，防止 overview 和 runs 页面因终态或 UTC 边界不一致产生互相矛盾的数据。
- 详情按 invocation 白名单映射，运行账本中未来可能出现的字段不会自动穿透到后台响应。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test fixture bug] 分层插入 AgentThread/AgentRun 的外键父记录**
- **Found during:** Task 2
- **Issue:** 真实 PostgreSQL 测试将独立 ORM 实体同时 flush，SQLAlchemy 无 relationship 可据以排序，导致 thread/run 外键违反。
- **Fix:** 先 flush User，再 flush AgentThread，最后写入 AgentRun。
- **Files modified:** `backend/tests/integration/test_admin_run_metrics_repository.py`
- **Verification:** 隔离 PostgreSQL focused suite 5 passed。
- **Committed in:** `670a681`

**2. [Rule 2 - Missing critical] 在 detail 中添加 invocation 白名单投影**
- **Found during:** Task 2
- **Issue:** 仅返回 run 计数会遗漏管理员诊断所需的失败节点/工具 evidence，且容易诱使前端索取原始 ledger。
- **Fix:** 增加 invocation 的 node/status/attempt/cost/failure/safe digest DTO 与 Repository capability；不读取任何 raw provider 或 state 数据。
- **Files modified:** `backend/app/admin/{schemas,ports,repository,service}.py`
- **Verification:** focused service/HTTPX/PostgreSQL suite 和 Ruff 通过。
- **Committed in:** `670a681`

---

**Total deviations:** 2 auto-fixed（Rule 1: 1，Rule 2: 1）。
**Impact on plan:** 都是 PostgreSQL 测试真实性和最小化诊断合同所必需；未新增依赖或扩大数据暴露面。

## Issues Encountered

- 直接运行 pytest 被项目的 test database fail-closed 配置拒绝；改用 `tests/run_pg.py` wrapper 后，隔离 PostgreSQL 验证通过。
- `uv run mypy app/admin` 仍因既有 `app/memory/providers.py` 的 4 个类型错误失败；该文件未被本计划修改，focused tests 与 Ruff 均通过。

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-19 可直接消费 strict metrics/list/detail contracts，为 runs 页面保留同一 UTC filter 与 opaque cursor。
- 06-20 可使用公开管理员 API 对 metrics、filters 和 detail 执行真实 E2E；不得绕过 DB-RBAC 或请求非白名单 ledger 字段。

## Self-Check: PASSED

- 已确认 `backend/app/admin/repository.py`、`backend/app/admin/api.py` 和三个 run contract 测试文件存在。
- 已确认 `db8cde9` 与 `670a681` 位于 Git 历史。
- 隔离 PostgreSQL focused suite：5 passed；Ruff：All checks passed。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
