---
phase: 05-diet-planning-subgraph
plan: "04"
subsystem: agent
tags: [python, fastapi, langgraph, postgresql, sse, memory]
requires:
  - phase: 05-02
    provides: isolated DietPlanningState, owned planning commands, checkpoints, and safe SSE
  - phase: 04-07
    provides: typed explicit-preference capture with owner-scoped, delete-aware memory semantics
provides:
  - same-thread, slot-local planning replacement with preserved unaffected meals and exclusions
  - replay-safe explicit preference capture and bounded three-adjustment recovery
  - safe range/RELAX projection without feedback, provider, ledger, or reasoning disclosure
affects: [planning-api, agent-tools, memory, planning-ui]
tech-stack:
  added: []
  patterns: [closed planning resume payload, slot-local replacement, opaque capture markers, safe adjustment SSE projection]
key-files:
  created:
    - docs/learning/05-diet-planning-adjustments.md
  modified:
    - backend/app/agent/graph.py
    - backend/app/agent/tools.py
    - backend/app/agent/service.py
    - backend/app/agent/api.py
    - backend/app/planning/service.py
    - backend/app/planning/data/controlled-recipes.v1.json
    - backend/tests/unit/test_diet_planning_graph.py
    - backend/tests/integration/test_diet_planning_agent_api.py
key-decisions:
  - "Planning feedback stays on the existing owned thread and is reduced to a closed intent plus an optional breakfast/lunch/dinner slot."
  - "Only opaque SHA-256 capture markers persist in planning state; explicit preference writes cross the existing typed memory tool boundary."
  - "Slot replacement asks PlanningService to exclude the old recipe, while untouched slots are retained verbatim by the adapter."
patterns-established:
  - "Adjustment reports expose business-safe changed slots, range status, and permitted energy/macro relaxation facts only."
  - "A terminal third adjustment persists LIMIT_REACHED; subsequent commands do not call planning composition."
requirements-completed: [PLN-04, PLN-05, PLN-06]
duration: 28min
completed: 2026-09-01
---

# Phase 5 Plan 04: 后端局部调整、记忆捕获、透明放宽与有界恢复 Summary

**同一规划线程现在可安全替换单个早餐、午餐或晚餐，捕获明确偏好，并在三次调整后以透明安全投影终止。**

## Performance

- **Duration:** 28 min
- **Started:** 2026-09-01T08:26:00Z
- **Completed:** 2026-09-01T08:54:03Z
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- RED contracts 覆盖 local replacement、闭合三餐 choice、显式记忆写入幂等、RELAX 安全 DTO 和第四次 command 不执行 composition。
- `DietPlanningGraph` 将 feedback 降为已验证的槽位/意图，保留未受影响餐次、confirmed exclusions 与健康边界，并只经 typed planning/memory tools 执行副作用。
- 公开 Agent API 依据 planning checkpoint namespace 在同一 owned thread 执行调整；snapshot/SSE 不包含原始 feedback、ledger/provider ID、工具结果或推理内容。
- 新增第二个审核午餐候选，使真正的 slot-local dish replacement 可达，而不是伪造一次全餐重组。

## Task Commits

1. **Task 1: 写 local replacement、memory replay、RELAX 和 limit 的 RED 后端合同** — `62bd2cb` (`test`)
2. **Task 2: 实现约束保留、审计记忆和安全恢复投影** — `ac2ef27` (`feat`)

## Verification

- PASS — `cd backend && uv run pytest tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py -q` — 11 passed。
- PASS — `cd backend && uv run ruff check app/agent app/planning/service.py tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py`。
- PASS — `cd backend && uv run python -m json.tool app/planning/data/controlled-recipes.v1.json >/dev/null`。
- PARTIAL — `uv run mypy app/agent/graph.py app/agent/api.py` 仅因既有 `app/memory/providers.py` 的 Mem0 缺少 `py.typed` 和 object 类型错误失败；本计划修改入口没有新增 mypy 报错。

## Files Created/Modified

- `backend/app/agent/{state.py,graph.py,tools.py,service.py,api.py}` — planning state replay markers、slot-local graph routing、typed tool boundary和 same-thread API recovery。
- `backend/app/planning/service.py` 与 `backend/app/planning/data/controlled-recipes.v1.json` — 领域服务排除当前菜谱，并提供第二个审核午餐候选。
- `backend/tests/unit/test_diet_planning_graph.py` 与 `backend/tests/integration/test_diet_planning_agent_api.py` — fake graph 和真实 PostgreSQL/HTTPX 合同。
- `docs/learning/05-diet-planning-adjustments.md` — 中文设计、数据流、测试与常见错误教学。

## Decisions Made

- 同线程调整使用既有 `/input` public API，而不是引入平行 endpoint；run command hash 继续提供幂等边界。
- 歧义反馈只返回 `breakfast`、`lunch`、`dinner` choice；无效 resume 是 no-op。
- RELAX 投影只公开 energy/macro 的原范围、计划值、偏离和理由；排除项和 health safety 从不进入可放宽集合。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] 增加审核的备用午餐候选**
- **Found during:** Task 2
- **Issue:** 受控 seed 每个餐次只有一个合格候选。排除当前午餐后没有任何真实替换项，局部“换菜”一定失败。
- **Fix:** 增加第二个项目自有、审核通过的午餐 recipe，并由 `PlanningService` 排除当前 recipe 后选择 replacement。
- **Files modified:** `backend/app/planning/service.py`, `backend/app/planning/data/controlled-recipes.v1.json`, `backend/app/planning/data/README.md`。
- **Verification:** 真实 PostgreSQL API 调整后早餐/晚餐 identity 不变、午餐发生替换；11 个 graph/API tests passed。
- **Committed in:** `ac2ef27`

**Total deviations:** 1 auto-fixed (Rule 2: 1). **Impact on plan:** 这是兑现局部替换合同所必需的受控领域数据补全，没有扩张到前端或非受控菜谱能力。

## Known Stubs

None — adjustment 使用真实 planning service、真实 PostgreSQL candidate seed 和 Phase 4 memory ledger；没有接入空/mock UI 数据。

## Issues Encountered

- `uv` 在 sandbox 内不能访问既有用户级 cache；以受控批准重跑后，pytest/Ruff 均完成。
- mypy 会跟随 import 进入未修改的 `app/memory/providers.py`，暴露既有 Mem0 typing 问题；本计划未修改该模块，未将其误修为范围内变更。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 后续 H5 计划页可消费安全 `adjustment`、`range_status`、`relaxation` 与 `LIMIT_REACHED` 投影，而无需了解 graph/tool/checkpoint 内部细节。
- `app/memory/providers.py` 的既有 mypy 问题仍待独立类型维护任务处理。

## Self-Check: PASSED

- 已确认 `backend/app/agent/graph.py`、`backend/tests/unit/test_diet_planning_graph.py`、`backend/tests/integration/test_diet_planning_agent_api.py` 与 `docs/learning/05-diet-planning-adjustments.md` 存在。
- 已确认任务提交 `62bd2cb` 与 `ac2ef27` 均在 Git 历史中存在。
