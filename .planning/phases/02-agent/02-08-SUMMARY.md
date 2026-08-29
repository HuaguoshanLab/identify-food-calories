---
phase: 02-agent
plan: 08
subsystem: database
tags: [postgresql, alembic, langgraph, checkpointer, usda-fdc, sha256]
requires:
  - phase: 02-agent
    provides: "隔离 PostgreSQL wrapper、Agent/Nutrition schema 与确定性 Nutrition Repository"
provides:
  - "离线 hash 校验、不可变版本和幂等写入的 USDA FDC 小型受控目录"
  - "独立于 Alembic 业务 schema 的显式 AsyncPostgresSaver setup CLI"
  - "迁移 → Checkpointer setup → seed apply 的真实 PostgreSQL 可重复初始化证据"
affects: [agent-api, agent-runtime, playwright, nutrition-tools]
tech-stack:
  added: []
  patterns: ["immutable catalog version content hash", "explicit checkpointer schema lifecycle", "PostgreSQL-backed execution lease"]
key-files:
  created:
    - backend/app/nutrition/importer.py
    - backend/app/nutrition/data/fdc-seed-v1.json
    - backend/scripts/setup_checkpointer.py
    - backend/app/agent/supervisor.py
    - backend/migrations/versions/0005_nutrition_catalog_content_hash.py
  modified:
    - backend/app/nutrition/repository.py
    - backend/tests/integration/test_agent_bootstrap.py
    - backend/tests/integration/test_agent_migration.py
key-decisions:
  - "FDC seed 只接受离线 local manifest；canonical SHA-256 不匹配或同版本 hash 冲突时拒绝写入。"
  - "Checkpointer 表通过独立 CLI 显式 setup，不进入 Alembic 业务 migration，也不在请求或 worker lifespan 中隐式创建。"
  - "测试启动始终保留 DATABASE_URL=5432/food_agent_dev 与 TEST_DATABASE_URL=55432/food_agent_test 的互异边界。"
patterns-established:
  - "目录数据版本必须以 immutable content hash 写入 PostgreSQL，重复 apply 无变更、hash 冲突失败。"
  - "真实 PostgreSQL migration 测试必须把外部 Checkpointer 表与 Alembic 管理的业务 schema 分开断言。"
requirements-completed: [AGT-04, NUT-01, NUT-02, QLT-02]
duration: 52min
completed: 2026-08-29
---

# Phase 02 Plan 08: 可重复的目录与 Checkpointer 初始化链 Summary

**USDA FDC 离线受控目录以 hash 不可变版本写入，并由显式 Checkpointer setup 组成可重复验证的 PostgreSQL 初始化链。**

## Performance

- **Duration:** 52 min
- **Completed:** 2026-08-29
- **Tasks:** 2/2
- **Files modified:** 18

## Accomplishments

- 固化 24 条 USDA FoodData Central CC0 记录；每条含 FDC id、精确来源 URL、prepared state、四项营养值、受控别名和全局 manifest hash。
- `--check` 只校验本地 manifest；`--apply` 通过 Service/Repository 写入 immutable catalog version，重复 apply 零变更，同版本不同 hash 直接拒绝，绝不访问 FDC 网络或补零。
- 交付仅接受已验证 `TEST_DATABASE_URL` 的 `AsyncPostgresSaver` setup CLI（strict msgpack、禁用 pickle）与 PostgreSQL lease supervisor。
- 真实测试连续执行初始化链，确认 Alembic `0005`、Checkpointer 三表、qualified cooked rice 和 catalog hash 都存在，且开发库目标保持未改写。

## Task Commits

1. **Task 1: 固化 FDC seed 与幂等 apply（RED）** — `dfe3978`
2. **Task 1: 固化 FDC seed 与幂等 apply（GREEN）** — `567724a`
3. **Task 2: 建立显式 Checkpointer setup 与全链幂等验证（RED）** — `7cc4c76`
4. **Task 2: 建立显式 Checkpointer setup 与全链幂等验证（GREEN）** — `b26502c`
5. **迁移回归修复** — `1cfff2d`

## Files Created/Modified

- `backend/app/nutrition/importer.py` — strict FDC manifest DTO、hash 校验、Service 和 CLI。
- `backend/app/nutrition/data/fdc-seed-v1.json` — 24 条离线可审计的 CC0 小型目录。
- `backend/migrations/versions/0005_nutrition_catalog_content_hash.py` — catalog version 的不可变 hash 持久化约束。
- `backend/scripts/setup_checkpointer.py` — 显式、安全的 AsyncPostgresSaver schema setup。
- `backend/app/agent/supervisor.py` — 不依赖进程本地锁的持久租约 supervisor。
- `backend/tests/integration/test_agent_bootstrap.py` — 全链重复启动与真实表/seed 断言。

## Decisions Made

- Household portion 未提供精确来源或双角色签署时不会导入；目录不提供该换算，后续工具必须追问克数。
- Checkpointer migration 生命周期与 Alembic 业务 schema 故意拆分，防止 library-owned 表被误伪装成业务 migration。
- `DATABASE_URL` 只保留开发哨兵，所有破坏性测试步骤只接收 guard 返回的 `TEST_DATABASE_URL`。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 持久化 catalog content hash**
- **Found during:** Task 1
- **Issue:** 原有 `nutrition_catalog_versions` 没有 content hash，无法可靠拒绝同版本 manifest 覆盖。
- **Fix:** 添加 `0005` Alembic migration、ORM 唯一约束和 Repository 映射。
- **Files modified:** `backend/app/nutrition/models.py`, `backend/migrations/versions/0005_nutrition_catalog_content_hash.py`
- **Verification:** importer conflict unit contract 与真实 PostgreSQL schema metadata contract 通过。
- **Committed in:** `567724a`, `1cfff2d`

**2. [Rule 1 - Bug] 对齐 migration 回归测试与 Checkpointer 独立生命周期**
- **Found during:** 全量 PostgreSQL 回归
- **Issue:** 旧测试固定 head 为 `0004`，并把显式 setup 创建的 Checkpointer 表误当成 Alembic downgrade 的残留。
- **Fix:** 更新 `0005` metadata 断言；migration-only 测试从空隔离 schema 开始，并显式区分 library-owned 表。
- **Files modified:** `backend/tests/integration/test_agent_migration.py`, `backend/tests/integration/test_auth_database_protocols.py`, `backend/tests/integration/test_auth_migration.py`
- **Verification:** 真实 PostgreSQL 全量回归 `158 passed`。
- **Committed in:** `1cfff2d`

**3. [Rule 1 - Bug] 移除 AgentRepository 未实现且未使用的 `now` Protocol 成员**
- **Found during:** Task 2 mypy 检查
- **Issue:** 新 supervisor 注入现有 SQLAlchemy Repository 时，Protocol 声明了 adapter 从未实现也未使用的方法，导致类型边界失真。
- **Fix:** 移除该无效 Port 成员，保持时钟只由 Service 注入。
- **Files modified:** `backend/app/agent/ports.py`
- **Verification:** 目标范围 mypy 通过。
- **Committed in:** `b26502c`

**Total deviations:** 3 auto-fixed（2 个 Rule 1，1 个 Rule 2）。
**Impact on plan:** 均为不可变目录、安全测试隔离或类型边界正确性所必需，没有扩展产品功能。

## Issues Encountered

- 常规沙箱拒绝本机 PostgreSQL loopback；在受控权限下通过现有 `tests/run_pg.py` wrapper 完成真实数据库验证。
- 全库 mypy 当前报告 69 个 Phase 1 既有测试类型错误；本计划新增/修改范围的 mypy 检查通过，未修改无关认证测试。

## Known Stubs

None. 目录、Checkpointer setup 和 supervisor 都有真实实现与验证；生产仍必须显式提供已审查的数据库配置。

## User Setup Required

None - 本计划没有外部账号或密钥配置步骤。

## Next Phase Readiness

- Agent API、SSE、Playwright 和 Graph runtime 可以先运行同一初始化器，可靠依赖 migration、Checkpointer 表和 qualified FDC seed。
- 后续生产部署必须沿用显式 Checkpointer setup，禁止把 setup 塞进请求、worker 或 graph node。

## Self-Check: PASSED

- 已确认 importer、FDC seed、Checkpointer CLI、lease supervisor、`0005` migration 和本 Summary 均存在。
- 已确认 `dfe3978`、`567724a`、`7cc4c76`、`b26502c`、`1cfff2d` 均存在于 Git 历史。

*Phase: 02-agent*
*Completed: 2026-08-29*
