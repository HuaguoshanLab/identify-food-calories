---
phase: 06-user-dashboard-admin
plan: 11
subsystem: admin-api
tags: [fastapi, postgresql, sqlalchemy, alembic, rbac, audit]
requires:
  - phase: 06-07
    provides: authorized 0015 Alembic migration predecessor
  - phase: 06-08
    provides: current Phase 06 test-directory index conventions
provides:
  - PostgreSQL-authoritative administrator role recheck for every admin endpoint
  - append-only generic command audit evidence with safe scalar diffs
  - read-only signed-cursor audit timeline with allowlisted projections
affects: [admin-api, admin-frontend, catalog-commands, agent-run-operations]
tech-stack:
  added: []
  patterns: [endpoint-local-db-rbac, single-transaction-audit, signed-keyset-pagination, append-only-postgresql-trigger]
key-files:
  created: [backend/migrations/versions/0016_admin_audit_foundation.py, backend/tests/admin/test_admin_rbac_audit_service.py, backend/tests/admin/test_admin_audit_service.py]
  modified: [backend/app/admin/service.py, backend/app/admin/repository.py, backend/app/admin/api.py, backend/app/admin/models.py]
key-decisions:
  - "Admin authorization always reloads the active role from PostgreSQL; JWT claims only authenticate a session."
  - "Generic audit evidence accepts only server-computed scalar field diffs and exposes an explicit response whitelist."
  - "The authorized migration is 0016 with 0015 as its sole predecessor, preserving the one-head chain."
patterns-established:
  - "Admin routes call require_role before domain reads, then services own commit/rollback boundaries."
  - "Audit timeline cursors sign the UTC timestamp and UUID tiebreaker before repository keyset lookup."
requirements-completed: [ADM-01, ADM-05]
duration: 6min
completed: 2026-09-02
---

# Phase 06 Plan 11: DB-RBAC and Admin Audit Foundation Summary

**后台 API 以 PostgreSQL 当前 active admin role 为唯一授权真相，并提供不可变命令审计和最小化的签名 cursor 查询。**

## Performance

- **Duration:** 6 min
- **Started:** 2026-09-02T11:23:45Z
- **Completed:** 2026-09-02T11:30:03Z
- **Tasks:** 3/3
- **Files modified:** 16

## Accomplishments

- `/api/v1/admin/probe` 和新的 `/api/v1/admin/audit` 都先通过会话认证，再从 PostgreSQL 重读 active admin role；降级后的旧 token 不会继续被授权。
- 新增 `AdminAuditEvent`、数据库 check/index 和 PostgreSQL trigger，禁止更新或删除通用审计证据；角色提升也在同一事务写入通用事件。
- 审计 API 只返回 actor 标识、时间、action/object、reason、字段级 diff、关联版本和 command key；不暴露邮箱、密钥、原图、Provider body 或 Graph State。

## Task Commits

1. **Task 1: 写 DB-authoritative RBAC/audit query RED 测试** — `fb2c902` (test)
2. **Task 2: 实现 admin 角色守卫、通用审计和 audit API** — `15d5dcd` (feat)
3. **Task 3: 固定线性迁移前驱** — `4106757` (chore)

## Files Created/Modified

- `backend/app/admin/models.py` — 角色审计之外的通用、最小化 `AdminAuditEvent` ORM。
- `backend/app/admin/service.py` — DB-RBAC、原子命令审计、敏感字段拒绝和签名 cursor 投影。
- `backend/app/admin/repository.py` — flush-only event insert 和稳定 time/UUID keyset 查询。
- `backend/app/admin/api.py` — endpoint-local RBAC 与只读 `/audit` HTTP 合同。
- `backend/migrations/versions/0016_admin_audit_foundation.py` — append-only table、索引和阻止 UPDATE/DELETE 的 PostgreSQL trigger。
- `backend/tests/admin/`、`backend/tests/unit/test_admin_*_api.py`、`backend/tests/integration/test_admin_audit_repository.py` — Service、HTTP 和真实 PostgreSQL 证据。

## Verification

- `uv run pytest tests/admin/test_admin_rbac_audit_service.py tests/admin/test_admin_audit_service.py tests/unit/test_admin_rbac_api.py tests/unit/test_admin_audit_api.py -q` — PASS（6 passed）。
- `APP_ENV=test ... uv run pytest tests/integration/test_admin_audit_repository.py tests/integration/test_admin_audit.py -q` — PASS（5 passed）。
- `uv run ruff check app/admin tests/admin tests/unit/test_admin_rbac_api.py tests/unit/test_admin_audit_api.py tests/integration/test_admin_audit_repository.py` — PASS。
- `uv run mypy app/admin` — PASS（8 source files）。
- `uv run alembic heads` — PASS（唯一 `0016 (head)`）；隔离 `food_agent_test` 已成功 upgrade 到 head。

## Decisions Made

- JWT 中的 role claim 不被信任为最终授权，所有 admin endpoint 都使用数据库当前 role。
- 审计差异限定为浅层标量，并拒绝 email、token、secret、image、Provider、State 与 prompt 等敏感字段名。
- `0014`、`0015` 已被先前依赖计划使用；依已获授权继续使用 `0016_admin_audit_foundation.py`，`down_revision = "0015"`。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 在数据库强制通用审计 append-only**
- **Found during:** Task 2
- **Issue:** 只把事件称为“immutable”却没有数据库层 UPDATE/DELETE 防护，任何有表权限的错误路径仍可篡改或抹除证据。
- **Fix:** migration 创建 PostgreSQL trigger，拒绝 `admin_audit_events` 的 UPDATE 与 DELETE。
- **Files modified:** `backend/migrations/versions/0016_admin_audit_foundation.py`
- **Verification:** 隔离 PostgreSQL migration upgrade 成功，focused integration tests 通过。
- **Committed in:** `4106757`

**2. [Rule 2 - Missing Critical] 阻断敏感字段进入审计 diff**
- **Found during:** Task 2
- **Issue:** 通用 JSON diff 若接受任意字段，后续命令可意外写入邮箱、token、密钥、图像、Provider 或 Graph State。
- **Fix:** Service 只允许浅层 scalar diff，并拒绝敏感字段名；新增 service 契约测试。
- **Files modified:** `backend/app/admin/service.py`, `backend/tests/admin/test_admin_rbac_audit_service.py`
- **Verification:** 6 个 focused Service/API tests 通过。
- **Committed in:** `15d5dcd`

**3. [Rule 3 - Blocking] 沿已授权链采用 migration 0016**
- **Found during:** Task 3
- **Issue:** 计划的 `0014` 已由 06-03 占用，`0015` 已由 06-07 占用；重用编号会产生冲突或多 head。
- **Fix:** 创建 `0016_admin_audit_foundation.py`，唯一前驱设为 `0015`，并同步迁移目录索引。
- **Files modified:** `backend/migrations/versions/0016_admin_audit_foundation.py`, `backend/migrations/README.md`, `backend/migrations/versions/README.md`
- **Verification:** `alembic heads` 只报告 `0016 (head)`，隔离测试库升级成功。
- **Committed in:** `4106757`

---

**Total deviations:** 3 auto-fixed（Rule 2: 2，Rule 3: 1）。
**Impact on plan:** 都是审计不可篡改、敏感数据最小化和 Alembic 单 head 的正确性要求，没有扩大产品范围。

## Issues Encountered

- 初次运行 `uv` 因 sandbox 无权读取共享依赖缓存而失败；获得受控缓存访问后，所有计划验证均完成。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 后续 catalog、run 与 config command 可在 Service 事务内调用 `record_command_audit`，复用 DB-RBAC、safe diff 和唯一 command key。
- admin frontend 可消费 `/api/v1/admin/audit` 的最小化 response，不需要也不得请求原始审计 payload。

## Self-Check: PASSED

- 已确认 `backend/migrations/versions/0016_admin_audit_foundation.py` 与 `backend/app/admin/service.py` 存在。
- 已确认 `fb2c902`、`15d5dcd` 与 `4106757` 均在 Git 历史中存在。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
