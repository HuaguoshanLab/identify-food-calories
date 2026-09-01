---
phase: 05-diet-planning-subgraph
plan: "01"
subsystem: planning-domain
tags: [python, pydantic, decimal, target-policy, health-safety, tdd]
requires:
  - phase: 03-multimodal-meal-analysis
    provides: "确定性 nutrition DTO、Service 和 fake-port 测试模式"
provides:
  - "target-policy.v1 的可复算成人目标区间"
  - "健康范围、确认与非保守速度的闭合安全动作"
  - "规划领域 DTO、Protocol 和确定性校验入口"
affects: [diet-planning-graph, planning-api, personal-profile, plans-h5]
tech-stack:
  added: []
  patterns: ["frozen extra-forbid public DTO", "Protocol-only domain dependency", "Decimal deterministic calculation"]
key-files:
  created:
    - backend/app/planning/schemas.py
    - backend/app/planning/service.py
    - backend/app/planning/ports.py
    - backend/tests/planning/test_planning_service.py
  modified:
    - backend/app/README.md
    - backend/tests/README.md
key-decisions:
  - "target-policy.v1 固定使用 Mifflin–St Jeor、五档活动因子、三档保守速度与 ±100 kcal 区间。"
  - "资料完整和偏好确认先返回 NEEDS_INPUT；健康 guard 在任何 target 或 recipe 访问前终止。"
  - "RELAX 只适用于能量或宏量目标，确认排除项和健康底线永远不能放宽。"
patterns-established:
  - "规划图与浏览器只消费动作 DTO，不能重算公式或安全结论。"
  - "规划领域服务仅依赖 Protocol，未引入 ORM、HTTP、Provider 或 LangGraph State。"
requirements-completed: [PLN-01, PLN-02, PLN-04, PLN-06]
duration: 14min
completed: 2026-09-01
---

# Phase 5 Plan 01: 确定性目标与安全合同 Summary

**以 `target-policy.v1` 提供可复算的成年目标区间、健康拒绝和闭合餐单校验动作，杜绝浏览器或模型成为数值真相来源。**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-01T07:25:00Z
- **Completed:** 2026-09-01T07:39:26Z
- **Tasks:** 2/2
- **Files modified:** 9

## Accomplishments

- 用冻结且 `extra="forbid"` 的 profile、偏好、目标、菜谱与结果 DTO 固化公开规划合同。
- 使用 `Decimal` 实现 Mifflin–St Jeor、五档活动因子、保守速度、±100 kcal 与 4/4/9 AMDR 区间。
- 在数值计算和任何未来 recipe 检索前拒绝未成年人、孕哺、疾病/用药、进食障碍/自伤、极端目标、未知速度和低能量结果。
- 新增 fake-port 测试，覆盖确认、拒绝、闭合动作和不可放宽的排除项。

## Task Commits

Each task was committed atomically:

1. **Task 1: 写确定性目标、确认和健康拒绝的 RED 合同** — `518ee36` (`test`)
2. **Task 2: 实现版本化确定性规划领域合同** — `cd2e36c` (`feat`)

## Files Created/Modified

- `backend/app/planning/schemas.py` — 版本、严格 DTO、闭合 action 与结果不变量。
- `backend/app/planning/service.py` — 目标计算、D-15 guard 和确定性校验入口。
- `backend/app/planning/ports.py` — profile/recipe/nutrition 的窄 Protocol 边界。
- `backend/app/planning/README.md` — 目录职责、允许依赖和文件索引。
- `backend/tests/planning/test_planning_service.py` — fake-port 的目标与安全合同证据。
- `backend/app/README.md`、`backend/tests/README.md`、`backend/tests/planning/README.md` — 目录索引与测试职责。

## Decisions Made

- `target-policy.v1` 固定使用 Mifflin–St Jeor、五档活动因子、三档保守速度与 ±100 kcal 公共区间。
- 未完整资料或未确认偏好返回 `NEEDS_INPUT`；高风险输入和非保守速度返回 `BLOCK_HEALTH_SCOPE`。
- `RELAX` 不得接受已确认排除项或任何健康边界。

## Verification

- `cd backend && uv run pytest tests/planning/test_planning_service.py -q` — 22 passed。
- `cd backend && uv run ruff check app/planning tests/planning` — passed。
- `cd backend && uv run mypy app/planning` — passed。
- `cd backend && uv run pytest tests/architecture/test_directory_contract.py -q` — 2 passed。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正未实际落到安全阈值以下的低能量 fixture**
- **Found during:** Task 2（实现版本化确定性规划领域合同）
- **Issue:** 原测试资料计算后的目标区间下限仍为 1202 kcal，不会触发计划要求的 `<1200 kcal` 健康拒绝。
- **Fix:** 将纯合成资料调整为 130 cm、25 kg、78 岁，使计算结果真实落在安全阈值以下。
- **Files modified:** `backend/tests/planning/test_planning_service.py`
- **Verification:** 22 项规划测试均通过。
- **Committed in:** `cd2e36c`（part of task commit）

---

**Total deviations:** 1 auto-fixed（Rule 1: 1）
**Impact on plan:** 修复仅让 RED 合同准确覆盖已冻结的安全边界，没有扩大功能范围。

## Issues Encountered

首次在受限沙箱中运行 `uv` 无法访问用户级缓存；获得授权后正常执行。不是代码问题。

## Known Stubs

None — 本计划创建的公开领域合同没有流向 UI 的空值、占位文案或 mock 数据源。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

后续 ORM、规划图、API 和 H5 可直接消费严格的动作 DTO 与 `target-policy.v1`，无需重写公式、确认或健康边界。计划校验的 recipe totals 与持久化 adapter 仍由后续计划实现。

## Self-Check: PASSED

- 已确认 8 个新增领域/测试/摘要文件存在。
- 已确认任务提交 `518ee36` 与 `cd2e36c` 存在于 Git 历史。

---
*Phase: 05-diet-planning-subgraph*
*Completed: 2026-09-01*
