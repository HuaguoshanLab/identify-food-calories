---
phase: 02-agent
plan: 05
subsystem: database-evaluation
tags: [alembic, postgresql, sqlalchemy, migration, frozen-eval, sha256]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "受保护的真实 PostgreSQL 测试 wrapper、Alembic 链和共享 SQLAlchemy Base"
  - phase: 02-agent
    provides: "Nutrition 与 Agent ORM、Provider/Graph 边界及冻结评测合同"
provides:
  - "无业务 seed 的 0004 Agent ledger 与版本化 nutrition schema"
  - "0003↔0004、ORM metadata/live PostgreSQL schema 无漂移的真实数据库证据"
  - "带 hash 链和语义门的 5-case complete happy-path 冻结前缀"
affects: [catalog-importer, checkpointer, agent-api, evaluation, release-report]
tech-stack:
  added: []
  patterns: ["ORM metadata as migration contract", "seed lifecycle separation", "append-only frozen JSONL hash chain"]
key-files:
  created:
    - backend/migrations/versions/0004_agent_core.py
    - backend/tests/integration/test_agent_migration.py
    - backend/evals/phase02-cases.jsonl
    - backend/evals/validate_dataset.py
  modified:
    - backend/app/nutrition/models.py
    - backend/app/agent/models.py
    - backend/tests/integration/test_auth_migration.py
    - backend/README.md
key-decisions:
  - "Alembic 0004 只创建 schema；FDC/catalog 业务记录只能由后续版本化 importer 写入。"
  - "catalog、version、source、food、alias、portion 都由同一 SQLAlchemy metadata 声明，迁移测试逐表核对真实 PostgreSQL。"
  - "冻结首批五例只接受完整 completed 主路径，并分别覆盖克数、受控份量、唯一别名、多菜、饮料加配料。"
patterns-established:
  - "所有真实迁移 child 保持 DATABASE_URL 开发哨兵与 TEST_DATABASE_URL 隔离库互异；开发库只读指纹，不可重绑。"
  - "JSONL case hash 排除自身 case_hash、包含 parent_hash；任意旧前缀改写都会导致校验失败。"
requirements-completed: [AGT-04, AGT-06, AGT-07, NUT-01, ARC-05, QLT-02]
duration: 12min
completed: 2026-08-29
---

# Phase 02 Plan 05: Agent Core Schema 与冻结 Happy Prefix Summary

**以无 seed 的可逆 0004 迁移交付 Agent 账本和版本化营养目录，并冻结 5 个可审计的完整主路径案例。**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-29T04:33:03Z
- **Completed:** 2026-08-29T04:45:40Z
- **Tasks:** 2/2
- **Files modified:** 16

## Accomplishments

- 新增 `0004_agent_core`：包括 thread/run/event/invocation/lease/deletion-intent 与 catalog/version/source/food/alias/portion，所有表、列、命名约束、索引与外键由 ORM metadata 合同驱动。
- 真实 PostgreSQL 测试从空库升级、`0003 ↔ 0004` 往返，逐表比较 metadata 和 live schema，断言 catalog 为 0 行且开发库指纹完全不变。
- 建立首批 5 个完整 `completed` 主路径案例和 SHA-256 parent hash 链，阻止将目录外、负数或工具失败伪装成 happy case，也拒绝 PII、密钥和思维链字段。

## Task Commits

1. **Task 1: 创建可逆且无 seed 的 0004 migration（RED）** — `831feb2` (`test`)
2. **Task 1: 创建可逆且无 seed 的 0004 migration（GREEN）** — `6e0fc18` (`feat`)
3. **Task 2: 建立语义严格的 5-case happy prefix** — `7bfa88d` (`test`)

## Files Created/Modified

- `backend/migrations/versions/0004_agent_core.py` — 只含业务 schema、完整 reverse downgrade，绝不插入 catalog/business seed。
- `backend/app/nutrition/{models.py,repository.py}` — catalog/version/source 的可追溯 metadata 边界与查询装配。
- `backend/app/agent/models.py` — tenant-bound `AgentDeletionIntent` 的持久化合同。
- `backend/tests/integration/test_agent_migration.py` — 真 PostgreSQL round-trip、schema drift、head 与零 seed 证据。
- `backend/evals/{phase02-cases.jsonl,validate_dataset.py}` — append-only 5-case frozen prefix 与 fail-closed 语义/hash 校验。
- `backend/tests/unit/test_eval_dataset.py` — 不允许 happy 掩盖边界失败、也不允许无痕改写旧 prefix。
- `backend/{README.md,evals/README.md}`、相关 module/test/migration README — 目录职责和文件索引。

## Decisions Made

- 业务 seed 与 schema migration 分离：迁移建立空且可约束的权威表，后续 importer 才可导入版本化 FDC 数据。
- `FoodCatalogItem` 通过 catalog version 和 source 外键保留来源、许可和版本链，不能把这些可追溯字段留作无约束的重复字符串。
- 初始冻结集不是“5 个能解析的样例”：每例必须携带 completed state、五步确定性 trace、完整报告字段、稳定事件序列及禁止行为断言。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐 migration 所依赖的单一 ORM metadata 合同**

- **Found during:** Task 1
- **Issue:** 02-06/02-07 初始 ORM 缺少 plan 所要求的 catalog/version/source 表和 deletion-intent；若直接在 migration 中手写这些表，会让 migration 与 ORM 分叉，违反本计划与架构规则。
- **Fix:** 在 Nutrition metadata 增加 catalog/version/source 与受约束外键，在 Agent metadata 增加 tenant-bound deletion intent；同步调整 Repository 和各级 README 索引。
- **Files modified:** `backend/app/nutrition/{models.py,repository.py,README.md}`、`backend/app/agent/{models.py,README.md}`。
- **Verification:** 真实 PostgreSQL 测试逐表、列、命名 check/unique、非 unique index、primary key 和 FK 语义比较 live schema 与 metadata；全量测试 154 passed。
- **Committed in:** `6e0fc18`

---

**Total deviations:** 1 auto-fixed（Rule 2）。
**Impact on plan:** 该修复是保持单一 schema 真相、D-18 删除意图落库和可追溯营养目录的必要条件；没有新增 API 或产品范围。

## Issues Encountered

- 默认沙箱禁止 TCP 访问本机 PostgreSQL；经受控权限在固定 `food_agent_test` 上运行真实迁移测试。wrapper 仍保持开发库和测试库互异，开发库仅做只读指纹检查。

## Known Stubs

None. 0004 有意保持 catalog 0 行；这不是 stub，而是将数据导入移交给 02-08 的安全、版本化 importer。

## User Setup Required

None - 本计划未新增外部依赖、密钥或账户。

## Next Phase Readiness

- 02-08 可安全连接 FDC importer、PostgreSQL Checkpointer 和初始化链；其 seed 必须满足本冻结前缀的 stable id、版本与受控“一碗”换算合同。
- 02-10 可将 5 条 happy case 接到真实纵向 API/Graph 流程；不得放松 completed trace、报告、事件或禁止行为断言。

## Self-Check: PASSED

- 已确认 `0004_agent_core.py`、`test_agent_migration.py`、`phase02-cases.jsonl`、`validate_dataset.py` 和本 Summary 存在。
- 已确认 TDD RED `831feb2`、GREEN `6e0fc18` 和数据集提交 `7bfa88d` 均存在。
- `tests/run_pg.py … pytest -q`：154 passed；dataset validator、`mypy app evals` 与 `ruff check .` 均通过。

*Phase: 02-agent*
*Completed: 2026-08-29*
