---
phase: 05-diet-planning-subgraph
plan: "02"
subsystem: agent
tags: [python, fastapi, langgraph, postgresql, pydantic, sse]
requires:
  - phase: 05-01
    provides: deterministic target and validation contracts
  - phase: 05-07
    provides: owner-scoped minimal planning profile persistence
  - phase: 05-08
    provides: controlled recipe schema and D-08 meal DTOs
provides:
  - isolated DietPlanningState, codec, checkpoint namespace, and bounded routed graph
  - authenticated idempotent diet-planning command with safe business-only SSE
  - strict controlled-recipe seed initialization for PostgreSQL runtime tests
affects: [agent-tools, planning-api, checkpointing, runtime-startup]
tech-stack:
  added: []
  patterns: [typed planning tool port, graph-kind checkpoint isolation, safe SSE projection]
key-files:
  created:
    - backend/app/planning/importer.py
    - backend/tests/unit/test_diet_planning_graph.py
    - backend/tests/integration/test_diet_planning_agent_api.py
  modified:
    - backend/app/agent/state.py
    - backend/app/agent/graph.py
    - backend/app/agent/tools.py
    - backend/app/agent/service.py
    - backend/app/agent/api.py
    - backend/app/main.py
decisions:
  - "diet_planning uses a separate state version and checkpoint namespace; meal-analysis blobs never decode as planning state."
  - "The initial planning command is idempotently bound to an owner and Idempotency-Key-derived thread UUID; completed retries do not re-claim an execution lease."
  - "Controlled recipes and their matching nutrition catalog version are loaded by the strict initialization path before any planning API test/runtime use."
metrics:
  duration: "~65 min"
  completed: "2026-09-01"
  tasks_completed: 2
  files_changed: 14
---

# Phase 5 Plan 02: 受限饮食规划子图与严格启动命令 Summary

独立、有界的饮食规划子图通过受控工具生成并校验早餐、午餐、晚餐，且 checkpoint 与 SSE 都不会泄露餐食分析或模型内部信息。

## Accomplishments

- 固定 RED 合同：完整资料与已确认偏好才可调用目标/菜谱工具；三次重排后安全停止；meal/planning codec 交叉反序列化失败。
- 新增 `DietPlanningState`、`DietPlanningGraph` 和 `RoutedAgentGraph`；图只调用 `PlanningToolAdapter` 的确定性目标、组合、校验和显式 profile 保存能力。
- 新增认证的 `POST /api/v1/agent/threads/diet-planning`，使用 Idempotency-Key 绑定 owned thread/run；返回安全的三餐卡片与业务阶段事件。
- 补齐受控菜谱 importer，并让严格初始化先装载匹配的 rice-fist catalog 和审核菜谱 seed，避免真实 API 在空候选上假性耗尽重排预算。

## Task Commits

1. **Task 1: 写首轮 planning graph、checkpoint 和安全事件 RED 合同** — `1ca9a58` (`test`)
2. **Task 2: 实现独立 State、图、工具端口与 public Agent 接线** — `f68e7f4` (`feat`)

## Verification

- `cd backend && uv run pytest tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py tests/unit/test_agent_memory_context.py -q` — passed (9 passed).
- `cd backend && uv run ruff check app/agent app/planning/importer.py scripts/run_initialized_app.py tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py` — passed.
- `cd backend && uv run mypy app/agent/state.py app/planning/importer.py` — passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] 将审核菜谱 seed 接入严格初始化**
- **Found during:** Task 2 real PostgreSQL API verification.
- **Issue:** 05-08 创建了受控菜谱 JSON，但标准初始化只加载旧 catalog；真实规划没有合格候选，必然耗尽三次重排。
- **Fix:** 新增受控菜谱离线 importer，并在初始化中先加载匹配 `foundation-foods-2026-08-rice-fist-v1` catalog，再导入审核菜谱。
- **Files modified:** `backend/app/planning/importer.py`, `backend/scripts/run_initialized_app.py`, `backend/app/planning/README.md`.
- **Verification:** PostgreSQL API contract returns completed breakfast/lunch/dinner report.
- **Commit:** `f68e7f4`.

**2. [Rule 1 - Bug] 已完成的幂等重试不再重新申请执行 lease**
- **Found during:** Task 2 idempotency API verification.
- **Issue:** 相同 planning command 的第二次请求在 run 已完成后仍申请 PostgreSQL lease，导致与已完成 run 的锁竞争。
- **Fix:** API 对完成的同 command run 直接返回已持久化 snapshot，不再执行或重复写 profile。
- **Files modified:** `backend/app/agent/api.py`.
- **Verification:** 同 Idempotency-Key 重试返回同一 thread，owner isolation 与 SSE contract 通过。
- **Commit:** `f68e7f4`.

**Total deviations:** 2 auto-fixed (Rule 1: 1; Rule 2: 1). **Impact:** 修复是运行时正确性、幂等性和真实 PostgreSQL 可用性的必要条件；未扩张产品范围。

## Known Stubs

None — 本计划的公开 planning report、工具接线和受控 recipe seed 都连接到真实实现，没有用于 UI 渲染的空/mock 数据。

## Deferred Issues

- 既有 `tests/integration/test_agent_vertical.py::test_real_pg_api_resumes_same_waiting_run_without_repeating_the_parse` 在显式 test 环境中仍期望 `tool_calls == 0`，但当前已提交的餐食图会在解析前执行直接偏好捕获并记作一次工具调用。该行为不在本计划改动范围内，未修改餐食分析图语义。

## Self-Check: PASSED

- 已确认 `backend/app/planning/importer.py`、`backend/tests/unit/test_diet_planning_graph.py` 和 `backend/tests/integration/test_diet_planning_agent_api.py` 存在。
- 已确认任务提交 `1ca9a58` 与 `f68e7f4` 均在 Git 历史中存在。
