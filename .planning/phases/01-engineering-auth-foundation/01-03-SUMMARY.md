---
phase: 01-engineering-auth-foundation
plan: 03
subsystem: auth-database
tags: [sqlalchemy, alembic, postgresql, authentication, repository]

requires:
  - phase: 01-engineering-auth-foundation/01-01
    provides: 隔离 PostgreSQL 测试库、fail-closed Settings 与同步 Session factory
provides:
  - 用户、邮箱验证、会话与 refresh token 的 SQLAlchemy 权威模型
  - 与 ORM 分离的公开 Pydantic Schema 和 flush-only Repository adapter
  - 只接受隔离 TEST_DATABASE_URL 的 Alembic 0001 基线
  - 空库 upgrade、downgrade、约束与 Repository 的真实 PostgreSQL 证据
affects: [01-04, 01-05, 01-10, 01-12, 01-13, auth, sessions, rbac]

tech-stack:
  added: [Alembic 0001 auth revision]
  patterns: [ORM-Schema separation, Protocol repository port, service-owned transactions, guarded test migrations]

key-files:
  created: [backend/app/auth/models.py, backend/app/auth/schemas.py, backend/app/auth/ports.py, backend/app/auth/repository.py, backend/migrations/versions/0001_auth_foundation.py, backend/tests/integration/test_auth_migration.py]
  modified: [backend/app/README.md, backend/README.md, backend/migrations/README.md, backend/tests/README.md, backend/tests/conftest.py]

key-decisions:
  - "验证码当前性由 user_id + purpose 的 PostgreSQL partial unique index 强制，终态由 consumed_at/invalidated_at 互斥约束表达。"
  - "Repository 只 query/add/flush，Service 保留多步骤认证协议的 commit/rollback 事务边界。"
  - "APP_ENV=test 的 Alembic 环境只使用经过现有隔离 guard 验证的 TEST_DATABASE_URL。"

patterns-established:
  - "公开 Schema 白名单：密码、验证码 context/code 摘要与 refresh token 摘要只存在 ORM，不进入响应模型。"
  - "迁移即 schema：真实 PostgreSQL 从 base 往返到 head，禁止 create_all 或 SQLite 替代。"

requirements-completed: [ARC-02, ARC-03, ARC-04, ARC-07]

duration: 12 min
completed: 2026-08-27
---

# Phase 1 Plan 3: 认证权威数据契约 Summary

**用户、验证码、会话与 refresh token 的约束化 PostgreSQL schema，配套分层 Repository 合约和 fail-closed Alembic 测试路径。**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-27T06:28:00Z
- **Completed:** 2026-08-27T06:39:30Z
- **Tasks:** 2
- **Files modified:** 18

## Accomplishments

- 将 SQLAlchemy ORM、Pydantic 公开 Schema、Repository Protocol 和同步 adapter 分离；公开输入不能自选 role，公开模型不含任何密码或令牌摘要。
- `0001` 建立规范化邮箱、固定角色、未验证账号、验证码时效/次数/当前性、会话 family 与 refresh 轮换所需的外键、唯一约束和索引。
- Alembic 在 `APP_ENV=test` 下拒绝开发库、SQLite、缺失或非 `_test` 目标；空测试库 downgrade/upgrade 和 schema drift 检查通过。
- 真实 PostgreSQL 测试验证关键约束、partial unique index、Repository `flush()` 行为及开发 schema 前后快照不变。

## Task Commits

1. **Task 1: 定义 auth 模型、Schema 与 Repository port** - `d71427d` (feat)
2. **Task 2 RED: 固化失败的 migration/Repository 合约** - `4fc6769` (test)
3. **Task 2 GREEN: 建立受保护的 0001 Alembic 基线** - `9d13da6` (feat)
4. **Task 2 verification: 强化约束与目标库证据** - `4470699` (test)

## Files Created/Modified

- `backend/app/auth/models.py` - 用户、验证码、auth session 与 refresh token ORM 模型和约束 metadata。
- `backend/app/auth/schemas.py` - 注册、验证、当前用户与会话的运行时公开合约。
- `backend/app/auth/ports.py` / `repository.py` - 应用服务依赖的 Protocol 与同步 SQLAlchemy adapter。
- `backend/alembic.ini` / `backend/migrations/env.py` - CLI 配置和测试目标 fail-closed 迁移环境。
- `backend/migrations/versions/0001_auth_foundation.py` - 可升级、可降级的认证 schema 基线。
- `backend/tests/integration/test_auth_migration.py` - 空库往返、关键约束、Repository 和目标库隔离证据。
- auth、migration、versions 与 integration README - 职责、允许依赖和文件索引。

## Decisions Made

- 邮箱列本身必须等于 `lower(btrim(email))`，再叠加唯一约束；数据库拒绝未规范化写入，Service 负责规范化用户输入。
- refresh token 保存 `token_digest` 而非原文；`replaced_by_id` 只有已 consumed 的 token 才允许设置。
- 当前验证码不用可漂移的布尔字段，而用“未 consumed 且未 invalidated”的 partial unique index定义；新验证码必须先失效旧验证码并在同一 Service 事务插入。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical verification] 增加真实 PostgreSQL migration/Repository 合约测试**
- **Found during:** Task 2 RED
- **Issue:** Task 标记为 TDD，但计划文件列表未包含可证明空库往返、关键约束和 Repository 事务边界的测试。
- **Fix:** 创建 `tests/integration/` 目录、README 和 `test_auth_migration.py`，先得到缺少 Alembic 基线的预期 RED，再实现 GREEN。
- **Files modified:** `backend/tests/README.md`, `backend/tests/integration/README.md`, `backend/tests/integration/test_auth_migration.py`
- **Verification:** RED 为 `1 failed, 1 error, 1 passed`；GREEN 最终全套 `20 passed`。
- **Committed in:** `4fc6769`, `4470699`

**2. [Rule 3 - Blocking test runner] 使用当前 Python 解释器调用 Alembic**
- **Found during:** Task 2 GREEN
- **Issue:** 既有 fixture 依赖 PATH 中的裸 `alembic`，直接用 `.venv/bin/python -m pytest` 时不可保证解析到同一环境。
- **Fix:** fixture 改为 `sys.executable -m alembic upgrade head`，与测试解释器及锁定依赖保持一致。
- **Files modified:** `backend/tests/conftest.py`
- **Verification:** 隔离 PostgreSQL fixture 成功执行 0001，Repository 合约通过。
- **Committed in:** `9d13da6`

---

**Total deviations:** 2 auto-fixed (1 Rule 2, 1 Rule 3)。
**Impact on plan:** 两项均是 TDD、数据库隔离和可重复验证所必需，没有扩张认证产品功能。

## Issues Encountered

- 系统 `python3.11` 没有项目依赖，所有项目验证改用已提交工作流约定的 `backend/.venv`；没有安装新包或修改依赖锁。
- Docker daemon、Git index 和本机 PostgreSQL 端口受沙箱保护；通过受控授权运行同一限定命令完成验证和原子提交。

## Known Stubs

None. 可空的 `email_verified_at`、`consumed_at`、`invalidated_at`、`revoked_at` 和 Alembic revision 元数据均表达真实生命周期状态，不是 UI 或数据占位。

## User Setup Required

None - 复用 01-01 的 Docker PostgreSQL 与 backend virtualenv，不需要外部账号或密钥。

## Verification Evidence

- `.venv/bin/python -m compileall -q app migrations tests` → 通过。
- Auth mapper/import 与公开 Schema 敏感字段检查 → `AUTH_IMPORT_CONTRACT_PASS`。
- `alembic upgrade head` → 测试库从空 schema 升级到 `0001`。
- `alembic downgrade base && alembic upgrade head` → 双向迁移成功。
- `alembic check` → `No new upgrade operations detected.`。
- `pytest tests/unit tests/integration/test_auth_migration.py -q` → `20 passed`。
- 开发 schema 在测试迁移前后快照一致；错误 TEST_DATABASE_URL 在连接前被配置 guard 拒绝。

## Next Phase Readiness

- 01-04 可直接复用 `AuthRepository`、验证码模型和 partial-current 约束，实现 MailProvider 与注册验证 Service。
- 01-05/01-10 可在 session family、refresh digest 和 `SELECT FOR UPDATE` adapter 上实现登录与轮换协议。
- 无阻塞项。

## Self-Check: PASSED

- 18 个新增/修改文件均存在，新增 auth、versions、integration 目录均有 README 且父索引已同步。
- `d71427d`、`4fc6769`、`9d13da6`、`4470699` 均可从 Git 历史解析。
- Task 1 导入/Schema/Repository 边界与 Task 2 RED/GREEN、空库迁移、downgrade、漂移和真实 PostgreSQL 约束验收全部通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
