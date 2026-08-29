---
phase: 02-agent
plan: 07
subsystem: agent-runtime
tags: [langgraph, sqlalchemy, pydantic, postgres, idempotency, tdd]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "共享 SQLAlchemy Base、用户身份与 Service/Repository 事务边界"
  - phase: 02-agent
    provides: "Reasoning Provider Port 与确定性 Nutrition Service"
provides:
  - "用户归属的 thread/run/event/invocation/lease 权威 Agent ledger"
  - "版本化、受限且 JSON-safe 的 MealAgentState"
  - "Graph→NutritionToolAdapter→NutritionService 的可测试依赖合同"
affects: [agent-api, checkpointer, supervisor, sse, phase-02-evaluation]
tech-stack:
  added: []
  patterns: ["tenant-scoped repository port", "service-owned transactions", "durable invocation idempotency", "graph-tool adapter boundary"]
key-files:
  created:
    - backend/app/agent/models.py
    - backend/app/agent/service.py
    - backend/app/agent/state.py
    - backend/app/agent/tools.py
    - backend/app/agent/graph.py
  modified:
    - backend/app/README.md
    - backend/tests/unit/test_runtime_foundation.py
    - backend/tests/unit/README.md
key-decisions:
  - "thread_id 只是恢复游标；所有用户资源读取均通过 Repository 的 (user_id, resource_id) SQL 过滤。"
  - "命令、provider/tool 调用与事件使用独立 ledger；Checkpointer 不承担业务所有权或 exactly-once 责任。"
  - "Graph 只能接收 NutritionToolAdapter，饮食规划在 Phase 2 返回 CAPABILITY_NOT_AVAILABLE。"
patterns-established:
  - "Repository 只 flush/lock，AgentService 统一 commit/rollback 与命令幂等策略。"
  - "State 使用 Pydantic runtime validation 和固定上限，禁止 ORM、Provider 原文、token、CoT 与图片引用。"
requirements-completed: [AGT-01, AGT-02, AGT-04, AGT-06, AGT-07, ARC-05, QLT-02]
duration: 18min
completed: 2026-08-29
---

# Phase 02 Plan 07: Agent Ledger、State 与 Graph 合同 Summary

**建立 tenant-safe 的 Agent 运行账本和有界 JSON State，并以窄工具适配器把 Graph 与确定性营养领域隔离。**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-08-29
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments

- 用共享 SQLAlchemy Base 建立 thread、run、event、invocation 和 PostgreSQL lease 的最小权威 ledger；命令 hash、事件序号和调用幂等键具备唯一约束或行锁路径。
- 建立与 ORM/API/Provider DTO 分离的 `MealAgentState`，包含预算、项目、候选、工具安全摘要、版本和状态；State 严格限制长度且 Phase 2 不允许图片引用。
- 建立 `NutritionToolAdapter` 与主图路由/lifespan runtime 合同；Graph 不导入 SQLAlchemy、Model 或 Repository，未交付的饮食规划固定返回 `CAPABILITY_NOT_AVAILABLE`。
- 以 TDD 证明 tenant 命令幂等、State JSON 序列化与 Graph import 边界。

## Task Commits

1. **Task 1: 定义 ledger、State 和运行合同** — `73b0cf6` (`feat`)
2. **Task 2: 建立可接线的 Graph/tool/supervisor 合同（RED）** — `3f7c79e` (`test`)
3. **Task 2: 建立可接线的 Graph/tool/supervisor 合同（GREEN）** — `766391b` (`feat`)

## Files Created/Modified

- `backend/app/agent/models.py` — 可迁移的权威 Agent ledger ORM 与数据库约束。
- `backend/app/agent/{ports,repository,service}.py` — tenant-safe Repository Port、flush-only adapter 和事务/幂等边界。
- `backend/app/agent/state.py` — 版本化、JSON-safe、有预算上限的运行 State。
- `backend/app/agent/{tools,graph}.py` — Nutrition Service 工具适配器、两子图路由与 lifespan runtime Protocol。
- `backend/tests/unit/test_runtime_foundation.py` — 无 PostgreSQL 的 State、命令 hash 和 import 边界证据。
- `backend/app/README.md`、`backend/app/agent/README.md`、`backend/tests/unit/README.md` — 目录职责、允许依赖与文件索引。

## Decisions Made

- `AgentRun` 的 command key 与 canonical JSON SHA-256 hash 绑定；同 key/不同 payload 必定拒绝，不能把重放误认为新命令。
- 事件 ledger 只保留 allowlist payload/safe summary 的接口位置；完整 State、Provider body 与用户认证材料不进入事件模型。
- lease 记录在 PostgreSQL 模型中，具体 supervisor 初始化与真实数据库竞争证明留给 02-08/02-12。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Task 1 同步创建 Agent 目录 README 与父级索引**

- **Found during:** Task 1
- **Issue:** 计划在 Task 2 才列出 `agent/README.md`，但 Task 1 已创建 `agent/` 目录，会违反项目的新目录同次文档硬约束。
- **Fix:** 在 Task 1 一并创建含职责/允许依赖/文件索引的 README，并更新 `backend/app/README.md`。
- **Files modified:** `backend/app/agent/README.md`, `backend/app/README.md`
- **Verification:** `tests/architecture/test_directory_contract.py` 通过。
- **Committed in:** `73b0cf6`

**2. [Rule 1 - Bug] 将 import boundary 测试改为解析真实导入节点**

- **Found during:** Task 2 GREEN
- **Issue:** 初版测试把模块文档中的“禁止 SQLAlchemy”文字当成实际 import，造成假失败。
- **Fix:** 用 Python AST 检查导入声明，仍严格禁止 Graph 导入 SQLAlchemy、Agent Model 或 Repository。
- **Files modified:** `backend/tests/unit/test_runtime_foundation.py`
- **Verification:** 目标测试、mypy、Ruff 和 32 项相关回归全部通过。
- **Committed in:** `766391b`

**Total deviations:** 2 auto-fixed（Rule 2 ×1，Rule 1 ×1）。
**Impact on plan:** 两项均为目录合同与测试准确性的必要修复，没有扩展产品能力。

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| `CAPABILITY_NOT_AVAILABLE` 规划分支 | `backend/app/agent/graph.py` | Phase 5 才交付饮食规划；当前明确拒绝，不能伪造计划结果。 |
| lifespan runtime Protocol | `backend/app/agent/graph.py` | 真实 Checkpointer、PostgreSQL lease supervisor 与初始化链由 02-08 接线并用真实 PG 证明。 |

## User Setup Required

None - 本计划未新增外部依赖、密钥或账号。

## Next Phase Readiness

- 02-08 可在不改变依赖方向的前提下接入真实 `AsyncPostgresSaver`、营养 seed 与 PostgreSQL lease supervisor。
- 02-09/02-10 可通过 `AgentService` 和 `AgentRuntime` 实现 API、worker 与真实首个垂直 Green，不得让路由或 Graph 直接访问 ORM。

## Self-Check: PASSED

- 已确认 `models.py`、`service.py`、`state.py`、`tools.py`、`graph.py` 和本 Summary 存在。
- 已确认 `73b0cf6`、`3f7c79e`、`766391b` 均存在于 Git 历史。
- `pytest`（32 passed）、目标运行时测试、`mypy app/agent` 与 Ruff 均通过。
