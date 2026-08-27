---
phase: 01-engineering-auth-foundation
plan: 12
subsystem: authorization
tags: [fastapi, postgresql, sqlalchemy, alembic, rbac, audit, cli]

requires:
  - phase: 01-engineering-auth-foundation/01-05
    provides: 已签名且 session-bound 的 Bearer 协议，以及按数据库重读身份的认证 Service
  - phase: 01-engineering-auth-foundation/01-10
    provides: 可撤销 session family 与数据库会话校验
provides:
  - 会话验证后按 PostgreSQL active role 重读的 `/api/v1/admin/probe`
  - 角色变化与 `admin_role_audit` 同事务提交的管理员 bootstrap/promote CLI
  - 真实 PostgreSQL RBAC、审计字段、失败回滚与 migration 链验证
affects: [phase-06-admin-frontend, rbac, audit-log, admin-operations]

tech-stack:
  added: []
  patterns: [database-authoritative-rbac, transaction-scoped-postgresql-advisory-lock, atomic-role-audit, explicit-admin-cli]

key-files:
  created: [backend/app/admin/models.py, backend/app/admin/service.py, backend/app/admin/api.py, backend/app/admin/cli.py, backend/migrations/versions/0003_admin_audit.py, backend/tests/integration/test_admin_audit.py]
  modified: [backend/app/main.py, backend/tests/integration/test_auth_migration.py, backend/README.md]

key-decisions:
  - "admin probe 先沿用既有 session-bound Bearer 验证，再按 subject 从 PostgreSQL 读取 active role；JWT role claim 不参与最终授权。"
  - "首次 bootstrap 使用 system:bootstrap actor；后续提升只接受已验证、active 的现有 admin actor，拒绝自我提升和空 reason。"
  - "角色提升和 audit 在同一 Session transaction 提交；事务级 PostgreSQL advisory lock 串行化首次管理员的 check-then-promote 判定。"

patterns-established:
  - "Admin API 只处理 HTTP/Bearer 语义，AdminService 通过 Repository port 执行角色规则、行锁和事务。"
  - "任何受控角色变化都必须写 actor、target、before/after、occurred_at 与 trimmed non-empty reason。"

requirements-completed: [AUTH-05, ARC-02, ARC-03, ARC-04, ARC-07]

duration: 12 min
completed: 2026-08-27
---

# Phase 1 Plan 12: 数据库权威 RBAC 与管理员审计 Summary

**后端 admin probe 以 PostgreSQL 当前 active role 授权，管理员 bootstrap/promote CLI 将每一次角色变化与完整 audit 证据原子持久化。**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-27T10:00:00Z
- **Completed:** 2026-08-27T10:12:39Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments

- 新增 `/api/v1/admin/probe`：先验证原有 session-bound Bearer，再从数据库重读用户 active role；伪造 JWT `role=admin` 的普通用户稳定获得 403，数据库角色改变立即生效。
- 新增 `admin_role_audit` Alembic `0003` migration，数据库约束 actor/reason 非空、角色合法且前后角色不同；Service 保证角色更新和 audit row 同一事务提交。
- 新增仅后端使用的 `python -m app.admin.cli bootstrap|promote`。首次 bootstrap 记录 `system:bootstrap`，后续提升验证 active/verified admin actor，拒绝匿名、不存在 actor、自我提升和空 reason。
- 首次管理员判定使用 PostgreSQL transaction-scoped advisory lock，防止并发 bootstrap 同时观察到空管理员集合。
- 用户 H5 未增加 `/admin` 路由、后台导航或 admin probe 调用；前端现有无后台表面测试继续通过。

## Task Commits

1. **Task 1 RED: 建立 admin 审计模型、Service 与 probe 合约** - `5662237` (test)
2. **Task 1 GREEN: 建立 admin 审计模型、Service 与 probe** - `bb9577e` (feat)
3. **Task 2 RED: 可审计管理员 CLI 合约** - `deaa083` (test)
4. **Task 2 GREEN: 实现可审计管理员 CLI** - `1a1b9ca` (feat)
5. **Security follow-up: 串行化首次管理员 bootstrap** - `e3f89e2` (fix)

## Files Created/Modified

- `backend/app/admin/` - 独立 admin API、Schema、Repository port/adapter、Service、CLI 与目录契约。
- `backend/migrations/versions/0003_admin_audit.py` - PostgreSQL `admin_role_audit` 表、完整字段约束和可逆 migration。
- `backend/tests/integration/test_admin_audit.py` - 真实 PostgreSQL probe、JWT role 伪造、CLI actor、audit 字段与 rollback 证据。
- `backend/app/main.py` - 装配 backend-only admin router。
- `backend/tests/integration/test_auth_migration.py` - 将 migration head 断言推进到 `0003`。
- `backend/README.md` - 记录显式管理员 CLI 的安全操作方法。

## Decisions Made

- JWT `role` 只保持现有令牌结构兼容性，不能决定 admin 授权；每个 probe 都从数据库读取角色与 active 状态。
- bootstrap 不是公开 API，也不接受任意未认证提升：仅在不存在 active admin 时允许，actor 固定为 `system:bootstrap`；后续提升必须证明现有 admin actor。
- audit 不因“Phase 1 只做 probe”而延期。角色变化缺少审计行与审计行缺少角色变化同样视为失败事务。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression] 推进既有迁移 head 断言**
- **Found during:** Task 1 GREEN
- **Issue:** `test_auth_migration.py` 固定断言 migration head 为 `0002`，加入计划要求的 `0003` 后会使完整后端回归失败。
- **Fix:** 将空库重建断言同步到 `0003`，并要求 head 包含 `admin_role_audit`。
- **Files modified:** `backend/tests/integration/test_auth_migration.py`
- **Verification:** migration 链与 admin integration tests `4 passed`；完整 backend suite `81 passed`。
- **Committed in:** `bb9577e`

**2. [Rule 2 - Security] 串行化首次管理员 bootstrap**
- **Found during:** Task 2 close-out review
- **Issue:** 单纯的“无 active admin”查询会存在并发 check-then-promote 窗口，两个 CLI 进程可能同时通过首次 bootstrap 判断。
- **Fix:** Repository 在同一事务内取得 PostgreSQL transaction-scoped advisory lock，再执行 active-admin 判断、角色变化和 audit 写入。
- **Files modified:** `backend/app/admin/ports.py`, `backend/app/admin/repository.py`, `backend/app/admin/service.py`
- **Verification:** admin integration suite `4 passed`，完整 backend PostgreSQL suite `81 passed`。
- **Committed in:** `e3f89e2`

**3. [Rule 2 - Operational contract] 补充管理员 CLI 的后端使用说明**
- **Found during:** Task 2 GREEN
- **Issue:** Phase 1 D-24 要求 README 包含创建管理员命令；计划文件列表未列出 `backend/README.md`。
- **Fix:** 写入 bootstrap/promote 命令、actor/reason 与事务安全约束。
- **Files modified:** `backend/README.md`
- **Verification:** `python -m app.admin.cli --help` 通过，CLI PostgreSQL tests 通过。
- **Committed in:** `1a1b9ca`

---

**Total deviations:** 3 auto-fixed（1 Rule 1，2 Rule 2）。
**Impact on plan:** 都是 migration 回归、bootstrap 提权竞争和既有文档契约的必要修复；没有增加前端后台或改变模块化单体架构。

## Issues Encountered

- 沙箱默认拒绝 Docker socket 与本机 PostgreSQL 端口；使用限定授权启动已有隔离容器并重跑相同命令后通过。系统 Python 3.11 未安装 pytest，改用项目已存在的 `backend/.venv/bin/python`，没有新增依赖或变更测试环境。

## Authentication Gates

None.

## Known Stubs

None. 已扫描本计划新增/修改文件，未发现流向运行时的空数据、占位文本或未接线组件。

## User Setup Required

None - 使用既有 Docker PostgreSQL/Mailpit 和现有 backend virtual environment，不需要外部账号或密钥。

## Verification Evidence

- Task 1 RED：`pytest tests/integration/test_admin_audit.py -q` 因 `app.admin` 不存在而预期失败。
- Task 1 GREEN：真实 PostgreSQL admin/migration 测试 `4 passed`，并完成 `.venv/bin/python -m compileall -q app migrations tests`。
- Task 2 RED：CLI 合约因 `app.admin.cli` 不存在而预期失败。
- Task 2 GREEN：真实 PostgreSQL admin audit suite `4 passed`，覆盖 `system:bootstrap`、delegated actor、before/after/time/reason、non-admin/inactive/unverified/self/empty-reason 拒绝与失败 rollback 无孤儿 audit。
- 最终 backend 回归：`81 passed, 7 warnings`，无 skip；warning 仅来自既有 Starlette TestClient per-request cookie deprecation。
- 最终 frontend 回归：`npm run lint`、`npm run typecheck`、`npm run test`（`27 passed`）与 `npm run build` 全部通过。
- `rg` 扫描确认 `frontend/` 无新 `/admin` 路由、后台导航或 admin probe 调用；本计划未创建 `admin-frontend/`。

## Next Phase Readiness

- Phase 6 可复用 admin API 分层、数据库权威 role guard 和 audit 约束实现独立 `admin-frontend/`；用户 H5 必须继续保持无后台表面。
- 后续任何 `/api/v1/admin/*` 写操作都应复用 `AdminService.require_role`，并为实际业务变更扩展同级审计事件，不得仅信任令牌 claim。
- 无阻塞项。

## Self-Check: PASSED

- `models.py`、`service.py`、`api.py`、`cli.py`、`0003_admin_audit.py`、真实 PostgreSQL 集成测试和本 Summary 均存在。
- `5662237`、`bb9577e`、`deaa083`、`1a1b9ca` 与 `e3f89e2` 全部可由 Git 历史解析；两个 TDD task 均保持 RED → GREEN 顺序。
- 计划级 RBAC、CLI、审计事务和无 admin H5 表面验证已在最终完整回归中通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
