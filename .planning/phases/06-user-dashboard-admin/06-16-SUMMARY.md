---
phase: 06-user-dashboard-admin
plan: 16
subsystem: admin-api-database
tags: [fastapi, sqlalchemy, alembic, rbac, provider, runtime-config]
requires:
  - phase: 06-14
    provides: immutable catalog publication migration lineage through 0018
provides:
  - append-only non-secret reasoning runtime configuration versions
  - current-database-RBAC configuration command and audited API
  - immutable run/invocation configuration and price-cap ledger fields
affects: [agent-runtime, admin-frontend, provider-factory, migrations]
tech-stack:
  added: []
  patterns: [append-only policy versioning, advisory-lock admission, environment-only credential resolution]
key-files:
  created:
    - backend/migrations/versions/0019_runtime_config_versions.py
    - backend/tests/admin/test_runtime_config_service.py
  modified:
    - backend/app/agent/api.py
    - backend/app/agent/ports.py
    - backend/app/agent/models.py
    - backend/app/agent/service.py
    - backend/app/admin/service.py
    - backend/app/providers/reasoning/factory.py
key-decisions:
  - "迁移按用户授权从实际 0018 head 顺延为 0019，而不重用已占用的 0017。"
  - "配置 API 只接收 provider、固定 model alias、启用状态、价格和上限；密钥与 endpoint 永远只由环境解析。"
patterns-established:
  - "管理员配置命令在读写前加载当前数据库角色，并以 PostgreSQL advisory lock 串行化版本分配与准入读取。"
  - "Agent HTTP 路由只通过注入的 admission port 创建新 run；旧幂等 run 保持原快照。"
requirements-completed: [ADM-04, ADM-05]
duration: 31min
completed: 2026-09-03
---

# Phase 06 Plan 16: Runtime Configuration Admission Summary

**后台可追加、审计并锁定非密钥推理配置版本，Agent 账本可保留配置与价格上限快照，Provider 凭据仍只来自环境。**

## Performance

- **Duration:** 31 min
- **Started:** 2026-09-03T03:23:00Z
- **Completed:** 2026-09-03T03:54:00Z
- **Tasks:** 3/3
- **Files modified:** 14

## Accomplishments

- 建立 `agent_runtime_config_versions` append-only 表，并为 Agent run/invocation 追加 runtime-config 与价格/上限快照字段。
- 新增严格的管理员配置命令与 `/api/v1/admin/runtime-config`；每次命令重读数据库管理员角色、要求 Idempotency-Key、记录最小审计 diff。
- Provider 工厂仅从环境读取 DeepSeek 密钥，严格拒绝配置输入中的 endpoint、key、未知 alias 或异常价格；0019 已完成真实 PostgreSQL 降级再升级且保持单一 head。
- 所有真实 Agent HTTP 新 run 在写入 ledger 前经 admin-owned admission port 锁定 active config；停用后的新命令返回通用 503，既有幂等重放继续使用启动时快照。

## Task Commits

1. **Task 1: 写配置快照和停用 RED 测试** - `1bc9678` (test)
2. **Task 2: 实现 immutable runtime config 准入** - `be1efaa` (feat)
3. **Task 3: 固定终端迁移并验证唯一 head** - `bbc796e` (chore)
4. **安全回归修复：快照价格类型校验** - `d446000` (fix)
5. **最小实际命令接线：强制 admission** - `4991de0` (feat)

## Files Created/Modified

- `backend/migrations/versions/0019_runtime_config_versions.py` - `0018 → 0019` 单线 schema 与可逆 downgrade。
- `backend/app/agent/models.py` - 运行配置版本及 run/invocation 快照 ORM 数据。
- `backend/app/agent/service.py` - 写账本前拒绝含 secret/endpoint 的 snapshot，并冻结 invocation 上限。
- `backend/app/agent/{api,ports}.py` - Agent HTTP 命令使用窄 admission port；路由不查询 admin 表。
- `backend/app/admin/{schemas,repository,service,api}.py` - 严格 DTO、DB-RBAC、advisory lock、审计与配置 HTTP 命令。
- `backend/app/providers/reasoning/factory.py` - 仅环境密钥 + allowlisted snapshot 的 Provider 装配。
- `backend/tests/admin/test_runtime_config_service.py` - Fake repository、无真实 Provider/密钥的 RED/GREEN 合约。

## Decisions Made

- `0017`、`0018` 已被完成工作占用，按用户授权将本计划顺延为 `0019`，`down_revision = "0018"`。
- 准入使用保守 worst-case 单次与周期 cap；关闭配置只阻断后续 admission，已获得的 immutable snapshot 不被改写。
- AgentService 只依赖 `RuntimeConfigAdmitter` port；AdminService 作为 request composition 中的实现，保持 API → Service → Repository 边界。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Runtime JSON snapshot 的 Decimal 字符串在 Factory 中无法比较**
- **Found during:** Task 2
- **Issue:** 账本 JSON 以字符串存储价格，Factory 直接与整数比较会抛出 `TypeError`。
- **Fix:** Factory 显式解析 Decimal，异常价格在创建任何 Provider client 前 fail closed。
- **Files modified:** `backend/app/providers/reasoning/factory.py`, `backend/tests/admin/test_runtime_config_service.py`
- **Verification:** `uv run pytest tests/admin/test_runtime_config_service.py -q`。
- **Committed in:** `d446000`

**2. [Rule 2 - Documentation] 迁移目录索引同步到 0019**
- **Found during:** Task 2
- **Issue:** 新增 migration 未更新目录文件索引，违反仓库目录文档合同。
- **Fix:** 更新 `backend/migrations/README.md` 与 `backend/migrations/versions/README.md`。
- **Committed in:** `be1efaa`

**3. [User-authorized migration sequencing] Draft 中的 0017 已被占用**
- **Found during:** Task 3
- **Issue:** 实际 head 已是 `0018`；重用 0017 会制造并行 head。
- **Fix:** 使用用户授权的 `0019_runtime_config_versions.py`，唯一前驱设为 `0018`。
- **Verification:** 隔离 PostgreSQL 中 `0019 → 0018 → 0019` 成功，`alembic heads` 仅输出 `0019 (head)`。

---

**Total deviations:** 2 auto-fixed（1 bug、1 文档合同）和 1 项用户授权迁移顺延。  
**Impact on plan:** 安全边界和单线迁移得到加强；未增加依赖。

## Verification

- `cd backend && uv run pytest tests/admin tests/unit/test_admin_audit_api.py -q` → **17 passed**。
- `cd backend && uv run pytest tests/admin tests/unit/test_admin_audit_api.py tests/unit/test_agent_api_contract.py tests/unit/test_runtime_foundation.py -q` → **34 passed**。
- `cd backend && uv run ruff check ...` → **All checks passed**。
- `APP_ENV=test TEST_DATABASE_URL=... uv run alembic downgrade 0018 && ... upgrade head` → **成功**。
- `APP_ENV=test TEST_DATABASE_URL=... uv run alembic heads` → **0019 (head)，且仅一个 head**。

## User Setup Required

None - 不新增密钥；DeepSeek 密钥和 endpoint 继续仅由未提交环境变量提供。

## Next Phase Readiness

- 管理后台已获得安全的运行配置写接口和可审计投影。
- Agent HTTP 新 run 已被强制接入 `admit_runtime_call`，后续停用/启用配置可立即控制新调用而不改写旧账本。

## Self-Check: PASSED

- `0019_runtime_config_versions.py`、RED tests、admission port 与五个原子提交均存在。
- `git log --all` 可定位 `1bc9678`、`be1efaa`、`bbc796e`、`d446000`、`4991de0`。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
