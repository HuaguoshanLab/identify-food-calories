---
phase: 06-user-dashboard-admin
plan: 05
subsystem: api
tags: [fastapi, sse, pydantic, langgraph, security, pytest]
requires:
  - phase: 03-multimodal-agent
    provides: Agent ledger, graph state, and authenticated SSE replay boundary
  - phase: 05-diet-planning-subgraph
    provides: bounded diet-planning graph and deterministic validation tools
provides:
  - Versioned strict safe-stage SSE DTO for browser progress UI
  - Allowlisted meal-analysis and diet-planning lifecycle mappings
  - Actual calculation and validation progress events without payload leakage
affects: [06-user-dashboard-admin, frontend-agent-progress, agent-api]
tech-stack:
  added: []
  patterns: ["SSE replays a versioned allowlist DTO instead of ledger events", "completed is emitted only as completed_validated after a report exists"]
key-files:
  created:
    - backend/tests/unit/test_safe_stream_stage_api.py
    - backend/tests/agent/test_safe_stream_stage_mapping.py
    - backend/tests/planning/test_safe_stream_stage_mapping.py
  modified:
    - backend/app/agent/schemas.py
    - backend/app/agent/api.py
    - backend/app/agent/service.py
    - backend/app/planning/schemas.py
    - backend/app/planning/service.py
key-decisions:
  - "SSE only exposes schema_version, stage, and safe message; it never serializes ledger payloads."
  - "Only a completed_validated event can render the completed stage."
  - "A single Agent SSE endpoint is the public boundary for both meal analysis and diet planning."
patterns-established:
  - "Map closed persisted lifecycle labels to user stages, and ignore unknown labels fail-closed."
  - "Derive calculation and validation progress from completed allowlisted tool summaries, not graph nodes or State."
requirements-completed: [UI-03]
duration: 10min
completed: 2026-09-02
---

# Phase 06 Plan 05: 安全业务阶段映射 Summary

**餐食分析与饮食规划共用版本化 SSE 阶段契约，完整呈现感知、补充、计算、校验、完成及安全失败结果，且不泄露内部事件负载。**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-02T09:12:33Z
- **Completed:** 2026-09-02T09:22:29Z
- **Tasks:** 2/2
- **Files modified:** 15

## Accomplishments

- 定义 `safe-stream-stage.v1` 严格 DTO，仅允许版本、阶段与安全文案进入 SSE。
- 为分析和规划覆盖感知、等待补充、工具计算、校验、已验证完成、可重试和终止状态。
- 仅在受控工具确实完成计算或校验后追加进度事件；未知事件一律不输出。

## Task Commits

1. **Task 1: 对两条 SSE 链写完整阶段 RED 矩阵** - `9bdc5af` (`test`)
2. **Task 2: 发布 canonical safe SSE stage 契约** - `ea676b7` (`feat`)

## Files Created/Modified

- `backend/app/agent/schemas.py` - 严格、版本化的安全 SSE 阶段 DTO。
- `backend/app/agent/api.py` - 只回放 allowlist DTO，并保持 SSE sequence/idempotency 语义。
- `backend/app/agent/service.py` - 在实际计算、校验和最终状态后记录安全阶段事件。
- `backend/app/planning/schemas.py`、`backend/app/planning/service.py` - 规划生命周期的闭合 allowlist 映射。
- `backend/tests/unit/test_safe_stream_stage_api.py` - 验证 DTO 排除 payload、State、Provider 与 base64。

## Decisions Made

- 使用 `completed_validated` 作为唯一完成信号，避免未经验证的内部 `completed` 事件被前端当作结果完成。
- 复用 Agent 的单一 SSE API 作为两条图的公开流边界；规划模块只提供不接触 State/Provider 的纯映射。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 同名测试模块在 pytest 默认导入模式下冲突**
- **Found during:** Task 2
- **Issue:** `tests/agent/` 与 `tests/planning/` 的同名测试文件导致 collection mismatch。
- **Fix:** 为两个测试目录新增 Python package namespace，并同步目录索引。
- **Files modified:** `backend/tests/agent/__init__.py`, `backend/tests/planning/__init__.py` 及对应 README。
- **Verification:** 阶段矩阵测试 18 passed。
- **Committed in:** `ea676b7`

**2. [Rule 1 - Bug] 新完成事件未被线程快照投影识别**
- **Found during:** Task 2 集成验证
- **Issue:** 改用 `completed_validated`、`retryable`、`terminal` 后，快照忽略其安全 report，导致公开 API 返回 `report: null`。
- **Fix:** 将新 allowlisted 终态加入快照事件筛选，仍只读取安全 report 字段。
- **Files modified:** `backend/app/agent/api.py`
- **Verification:** PostgreSQL 公开规划 API 集成测试 5 passed。
- **Committed in:** `ea676b7`

**3. [Rule 3 - Blocking] 计划引用的 `backend/app/planning/graph.py` 不存在**
- **Found during:** Task 2 read-first
- **Issue:** 实际饮食规划子图位于 `backend/app/agent/graph.py`，公开 SSE 同样由 `agent/api.py` 提供。
- **Fix:** 以实际唯一公开流边界和已存在的子图实现作为依据；规划模块仅保留纯生命周期映射。
- **Files modified:** `backend/app/agent/api.py`, `backend/app/agent/service.py`, `backend/app/planning/service.py`
- **Verification:** 阶段映射单元测试与公开规划 API 集成测试均通过。
- **Committed in:** `ea676b7`

---

**Total deviations:** 3 auto-fixed（2 个 Rule 1，1 个 Rule 3）。
**Impact on plan:** 均为测试可运行性、公开快照正确性和实际代码布局的必要修复；未扩展功能范围。

## Issues Encountered

- 沙箱默认禁止访问隔离 PostgreSQL；获准连接本机测试库后，`tests/integration/test_diet_planning_agent_api.py` 通过。
- `mypy` 仍报告 `backend/app/memory/providers.py` 的既有 Mem0 类型错误，已记录到本阶段 `deferred-items.md`；本计划修改的文件不再有 mypy 错误。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 前端可消费稳定的 `safe-stream-stage.v1` SSE 进度来源。
- 完整 `uv run mypy app` 仍受既有 Mem0 provider 类型问题阻塞，已记录为独立维护项。

## Self-Check: PASSED

- 已确认三个新增阶段测试文件存在。
- 已确认 `9bdc5af` 与 `ea676b7` 均存在于 Git 历史。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
